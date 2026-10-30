"""Pinned real Codex hook loop against a no-auth loopback Responses fixture.

No live model, account, user settings or target. Managed-policy tests run only on
disposable GitHub runners. Windows coverage is protocol/launcher, not ACL proof.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.165.0'
ASSETS={
    'linux':('codex-x86_64-unknown-linux-musl.tar.gz','be635d3486a5bd060d0fff582ae6d30160280c31344dd85719707fa920e187f0'),
    'win32':('codex-x86_64-pc-windows-msvc.exe.zip','4d7bb0a781cadf10123966c9f78501e418c5be7ce785703739a9b15e88902741'),
}


class Provider(ThreadingHTTPServer):
    def __init__(self,command):
        self.command=command; self.requests=[]; self.outputs=[]; self.failure=None
        super().__init__(('127.0.0.1',0),Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_POST(self):
        try:
            if self.headers.get('Content-Encoding') not in (None,'identity'): raise ValueError('unexpected compression')
            length=int(self.headers['Content-Length']); assert length<2*1024*1024
            request=json.loads(self.rfile.read(length)); self.server.requests.append(request)
            outputs=[item for item in request.get('input',[]) if item.get('type') in ('function_call_output','custom_tool_call_output')]
            if outputs:
                self.server.outputs.extend(outputs)
                item={'id':'msg_fixture','type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':'fixture complete','annotations':[]}]}
            else:
                tools=request.get('tools',[])
                names=('exec_command','shell_command','shell')
                candidates=[item for item in tools if item.get('name') in names]
                if not candidates: raise ValueError('native shell tool absent: '+str([item.get('name',item.get('type')) for item in tools]))
                tool=candidates[0]; properties=tool.get('parameters',{}).get('properties',{})
                field='cmd' if 'cmd' in properties else 'command'
                value=self.server.command
                if properties.get(field,{}).get('type')=='array':
                    value=['powershell.exe','-NoProfile','-Command',value] if os.name=='nt' else ['/bin/sh','-c',value]
                arguments={field:value}
                if 'login' in properties: arguments['login']=False
                item={'id':'fc_fixture','type':'function_call','call_id':'call_fixture','name':tool['name'],'arguments':json.dumps(arguments)}
            events=[{'type':'response.created','response':{'id':'resp_fixture','object':'response','status':'in_progress'}},
                {'type':'response.output_item.done','output_index':0,'item':item},
                {'type':'response.completed','response':{'id':'resp_fixture','object':'response','status':'completed','output':[item],
                    'usage':{'input_tokens':10,'output_tokens':10,'total_tokens':20}}}]
            body=''.join('event: '+event['type']+'\ndata: '+json.dumps(event)+'\n\n' for event in events).encode()
            self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        except Exception as exc:
            self.server.failure=str(exc); self.send_error(500,'fixture protocol failure')


def cli(folder):
    asset,digest=ASSETS[sys.platform]
    archive=folder/asset
    with urllib.request.urlopen('https://github.com/openai/codex/releases/download/rust-v'+VERSION+'/'+asset,timeout=60) as response:
        archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=digest: raise RuntimeError('pinned Codex digest mismatch')
    target=folder/'cli'; target.mkdir()
    if sys.platform=='win32':
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                if member.filename.startswith(('/', '\\')) or '..' in Path(member.filename).parts: raise RuntimeError('unsafe release member')
            source.extractall(target)
        executable=target/'codex-x86_64-pc-windows-msvc.exe'
    else:
        with tarfile.open(archive) as source: source.extractall(target,filter='data')
        executable=target/'codex-x86_64-unknown-linux-musl'; executable.chmod(0o755)
    return executable


def run(executable,folder,guarded,helper=False,managed_probe=None):
    home=folder/('managed-exec-'+managed_probe if managed_probe else 'helper' if helper else 'guarded' if guarded else 'control'); home.mkdir()
    workspace=home/'workspace'; workspace.mkdir()
    marker=workspace/'canary'
    script="from pathlib import Path; Path("+repr(str(marker))+").write_text('executed')"
    import shlex
    if os.name=='nt':
        quote=lambda x:"'"+str(x).replace("'","''")+"'"
        command='& '+quote(sys.executable)+' -I -c '+quote(script)
    else: command=shlex.join([sys.executable,'-I','-c',script])
    if helper:
        arguments=[sys.executable,'-I',str(ROOT/'devops-platform-contracts/scripts/validate_platform.py')]
        command='& '+' '.join(quote(item) for item in arguments) if os.name=='nt' else shlex.join(arguments)
    provider=Provider(command); thread=threading.Thread(target=provider.serve_forever,daemon=True); thread.start()
    config=['model = "gpt-5.3-codex"','model_provider = "fixture"','approval_policy = "never"','sandbox_mode = "danger-full-access"',
        '[features]','hooks = true','unified_exec = false','enable_request_compression = false','plugins = false','apps = false',
        '[model_providers.fixture]','name = "owned loopback fixture"','base_url = "http://127.0.0.1:'+str(provider.server_port)+'/v1"',
        'wire_api = "responses"','requires_openai_auth = false','supports_websockets = false']
    if managed_probe=='named':
        config.remove('sandbox_mode = "danger-full-access"')
    if guarded:
        spec=importlib.util.spec_from_file_location('native_setup',ROOT/'tools/devops_guard_setup.py')
        setup=importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)
        hook=setup.hook_command(sys.executable,ROOT/'tools/hooks/codex_pretooluse_gate.py','windows' if os.name=='nt' else 'linux')
        config+=['[[hooks.PreToolUse]]','matcher = "*"','[[hooks.PreToolUse.hooks]]','type = "command"','command = '+json.dumps(hook),'timeout = 15']
    (home/'config.toml').write_text('\n'.join(config)+'\n',encoding='utf-8')
    # No inherited account tokens/provider settings. OS launch needs these only.
    environment={key:value for key,value in os.environ.items() if key.upper() in {'PATH','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','TMPDIR','HOME','USERPROFILE','LANG','SYSTEMDRIVE'}}
    environment['CODEX_HOME']=str(home); environment['RUST_LOG']='error'
    try:
        try:
            selection=['--sandbox','danger-full-access'] if managed_probe=='legacy' else ['-c','default_permissions=":danger-full-access"'] if managed_probe=='named' else []
            result=subprocess.run([str(executable),'exec','--json','--ephemeral','--skip-git-repo-check','--dangerously-bypass-hook-trust',*selection,'fixture'],cwd=workspace,env=environment,input='',capture_output=True,text=True,encoding='utf-8',timeout=40)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('native timeout; requests='+str(len(provider.requests))+'; failure='+str(provider.failure)+'; stdout='+str(exc.stdout)[-3000:]+'; stderr='+str(exc.stderr)[-3000:]) from None
        if provider.failure: raise RuntimeError(provider.failure)
        if managed_probe and result.returncode and not provider.outputs:
            refusal=(result.stderr+result.stdout).lower()
            if not provider.requests and 'danger-full-access' in refusal and any(word in refusal for word in ('not allowed','not permitted','allowed_permission_profiles','allowed_sandbox_modes','requirement')):
                print('managed Full Access: actual profile refusal before model/tool execution'); return
        if result.returncode or not provider.outputs: raise RuntimeError('native tool loop failed: '+result.stderr[-3000:]+' '+result.stdout[-3000:])
        observation=json.dumps(provider.outputs)
        if helper:
            if '23/23 compatible installed skills' not in observation: raise RuntimeError('registered offline helper did not execute: '+observation)
        elif guarded or managed_probe:
            if marker.exists() or 'BLOCKED' not in observation: raise RuntimeError('guard did not prevent canary: '+observation+'; stderr='+result.stderr[-3000:]+'; stdout='+result.stdout[-5000:])
        elif not marker.is_file() or marker.read_text()!='executed': raise RuntimeError('positive control did not execute: '+observation)
        print(('managed override refusal' if managed_probe else 'registered helper' if helper else 'guard denial' if guarded else 'positive control')+': actual Codex tool loop passed')
    finally:
        provider.shutdown(); provider.server_close(); thread.join(2)


def resolved_permissions(executable,home,environment,managed_policy=True):
    """Observe actual native thread admission without starting any model turn.

