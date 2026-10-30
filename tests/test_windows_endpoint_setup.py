"""Unsigned bundle preparation, static data quoting and owner dry-run refusal."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('windows_endpoint_preparation',ROOT/'tools/prepare_windows_endpoint.py')
P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)


class EndpointSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='endpoint-setup-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'source.ps1';self.source.write_text('param($Parameters,$Context)\n@{state="after"}\n')
        tag=uuid.uuid4().hex
        self.plan={'schema_version':'1.0','endpoint_name':'DevopsBound-fixture','connector':'DIRECTORY\\fixtureconnector','run_as_gmsa':'DIRECTORY\\fixtureworker$',
            'module_root':str(Path(os.environ.get('ProgramFiles','C:/Program Files'))/('DevopsBound-'+tag)),
            'state_root':str(Path(os.environ.get('ProgramData','C:/ProgramData'))/('DevopsBound-'+tag)),'target_id':'fixture-target',
            'target_resource':{'kind':'windows-jea-v1','server':'dc01.directory.test','port':5986,'configuration_name':'DevopsBound-fixture',
                'ca_file':'/protected/ca.pem','authentication':{'method':'kerberos','cache_file':'/protected/connector.ccache'}},
            'tasks':{'canary-write':{'source_file':str(self.source),'parameters':{'value':{'enum':['before','after']}},'result_schema':{'state':{'enum':['after']}}}}}
        # Path on a non-Windows test runner must still describe the Windows host.
        if os.name!='nt':
            self.plan['module_root']='C:/Program Files/DevopsBound-'+tag
            self.plan['state_root']='C:/ProgramData/DevopsBound-'+tag

    def test_bundle_pins_exact_bytes_and_never_contains_active_authority(self):
        out=self.root/'review';digest=P.prepare(self.plan,out)
        manifest=json.loads((out/'owner-manifest.json').read_text())
        self.assertEqual(hashlib.sha256((out/'owner-manifest.json').read_bytes()).hexdigest(),digest)
        for name,binding in manifest['files'].items():self.assertEqual(hashlib.sha256((out/name).read_bytes()).hexdigest(),binding)
        resource=json.loads((out/'target-resource.review.json').read_text())
        self.assertRegex(resource['binding_digest'],r'^sha256:[a-f0-9]{64}$')
        self.assertIn('__OWNER_CURRENT_BOOT__',(out/'endpoint.psd1').read_text())
        self.assertFalse(any(x.suffix in {'.key','.pfx','.pem'} for x in out.iterdir()))
        with self.assertRaises(FileExistsError):P.prepare(self.plan,out)

    def test_unsafe_auth_source_schema_and_plan_expansion_refuse(self):
        for change in ('auth','source','schema','field'):
            plan=json.loads(json.dumps(self.plan))
            if change=='auth':plan['target_resource']['authentication']={'method':'ntlm','password':'synthetic-invalid'}
            if change=='source':plan['tasks']['canary-write']['source_file']='../unreviewed.ps1'
            if change=='schema':plan['tasks']['canary-write']['parameters']={'command':{'type':'string'}}
            if change=='field':plan['owner_run']=True
            with self.subTest(change=change),self.assertRaises((P.B.Refused,KeyError)):
                P.prepare(plan,self.root/change)
            self.assertFalse((self.root/change).exists())

    @unittest.skipUnless(os.name=='nt','Windows owner-loader dry-run')
    def test_native_owner_loader_binds_manifest_and_payload_tamper(self):
        out=self.root/'review';digest=P.prepare(self.plan,out)
        shell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        environment=os.environ.copy();environment['PSModulePath']=str(shell.parent/'Modules')+';'+str(Path(os.environ['ProgramFiles'])/'WindowsPowerShell/Modules')
        command=[str(shell),'-NoProfile','-NonInteractive','-File',str(ROOT/'tools/install_windows_endpoint.ps1'),'-Bundle',str(out),'-ExpectedManifestSHA256',digest]
        result=subprocess.run(command,capture_output=True,text=True,env=environment,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('prepared_not_installed',result.stdout)
        (out/'canary-write.ps1').write_text('throw "tampered fixture"')
        result=subprocess.run(command,capture_output=True,text=True,env=environment,timeout=30)
        self.assertEqual(result.returncode,3,result.stdout+result.stderr)
        self.assertFalse(Path(self.plan['module_root']).exists());self.assertFalse(Path(self.plan['state_root']).exists())

    @unittest.skipUnless(os.name=='nt','Windows PowerShell 5.1 static session preparation')
    def test_native_session_generation_preserves_unicode_and_module_types(self):
        self.plan['tasks']['canary-write']['parameters']['value']['enum'].append('проверка')
        out=self.root/'unicode';P.prepare(self.plan,out)
        shell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        environment=os.environ.copy();environment['PSModulePath']=str(shell.parent/'Modules')+';'+str(Path(os.environ['ProgramFiles'])/'WindowsPowerShell/Modules')
        result=subprocess.run([str(shell),'-NoProfile','-NonInteractive','-File',str(ROOT/'tests/check_windows_endpoint_setup.ps1'),'-Bundle',str(out),'-ExpectedEnum','проверка'],
            capture_output=True,text=True,env=environment,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('WINDOWS_ENDPOINT_STATIC_SETUP_PASS',result.stdout)


if __name__=='__main__':unittest.main()
