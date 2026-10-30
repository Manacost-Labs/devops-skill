"""Protocol/uncertainty controls plus actual Windows PS5 local journal fixture."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('windows_bridge_fixture',ROOT/'tools/windows_bridge.py')
B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)


def packet():
    now=datetime.now(timezone.utc)
    target={'kind':'windows-jea-v1','server':'dc01.directory.test','port':5986,'configuration_name':'DevopsBound-fixture',
        'ca_file':str(ROOT/'tests/fixture-ca.pem'),'authentication':{'method':'kerberos','cache_file':str(ROOT/'tests/fixture.ccache')},'binding_digest':'sha256:'+'b'*64}
    parameters={'value':'after'}
    return {'schema_version':'2.0','target':target,'parameters':parameters,'context':{'operation_id':'ops-bridge-fixture','task_id':'canary-write','target_id':'fixture-target',
        'call_digest':'sha256:'+'c'*64,'grant_digest':'sha256:'+'d'*64,'registry_digest':'sha256:'+'e'*64,'epoch':'f'*64,
        'not_before':(now-timedelta(minutes=1)).isoformat(),'expires':(now+timedelta(minutes=5)).isoformat(),
        'parameters_digest':B.digest(parameters),'target_digest':B.digest(target)}}


class Transport:
    calls=[]
    fail=False
    def __init__(self,target): self.target=target
    def __enter__(self): return self
    def __exit__(self,*_): pass
    def invoke(self,command,parameters):
        self.calls.append((command,parameters))
        if command=='Get-DevopsEndpointBinding': return {'binding_digest':self.target['binding_digest'],'target_id':'fixture-target'}
        if command=='Get-DevopsBoundTaskStatus': return {'binding_digest':self.target['binding_digest'],'call_digest':parameters['CallDigest'],'status':'outcome_unknown'}
        if self.fail: raise OSError('lost reply after remote write')
        context=B.decode(parameters['ContextJson'])
        return {'binding_digest':self.target['binding_digest'],'call_digest':context['call_digest'],'operation_id':context['operation_id'],'status':'executed','result':{'state':'after'}}


class WindowsBridgeTests(unittest.TestCase):
    def setUp(self): Transport.calls=[];Transport.fail=False

    def test_validated_fixed_command_and_typed_parameters(self):
        result,code=B.run(packet(),transport=Transport)
        self.assertEqual((result,code),({'state':'after'},0))
        self.assertEqual([x[0] for x in Transport.calls],['Get-DevopsEndpointBinding','Invoke-DevopsBoundTask'])
        self.assertEqual(set(Transport.calls[-1][1]),{'BindingDigest','ContextJson','ParametersJson'})

    def test_broker_valid_ninety_minute_window_is_supported(self):
        value=packet();value['context']['expires']=(datetime.now(timezone.utc)+timedelta(minutes=90)).isoformat()
        self.assertEqual(B.run(value,transport=Transport),({'state':'after'},0))

    def test_lost_reply_never_retries_or_claims_no_launch(self):
        Transport.fail=True
        self.assertEqual(B.run(packet(),transport=Transport),(None,4))
        self.assertEqual(len(Transport.calls),2)

    def test_invalid_context_target_or_parameters_never_connect(self):
        for field in ('schema_version','context','parameters','target'):
            value=packet();value[field]=None
            with self.subTest(field=field),self.assertRaises((B.Refused,TypeError,ValueError)):
                B.run(value,transport=Transport)
        value=packet();value['parameters']['command']='Get-ADUser'
        with self.assertRaises(B.Refused):B.run(value,transport=Transport)
        value=packet();value['context']['expires']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        with self.assertRaises(B.Refused):B.run(value,transport=Transport)
        value=packet();value['target']['configuration_name']='Microsoft.PowerShell';value['context']['target_digest']=B.digest(value['target'])
        with self.assertRaises(B.Refused):B.run(value,transport=Transport)
        self.assertFalse(Transport.calls)

    def test_status_is_read_only_and_binds_original_call(self):
        value=packet();value['parameters']={'original_call_digest':'sha256:'+'1'*64};value['context']['parameters_digest']=B.digest(value['parameters'])
        self.assertEqual(B.run(value,'status',Transport),({'state':'outcome_unknown'},0))
        self.assertNotIn('Invoke-DevopsBoundTask',[x[0] for x in Transport.calls])

    def test_duplicate_keys_and_extra_auth_options_are_refused(self):
        with self.assertRaises(B.Refused):B.decode('{"owner":false,"owner":true}')
        for field,value in (('method','ntlm'),('delegate',True),('password','not-a-real-credential')):
            data=packet();data['target']['authentication'][field]=value;data['context']['target_digest']=B.digest(data['target'])
            with self.subTest(field=field),self.assertRaises(B.Refused):B.validate(data)

    def test_constructor_enforces_auth_ca_endpoint_and_transport_guards(self):
        observed={};sent=[]
        class Session:
            trust_env=True
            proxies={'https':'inherited'}
            def send(self,request,**kwargs):sent.append(kwargs);return types.SimpleNamespace(status_code=302)
        class WSMan:
            def __init__(self,server,**kwargs):
                observed.update(server=server,**kwargs)
                self.transport=types.SimpleNamespace(endpoint='https://fixture.test:5986/wsman',_build_session=Session,session=None)
        class Pool:
            def __init__(self,connection,**kwargs):observed['pool']=kwargs
        modules={'pypsrp.powershell':types.SimpleNamespace(PowerShell=object,RunspacePool=Pool),'pypsrp.wsman':types.SimpleNamespace(WSMan=WSMan)}
        with tempfile.TemporaryDirectory() as directory:
            key=Path(directory)/'synthetic.key';key.write_text('synthetic unit key, never used for authentication');key.chmod(0o600)
            value=packet();value['target']['authentication']={'method':'certificate','certificate_pem':str(Path(directory)/'synthetic.pem'),'certificate_key_pem':str(key)}
            with mock.patch.dict(sys.modules,modules),mock.patch.dict(os.environ,{'HTTPS_PROXY':'http://untrusted.invalid','NETRC':'untrusted-file'}),mock.patch.object(B.logging,'disable'):
                client=B.PSRP(value['target'])
                self.assertEqual(observed['auth'],'certificate')
                self.assertTrue(observed['ssl']);self.assertTrue(observed['no_proxy'])
                self.assertEqual(observed['cert_validation'],value['target']['ca_file'])
                self.assertEqual(observed['reconnection_retries'],0)
                self.assertIs(observed['negotiate_delegate'],False)
                self.assertEqual(observed['pool']['configuration_name'],value['target']['configuration_name'])
                session=client.connection.transport.session
                self.assertFalse(session.trust_env);self.assertEqual(session.proxies,{})
                self.assertNotIn('HTTPS_PROXY',os.environ);self.assertNotIn('NETRC',os.environ)
                with self.assertRaises(B.Refused):session.send(types.SimpleNamespace(url='https://foreign.invalid/'))
                self.assertFalse(sent)
                with self.assertRaises(B.Refused):session.send(types.SimpleNamespace(url=client.connection.transport.endpoint))
                self.assertEqual(sent,[{'allow_redirects':False}])

    @unittest.skipUnless(os.name=='nt','Windows PowerShell 5.1 runtime fixture')
    def test_native_windows_journal_replay_and_quarantine(self):
        shell=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
        environment=os.environ.copy()
        environment['PSModulePath']=str(shell.parent/'Modules')+';'+str(Path(os.environ['ProgramFiles'])/'WindowsPowerShell/Modules')
        result=subprocess.run([str(shell),'-NoLogo','-NoProfile','-NonInteractive','-File',str(ROOT/'tests/check_windows_endpoint.ps1'),'-SourceRoot',str(ROOT)],
            capture_output=True,text=True,timeout=60,env=environment)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('WINDOWS_ENDPOINT_FIXTURE_PASS:',result.stdout)


if __name__=='__main__':unittest.main()