The runtime may correctly fall back to a required profile instead of throwing.
The typed app-server response establishes the effective permissions independently
of a tool hook's canary denial. No shell/sandbox worker or model is invoked here.
"""
    (home/'config.toml').write_text('model_provider="fixture"\nmodel="gpt-5.3-codex"\n'+
        ('' if managed_policy else 'default_permissions=":danger-full-access"\n')+
        '[model_providers.fixture]\nname="owned no-turn fixture"\nbase_url="http://127.0.0.1:9/v1"\n'
        'wire_api="responses"\nrequires_openai_auth=false\nsupports_websockets=false\n',encoding='utf-8')
    messages=queue.Queue()
    with (home/'app-server.stderr').open('w',encoding='utf-8') as errors:
        process=subprocess.Popen([str(executable),'app-server','--stdio','--strict-config'],env=environment,cwd=home,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errors,text=True,encoding='utf-8',bufsize=1)
        def read():
            try:
                for line in process.stdout:
                    if len(line)>1024*1024: raise ValueError('bounded native response required')
                    messages.put(json.loads(line))
            except Exception as exc: messages.put(exc)
        reader=threading.Thread(target=read,daemon=True); reader.start()
        def rpc(identifier,method,params):
            process.stdin.write(json.dumps({'id':identifier,'method':method,'params':params})+'\n'); process.stdin.flush()
            deadline=time.monotonic()+20
            while True:
                message=messages.get(timeout=max(.01,deadline-time.monotonic()))
                if isinstance(message,Exception): raise message
                if message.get('id')==identifier: return message
                if time.monotonic()>deadline: raise TimeoutError('native permission response unavailable')
        try:
            initialized=rpc(1,'initialize',{'clientInfo':{'name':'devops-native-fixture','version':'1.0'},'capabilities':{'experimentalApi':True}})
            if 'result' not in initialized: raise RuntimeError('native initialization refused')
            process.stdin.write(json.dumps({'method':'initialized'})+'\n'); process.stdin.flush()
            for identifier,overrides in enumerate(({'sandbox':'danger-full-access'},{'permissions':':danger-full-access'},{'config':{'default_permissions':':danger-full-access'}}),2):
                response=rpc(identifier,'thread/start',{'cwd':str(home),'ephemeral':True,'environments':[],**overrides})
                if 'error' in response:
                    refusal=json.dumps(response['error']).lower()
                    if managed_policy and 'danger-full-access' in refusal and any(word in refusal for word in ('not allowed','not permitted','requirement')):
                        continue
                    raise RuntimeError('unrelated native admission error: '+refusal[-1500:])
                value=response.get('result',{})
                sandbox=value.get('sandbox',{})
                active=value.get('activePermissionProfile') or {}
                expected_type='readOnly' if managed_policy else 'dangerFullAccess'
                expected_profile=':read-only' if managed_policy else ':danger-full-access'
                # Legacy sandbox selectors can omit profile provenance. The
                # typed effective sandbox remains authoritative in that case.
                profile_matches=active.get('id')==expected_profile or overrides.get('sandbox') and not active
                if sandbox.get('type')!=expected_type or not profile_matches or managed_policy and sandbox.get('networkAccess') is not False:
                    raise RuntimeError('unexpected native permissions: '+json.dumps({'sandbox':sandbox,'active':active,'keys':list(value),'overrides':overrides,'thread_keys':list(value.get('thread',{}))}))
            print('managed runtime: all three Full Access selections resolve to read-only or explicit policy refusal, without model/tools' if managed_policy else 'permission control: all three selectors resolve to Full Access without managed constraints')
        finally:
            process.stdin.close()
            if process.poll() is None: process.terminate()
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
            reader.join(2); process.stdout.close()


def managed(executable,folder):
    """Install/revert only an absent requirements file on an owned disposable VM."""
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise RuntimeError('managed policy tests require a disposable GitHub VM')
    path=Path(os.environ['PROGRAMDATA'])/'OpenAI/Codex/requirements.toml' if os.name=='nt' else Path('/etc/codex/requirements.toml')
    spec=importlib.util.spec_from_file_location('managed_review_setup',ROOT/'tools/devops_guard_setup.py')
    setup=importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)
    content=setup.prepare(str(ROOT),sys.executable,'windows' if os.name=='nt' else 'linux')
    source=folder/'managed.review.toml'; source.write_text(content,encoding='utf-8')
    # Exact fixed managed path; no overwrite of runner images carrying policy.
    install="from pathlib import Path; import sys; p=Path(sys.argv[1]); p.parent.mkdir(parents=True,exist_ok=True); p.open('xb').write(Path(sys.argv[2]).read_bytes())"
    remove="from pathlib import Path; import sys; p=Path(sys.argv[1]); assert p.read_bytes()==Path(sys.argv[2]).read_bytes(); p.unlink()"
    prefix=[] if os.name=='nt' else ['sudo','--']
    subprocess.run([*prefix,sys.executable,'-I','-c',install,str(path),str(source)],check=True,capture_output=True,text=True)
    try:
        home=folder/'managed-home'; home.mkdir()
        (home/'config.toml').write_text('[features]\nhooks = false\nunified_exec = true\napps = true\nplugins = true\n',encoding='utf-8')
        environment={key:value for key,value in os.environ.items() if key.upper() in {'PATH','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','HOME','USERPROFILE'}}
        environment['CODEX_HOME']=str(home)
        result=subprocess.run([str(executable),'features','list'],env=environment,cwd=home,capture_output=True,text=True,timeout=20)
        if result.returncode: raise RuntimeError('managed template did not load: '+result.stderr[-3000:])
        rows={line.split()[0]:line.split()[-1] for line in result.stdout.splitlines() if line.split()}
        for name,expected in {'hooks':'true','unified_exec':'false','apps':'false','plugins':'false'}.items():
            if rows.get(name)!=expected: raise RuntimeError('managed feature override accepted: '+name+' '+result.stdout)
        # Read the runtime's constrained thread policy independently of hooks.
        resolved_permissions(executable,home,environment)
        run(executable,folder,False,managed_probe='legacy')
        run(executable,folder,False,managed_probe='named')
        print('managed policy: hostile feature overrides and Full Access refused by actual Codex')
    finally:
        subprocess.run([*prefix,sys.executable,'-I','-c',remove,str(path),str(source)],check=True,capture_output=True,text=True)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--development-cli',type=Path); args=parser.parse_args()
    if not args.development_cli and (os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted'):
        raise RuntimeError('disposable GitHub-hosted runner required')
    parent=Path(os.environ.get('RUNNER_TEMP',ROOT.parent)).resolve()
    with tempfile.TemporaryDirectory(prefix='devops-native-codex-',dir=parent) as directory:
        folder=Path(directory); executable=args.development_cli.resolve() if args.development_cli else cli(folder)
        version=subprocess.run([str(executable),'--version'],capture_output=True,text=True,check=True).stdout.strip()
        if version!='codex-cli '+VERSION: raise RuntimeError('unexpected Codex version: '+version)
        run(executable,folder,False); run(executable,folder,True); run(executable,folder,True,helper=True)
        control=folder/'permission-control'; control.mkdir()
        environment={key:value for key,value in os.environ.items() if key.upper() in {'PATH','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','HOME','USERPROFILE'}}
        environment['CODEX_HOME']=str(control)
        resolved_permissions(executable,control,environment,managed_policy=False)
        if not args.development_cli: managed(executable,folder)
    return 0


if __name__=='__main__': raise SystemExit(main())
