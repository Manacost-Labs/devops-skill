"""Real Linux UID separation, mTLS, snapshots and worker execution; synthetic only.

Invoked only inside the owned, network-isolated CI container, never discovery.
Issuer keys exist in this root test process only. Workers/agents cannot read it.
"""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import signal
import ssl
import subprocess
import sys
import threading
import time
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from broker_fixture import C, EPOCH, HANDLER, registry, grant, call, admission, signed

ROOT = Path('/runtime')
spec = importlib.util.spec_from_file_location('native_service', ROOT/'tools/broker_server.py')
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
spec = importlib.util.spec_from_file_location('native_client', ROOT/'tools/devops_exec.py')
CLIENT = importlib.util.module_from_spec(spec); spec.loader.exec_module(CLIENT)


def identity(folder, name, ca_key=None, ca=None, server=False):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.now(timezone.utc)
    builder = (x509.CertificateBuilder().subject_name(subject).issuer_name(ca.subject if ca else subject)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=ca is None, path_length=0 if ca is None else None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key((ca_key or key).public_key()), critical=False)
        .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=ca is not None,
            data_encipherment=False,key_agreement=False,key_cert_sign=ca is None,crl_sign=ca is None,encipher_only=None,decipher_only=None), critical=True))
    if ca:
        builder = builder.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH if server else ExtendedKeyUsageOID.CLIENT_AUTH]),critical=False)
        if server:
            builder=builder.add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]),critical=False)
    cert=builder.sign(ca_key or key,hashes.SHA256())
    (folder/(name+'.pem')).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (folder/(name+'.key')).write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    (folder/(name+'.key')).chmod(0o600)
    return key, cert


