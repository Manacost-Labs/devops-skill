#!/usr/bin/env python3
"""Prepare an unsigned owner-reviewed JEA bundle; never installs or grants."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath, PurePosixPath
import re
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepared_windows_protocol',ROOT/'tools/windows_bridge.py')
B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)


def literal(value):
    """Static PowerShell data, never executable expressions from plan strings."""
    if isinstance(value,str):
        B.require(not any(ord(c)<32 or ord(c)==127 for c in value))
        return "'"+value.replace("'","''")+"'"
    if type(value) is bool:return '$true' if value else '$false'
    if type(value) is int:return str(value)
    if isinstance(value,list):return '@('+','.join(literal(x) for x in value)+')'
    if isinstance(value,dict):return '@{'+(';'.join(literal(k)+'='+literal(v) for k,v in value.items()))+'}'
    raise B.Refused('unsupported owner configuration value')


def schema(value):
    B.require(isinstance(value,dict) and len(value)<=32)
    result={}
    for name,rule in value.items():
        B.require(re.fullmatch(r'[a-z][a-z0-9_]{0,31}',name) and isinstance(rule,dict))
        if rule=={'type':'digest'}:result[name]={'Type':'digest'}
        elif set(rule)=={'type','minimum','maximum'}:
            B.require(rule['type']=='integer' and type(rule['minimum']) is int and type(rule['maximum']) is int and -(2**53)<rule['minimum']<=rule['maximum']<2**53)
            result[name]={'Type':'integer','Minimum':rule['minimum'],'Maximum':rule['maximum']}
        else:
            B.exact(rule,{'enum'})
            B.require(isinstance(rule['enum'],list) and 1<=len(rule['enum'])<=128 and all(type(x) in (str,int,bool) for x in rule['enum']))
            B.require(all(not isinstance(x,str) or 1<=len(x)<=256 for x in rule['enum']))
            result[name]={'Enum':rule['enum']}
    return result


def prepare(plan, output):
    B.exact(plan,{'schema_version','endpoint_name','connector','run_as_gmsa','module_root','state_root','target_id','target_resource','tasks'})
    B.require(plan['schema_version']=='1.0')
    B.require(re.fullmatch(r'DevopsBound-[a-z0-9-]{6,64}',plan['endpoint_name']))
    B.require(re.fullmatch(r'[A-Za-z0-9_.-]+\\[A-Za-z0-9_.-]+',plan['connector']))
    B.require(re.fullmatch(r'[A-Za-z0-9_.-]+\\[A-Za-z0-9_.-]+\$',plan['run_as_gmsa']))
    B.require(re.fullmatch(r'[a-z][a-z0-9-]{5,79}',plan['target_id']))
    for name in ('module_root','state_root'):B.require(PureWindowsPath(plan[name]).is_absolute())
    B.require(isinstance(plan['tasks'],dict) and 1<=len(plan['tasks'])<=128)
    files={};tasks={}
    for name,task in plan['tasks'].items():
        B.require(re.fullmatch(r'[a-z][a-z0-9-]{5,79}',name))
        B.exact(task,{'source_file','parameters','result_schema'})
        source=Path(task['source_file'])
        B.require(source.is_absolute() and source.is_file() and not source.is_symlink() and 0<source.stat().st_size<=1024*1024)
        raw=source.read_bytes()
        filename=name+'.ps1'
        files[filename]=raw
        tasks[name]={'File':filename,'SHA256':'sha256:'+hashlib.sha256(raw).hexdigest(),'Parameters':schema(task['parameters']),'Result':schema(task['result_schema'])}
    # No circular digest: bind the unsigned target settings before inserting
    # this endpoint's code/contract binding; then bind the complete resource.
    resource=dict(plan['target_resource'])
    B.require('binding_digest' not in resource)
    binding=B.digest({'target_id':plan['target_id'],'endpoint_name':plan['endpoint_name'],'target':resource,'tasks':tasks,
        'module_sha256':hashlib.sha256((ROOT/'tools/windows_endpoint/DevopsEndpoint.psm1').read_bytes()).hexdigest()})
    resource['binding_digest']=binding
    B.require(resource['configuration_name']==plan['endpoint_name'])
    target_digest=B.digest(resource)
    now=datetime.now(timezone.utc)
    probe={'schema_version':'2.0','target':resource,'parameters':{},'context':{'operation_id':'ops-preparation-check','task_id':next(iter(tasks)),
        'target_id':plan['target_id'],'call_digest':'sha256:'+'0'*64,'grant_digest':'sha256:'+'0'*64,'registry_digest':'sha256:'+'0'*64,
        'epoch':'0'*64,'not_before':(now-timedelta(minutes=1)).isoformat(),'expires':(now+timedelta(minutes=1)).isoformat(),
        'parameters_digest':B.digest({}),'target_digest':target_digest}}
    B.validate(probe,path_type=PurePosixPath)
    config={'SchemaVersion':'1.0','TargetId':plan['target_id'],'TargetDigest':target_digest,'BindingDigest':binding,
        'StatePath':plan['state_root'],'BootId':'__OWNER_CURRENT_BOOT__','Tasks':tasks}
    files['DevopsEndpoint.psm1']=(ROOT/'tools/windows_endpoint/DevopsEndpoint.psm1').read_bytes()
    files['endpoint.psd1']=(literal(config)+'\n').encode('utf-8-sig')
    role={'GUID':'7d90c8b1-8134-4da4-90ce-2e4152f503b4','VisibleFunctions':['Get-DevopsEndpointBinding','Get-DevopsBoundTaskStatus','Invoke-DevopsBoundTask'],
        'VisibleCmdlets':[],'VisibleAliases':[],'VisibleExternalCommands':[]}
    files['DevopsBoundRole.psrc']=(literal(role)+'\n').encode('utf-8-sig')
    manifest={key:plan[key] for key in ('schema_version','endpoint_name','connector','run_as_gmsa','module_root','state_root')}
    manifest['files']={name:hashlib.sha256(raw).hexdigest() for name,raw in sorted(files.items())}
    output.mkdir(mode=0o700)
    for name,raw in files.items():(output/name).write_bytes(raw)
    (output/'owner-manifest.json').write_bytes(B.canonical(manifest)+b'\n')
    (output/'target-resource.review.json').write_bytes(B.canonical(resource)+b'\n')
    shutil.copyfile(ROOT/'tools/install_windows_endpoint.ps1',output/'Install-ReviewedEndpoint.ps1')
    return hashlib.sha256((output/'owner-manifest.json').read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        B.require(args.plan.is_file() and not args.plan.is_symlink() and args.plan.stat().st_size<=LIMIT)
        digest=prepare(B.decode(args.plan.read_bytes()),args.output)
        print('PREPARED_NOT_INSTALLED owner_manifest_sha256='+digest)
        return 0
    except Exception:
        print('BLOCKED: invalid owner plan, source or occupied output; no endpoint or authority installed')
        return 3


LIMIT=65536
if __name__=='__main__':raise SystemExit(main())