class NativeBroker(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.folder=Path(tempfile.mkdtemp(dir='/fixture'))
        self.folder.chmod(0o711)
        for name in ('protected','bundle','workers','target','agent'):
            (self.folder/name).mkdir(mode=0o700)
        self.protected=self.folder/'protected'; self.state=self.protected/'state'; self.state.mkdir(mode=0o700)
        (self.folder/'workers').chmod(0o711)
        os.chown(self.folder/'target',1001,1001)
        (self.folder/'target/value').write_text('before'); os.chown(self.folder/'target/value',1001,1001)
        os.chown(self.folder/'agent',65534,65534)
        ca_key,ca=identity(self.protected,'ca')
        identity(self.protected,'server',ca_key,ca,True)
        _,cert=identity(self.folder/'agent','client',ca_key,ca)
        for path in (self.folder/'agent').iterdir(): os.chown(path,65534,65534)
        (self.folder/'agent/ca.pem').write_bytes(ca.public_bytes(serialization.Encoding.PEM))
        self.subject=C.digest(cert.public_bytes(serialization.Encoding.DER))
        self.registry,self.keys=registry(subject=self.subject)
        self.registry['targets']['fixture-target']['resource']={'path':str(self.folder/'target/value'),'private_state':str(self.state/'service.json')}
        for name,mode in (('probe-task','probe'),('failure-task','fail'),('slow-task','slow'),('ignore-task','ignore'),('invalid-task','invalid'),('snapshot-task','snapshot')):
            task=copy.deepcopy(self.registry['tasks']['configure-task' if mode in ('fail','slow','ignore','invalid') else 'inspect-task'])
            task.update(argv=['-I','@bundle/handler.py@',mode],parameters={})
            if mode in ('ignore','slow'): task['timeout_seconds']=1
            self.registry['tasks'][name]=task
        self.registry['targets']['fixture-target']['resource']['padding']='x'*12000
        self.registry_path=self.protected/'registry.json'; self.registry_path.write_bytes(C.canonical(self.registry))
        (self.folder/'bundle/handler.py').write_bytes(HANDLER)
        self.broker=S.Broker(self.registry_path,self.folder/'bundle',self.state,self.folder/'workers')
        self.addCleanup(self.broker.close)
        self.grant=grant(self.registry,self.keys)
        from http.server import ThreadingHTTPServer
        self.server=ThreadingHTTPServer(('127.0.0.1',0),S.handler(self.broker)); self.server.daemon_threads=True
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(self.protected/'server.pem'),str(self.protected/'server.key'))
        context.load_verify_locations(str(self.protected/'ca.pem')); context.verify_mode=ssl.CERT_REQUIRED
        self.server.socket=context.wrap_socket(self.server.socket,server_side=True)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.addCleanup(self.stop_server)
        self.profile={'url':'https://localhost:'+str(self.server.server_port),'ca_file':str(self.folder/'agent/ca.pem'),
            'client_certificate':str(self.folder/'agent/client.pem'),'client_private_key':str(self.folder/'agent/client.key'),'timeout_seconds':10}

    def stop_server(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)

    def packet(self,task='configure-task',operation='ops-native-fixture',authority=None,parameters=None):
        return {'call':call(task,operation=operation,parameters=parameters),'grant':authority or self.grant,'admission':None}

    def request(self,packet,route='execute'):
        return CLIENT.call_broker(self.profile,packet,route)

    def agent(self,code,*arguments):
        return subprocess.run([sys.executable,'-I','-c',code,*map(str,arguments)],user=65534,group=65534,extra_groups=[],
            cwd=self.folder/'agent',env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(self.folder/'agent')},capture_output=True,text=True,timeout=10)

    def test_real_agent_cannot_read_or_replace_broker_state_or_target_without_hooks(self):
        for path in (self.state/'service.json',self.registry_path,self.folder/'target/value',self.protected/'server.key'):
            for method in ('read_text','write_text'):
                result=self.agent("import pathlib,sys; p=pathlib.Path(sys.argv[1]); getattr(p,sys.argv[2])(*(['forged'] if sys.argv[2]=='write_text' else []))",path,method)
                self.assertNotEqual(result.returncode,0,path)
        self.assertEqual((self.folder/'target/value').read_text(),'before')

    def test_real_tls_reusable_grant_and_idempotent_receipt(self):
        for index in range(2):
            packet=self.packet(operation='ops-native-reuse-'+str(index))
            result=self.request(packet); self.assertEqual(result['status'],'executed'); self.assertTrue(result['result_valid'])
            self.assertTrue(self.request(packet)['replayed'])
        self.assertEqual((self.folder/'target/value').read_text(),'after')

    def test_real_unprivileged_client_has_only_typed_broker_authority(self):
        profile=self.folder/'agent/profile.json'; profile.write_bytes(C.canonical(self.profile)); profile.chmod(0o444)
        packet=self.folder/'agent/packet.json'; packet.write_bytes(C.canonical(self.packet())); packet.chmod(0o444)
        code="import importlib.util,json,sys; s=importlib.util.spec_from_file_location('client','/runtime/tools/devops_exec.py'); m=importlib.util.module_from_spec(s);s.loader.exec_module(m); print(json.dumps(m.call_broker(json.load(open(sys.argv[1])),json.load(open(sys.argv[2])),'execute')))"
        result=self.agent(code,profile,packet); self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'executed')
        forged=self.packet(operation='ops-native-forged'); forged['call']['risk']='R0'; packet.write_bytes(C.canonical(forged))
        result=self.agent(code,profile,packet); self.assertNotEqual(result.returncode,0)

    def test_worker_cannot_read_supervisor_state_or_modify_snapshot(self):
        self.assertEqual(self.request(self.packet('probe-task'))['result'],{'state':'denied'})
        self.assertEqual(self.request(self.packet('snapshot-task',operation='ops-snapshot-permission'))['result'],{'state':'denied'})

    def test_bundle_replacement_after_snapshot_cannot_change_executed_code(self):
        original=self.broker.snapshot
        def snapshot(*args):
            result=original(*args)
            (self.folder/'bundle/handler.py').write_bytes(b"raise SystemExit(99)")
            return result
        self.broker.snapshot=snapshot
        self.assertEqual(self.request(self.packet())['result'],{'state':'after'})

    def test_bundle_replacement_before_snapshot_refuses_without_mutation(self):
        (self.folder/'bundle/handler.py').write_bytes(b"raise SystemExit(99)")
        with self.assertRaises(CLIENT.C.Denied): self.request(self.packet())
        self.assertEqual((self.folder/'target/value').read_text(),'before')

    def test_safe_during_real_running_worker_invalidates_every_old_grant(self):
        outcome=[]
        thread=threading.Thread(target=lambda:outcome.append(self.request(self.packet('slow-task')))); thread.start()
        deadline=time.monotonic()+5
        while not list((self.state/'journal').glob('*.json')) and time.monotonic()<deadline: time.sleep(.01)
        start=time.monotonic(); restricted=self.request({'mode':'safe','grant':None},'restrict')
        self.assertLess(time.monotonic()-start,.8)
        thread.join(5); self.assertFalse(thread.is_alive()); self.assertEqual(outcome[0]['status'],'outcome_unknown')
        for authority in (self.grant,grant(self.registry,self.keys,identifier='grant-native-second')):
            with self.assertRaises(CLIENT.C.Denied): self.request(self.packet(authority=authority,operation='ops-native-old-grant'))
        self.assertEqual(restricted['mode'],'safe')

    def test_nonreader_stdin_timeout_is_bounded_and_freezes_mutations(self):
        start=time.monotonic(); result=self.request(self.packet('ignore-task'))
        self.assertLess(time.monotonic()-start,5); self.assertEqual(result['status'],'outcome_unknown')
        with self.assertRaises(CLIENT.C.Denied): self.request(self.packet(operation='ops-native-new-retry'))

    def test_failure_and_invalid_result_keep_target_frozen(self):
        result=self.request(self.packet('invalid-task'))
        self.assertEqual(result['status'],'outcome_unknown'); self.assertFalse(result['result_valid'])
        with self.assertRaises(CLIENT.C.Denied): self.request(self.packet(operation='ops-native-after-invalid'))

    def test_tls_without_client_identity_is_refused(self):
        import http.client
        context=ssl.create_default_context(cafile=self.profile['ca_file'])
        connection=http.client.HTTPSConnection('localhost',self.server.server_port,context=context,timeout=3)
        try:
            with self.assertRaises((OSError,http.client.HTTPException)):
                connection.request('POST','/v1/execute',body=C.canonical(self.packet()))
                connection.getresponse().read()
        finally: connection.close()

    def test_actual_service_main_checks_deployment_and_identity_separation(self):
        state=self.protected/'main-state'; state.mkdir(mode=0o700)
        workers=self.folder/'main-workers'; workers.mkdir(mode=0o711)
        config={'registry':str(self.registry_path),'bundle_dir':str(self.folder/'bundle'),
            'state_dir':str(state),'worker_dir':str(workers),'host':'127.0.0.1','port':0,
            'certificate':str(self.protected/'server.pem'),'private_key':str(self.protected/'server.key'),
            'client_ca':str(self.protected/'ca.pem'),'agent_uids':[65534],'agent_gids':[65534]}
        path=self.protected/'main-config.json'; path.write_bytes(C.canonical(config))
        process=subprocess.Popen([sys.executable,'-I',str(ROOT/'tools/broker_server.py'),'--config',str(path)],
            env={'PATH':'/usr/local/bin:/usr/bin:/bin'},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            ready=[]
            reader=threading.Thread(target=lambda:ready.append(process.stdout.readline()),daemon=True); reader.start(); reader.join(8)
            self.assertEqual(ready,['READY: protected task broker\n'])
        finally:
            process.terminate(); stdout,stderr=process.communicate(timeout=8)
        self.assertEqual(process.returncode,0,stderr)
        config['agent_gids']=[1001]; path.write_bytes(C.canonical(config))
        refused=subprocess.run([sys.executable,'-I',str(ROOT/'tools/broker_server.py'),'--config',str(path)],
            env={'PATH':'/usr/local/bin:/usr/bin:/bin'},capture_output=True,text=True,timeout=8)
        self.assertEqual(refused.returncode,3)


if __name__=='__main__':
    if os.name!='posix' or os.geteuid()!=0 or os.environ.get('DEVOPS_OWNED_BROKER_FIXTURE')!='1':
        raise SystemExit('owned isolated Linux fixture required')
    unittest.main(verbosity=2)
