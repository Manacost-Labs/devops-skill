"""Owned Windows CI endpoint interoperability. No domain or real credentials."""
import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import ipaddress
import json
from pathlib import Path
import socket
import ssl
import sys
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native_windows_bridge',ROOT/'tools/windows_bridge.py')
B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)


def certificates(folder, username):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID, ObjectIdentifier
    ca_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    ca_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'DevopsJEA-fixture-'+username)])
    now=datetime.now(timezone.utc)
    ca=(x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),critical=False)
        .add_extension(x509.KeyUsage(True,False,False,False,False,True,True,False,False),critical=True)
        .sign(ca_key,hashes.SHA256()))
    (folder/'ca.pem').write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    for name,server in (('server',True),('client',False)):
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        subject='localhost' if server else username
        builder=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,subject)]))
            .issuer_name(ca.subject if server else x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,subject)]))
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key((ca_key if server else key).public_key()),critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH if server else ExtendedKeyUsageOID.CLIENT_AUTH]),critical=False))
        if server:builder=builder.add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
        else:
            upn=(username+'@localhost').encode()
            builder=builder.add_extension(x509.SubjectAlternativeName([x509.OtherName(ObjectIdentifier('1.3.6.1.4.1.311.20.2.3'),bytes((12,len(upn)))+upn)]),critical=False)
        # An independently trusted self-signed client matches the maintainer's
        # documented local-account fixture. A synthetic CA-issued client with
        # no CRL cannot prove Windows' default revocation/trust acceptance.
        cert=builder.sign(ca_key if server else key,hashes.SHA256())
        (folder/(name+'.pem')).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        (folder/(name+'.key')).write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        (folder/(name+'.key')).chmod(0o600)
        if server:(folder/(name+'.pfx')).write_bytes(pkcs12.serialize_key_and_certificates(name.encode(),key,cert,None,serialization.NoEncryption()))


def packet(resource, task='canary-write', value='after', operation='ops-native-windows'):
    now=datetime.now(timezone.utc);parameters={'value':value}
    return {'schema_version':'2.0','target':resource,'parameters':parameters,'context':{'operation_id':operation,'task_id':task,'target_id':'fixture-target',
        'call_digest':'sha256:'+__import__('hashlib').sha256(operation.encode()).hexdigest(),'grant_digest':'sha256:'+'d'*64,'registry_digest':'sha256:'+'e'*64,
        'epoch':'f'*64,'not_before':(now-timedelta(minutes=1)).isoformat(),'expires':(now+timedelta(minutes=10)).isoformat(),
        'parameters_digest':B.digest(parameters),'target_digest':B.digest(resource)}}


def exercise(folder):
    resource=B.decode((folder/'target.json').read_bytes())
    target=folder/'state/value.txt'
    original=packet(resource)
    result,code=B.run(original)
    if code!=0:
        try:
            with B.PSRP(resource) as client:client.invoke('Get-DevopsEndpointBinding',{})
        except Exception as error:print('Synthetic fixture diagnostic:',type(error).__name__,str(error)[:1500])
    assert code==0 and result=={'state':'after'},('positive controlled task failed',code)
    assert target.read_text()=='after'
    target.write_text('external-change')
    assert B.run(original)==({'state':'after'},0)
    assert target.read_text()=='external-change','replay dispatched a second write'
    # An invalid DNS name is resolved to the *same reachable IPv4 listener*
    # only in this negative fixture. A connection failure cannot satisfy a
    # claimed certificate/hostname denial; require requests' actual SSLError.
    from requests.exceptions import SSLError
    original_lookup=socket.getaddrinfo
    def fixture_lookup(host,*args,**kwargs):
        return original_lookup('127.0.0.1' if host=='wrong-fixture.invalid' else host,*args,**kwargs)
    tls_failures=[]
    class BadTLS(B.PSRP):
        def __enter__(self):
            try:return super().__enter__()
            except SSLError as error:
                # Requests/urllib3 nest the OpenSSL verification exception.
                # Protocol alerts, SNI rejection and EOF are not proof of
                # certificate validation, even though they use SSLError too.
                pending=[error];seen=set();verified=[]
                while pending and len(seen)<32:
                    current=pending.pop()
                    if not isinstance(current,BaseException) or id(current) in seen:continue
                    seen.add(id(current))
                    if isinstance(current,ssl.SSLCertVerificationError):verified.append(current.verify_code)
                    pending.extend([getattr(current,'reason',None),current.__cause__,current.__context__])
                    pending.extend(item for item in current.args if isinstance(item,BaseException))
                tls_failures.append(verified)
                raise
    for field,bad_value in (('ca_file',str(folder/'client.pem')),('server','wrong-fixture.invalid')):
        altered=dict(resource);altered[field]=bad_value
        refused=packet(altered,operation='ops-native-tls-'+field.replace('_','-'))
        count=len(tls_failures)
        with mock.patch.object(socket,'getaddrinfo',fixture_lookup):
            assert B.run(refused,transport=BadTLS)[1]==3,'TLS failure was not rejected before task dispatch'
        assert len(tls_failures)==count+1 and tls_failures[-1],'missing actual certificate validation failure'
        if field=='server':assert 62 in tls_failures[-1],'missing actual DNS hostname mismatch'
        assert target.read_text()=='external-change'
    # The same certificate-mapped nonadmin connector must not receive a raw
    # filesystem cmdlet or a code evaluation primitive in this actual endpoint.
    denied_commands=(('Get-Item',{'LiteralPath':str(target)}),
        ('Invoke-Expression',{'Command':'Get-DevopsEndpointBinding'}),
        ('New-PSSession',{'ComputerName':'localhost','UseSSL':True,'Port':resource['port'],'ConfigurationName':resource['configuration_name']}))
    for command,parameters in denied_commands:
        with B.PSRP(resource) as client:
            pipeline=client.PowerShell(client.pool);pipeline.add_cmdlet(command)
            for name,item in parameters.items():pipeline.add_parameter(name,item)
            try:pipeline.invoke()
            except Exception:pass
            # Binding, authentication and transport failures do not prove a
            # policy denial. Require the actual hidden-command error record.
            denied=any(getattr(error,'fq_error','').split(',')[0]=='CommandNotFoundException' for error in pipeline.streams.error)
            assert denied,'missing exact command-visibility denial for '+command
    # No access to the default unrestricted PS endpoint or Windows shell.
    from pypsrp.powershell import RunspacePool
    from pypsrp.shell import WinRS
    from pypsrp.exceptions import AuthenticationError,WSManFaultError,WinRMTransportError
    for shell in ('default','winrs'):
        client=B.PSRP(resource)
        denied=False
        try:
            pool=RunspacePool(client.connection) if shell=='default' else WinRS(client.connection)
            pool.open()
        except AuthenticationError:denied=True
        except WSManFaultError as error:denied=error.code in (5,0x80070005)
        except WinRMTransportError as error:denied=error.code in (401,403)
        finally:client.connection.close()
        assert denied,'unrestricted remote entry point accepted'
    bad=packet(resource,operation='ops-native-bad-value');bad['parameters']['value']='unregistered';bad['context']['parameters_digest']=B.digest(bad['parameters'])
    assert B.run(bad)[1]!=0 and target.read_text()=='external-change'
    # Lose the reply after an actual remote task, then reconcile/read the
    # original receipt; no automatic mutation retry is attempted by the bridge.
    class LostReply(B.PSRP):
        def invoke(self,command,parameters):
            result=super().invoke(command,parameters)
            if command=='Invoke-DevopsBoundTask':raise OSError('synthetic dropped reply')
            return result
    lost=packet(resource,value='before',operation='ops-native-lost-reply')
    assert B.run(lost,transport=LostReply)==(None,4)
    assert target.read_text()=='before'
    status=packet(resource,operation='ops-native-read-receipt');status['parameters']={'original_call_digest':lost['context']['call_digest']};status['context']['parameters_digest']=B.digest(status['parameters'])
    assert B.run(status,'status')==({'state':'executed'},0)
    failure=packet(resource,value='fail',operation='ops-native-task-failure')
    assert B.run(failure)[1]==4 and target.read_text()=='fail'
    assert B.run(packet(resource,operation='ops-native-new-retry'))[1]==4
    assert target.read_text()=='fail','new operation bypassed remote quarantine'
    print('NATIVE_WINDOWS_JEA_PASS: actual HTTPS certificate connector, JEA allow/deny, replay, lost reply, quarantine; AD not_run')


def diagnose_tls(folder):
    resource=B.decode((folder/'target.json').read_bytes())
    print('TLS_DIAGNOSTIC resolver',socket.getaddrinfo('localhost',resource['port'],type=socket.SOCK_STREAM))
    for version in (ssl.TLSVersion.TLSv1_3,ssl.TLSVersion.TLSv1_2):
        stage='context'
        try:
            context=ssl.create_default_context(cafile=resource['ca_file'])
            context.check_hostname=True;context.verify_mode=ssl.CERT_REQUIRED
            context.minimum_version=version;context.maximum_version=version
            context.post_handshake_auth=True;context.set_alpn_protocols(['http/1.1'])
            context.load_cert_chain(str(folder/'client.pem'),str(folder/'client.key'))
            stage='connect'
            with socket.create_connection(('127.0.0.1',resource['port']),timeout=5) as connection:
                stage='handshake'
                with context.wrap_socket(connection,server_hostname='localhost') as channel:
                    print('TLS_DIAGNOSTIC',version.name,'handshake',channel.version(),channel.cipher()[0])
                    stage='send'
                    # GET can be rejected by HTTP.sys before client-certificate
                    # authentication. A static Identify POST tests that stage
                    # without creating a shell or dispatching any task.
                    body=('''<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing" xmlns:w="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"><s:Header><a:To>https://localhost:%s/wsman</a:To><w:ResourceURI>http://schemas.microsoft.com/powershell/%s</w:ResourceURI><a:ReplyTo><a:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</a:Address></a:ReplyTo><a:Action>http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity/Identify</a:Action><a:MessageID>uuid:00000000-0000-0000-0000-000000000001</a:MessageID></s:Header><s:Body><Identify xmlns="http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd"/></s:Body></s:Envelope>'''%(resource['port'],resource['configuration_name'])).encode('ascii')
                    headers=('POST /wsman HTTP/1.1\r\nHost: localhost:%s\r\nAuthorization: http://schemas.dmtf.org/wbem/wsman/1/wsman/secprofile/https/mutual\r\nContent-Type: application/soap+xml;charset=UTF-8\r\nContent-Length: %s\r\nConnection: close\r\n\r\n'%(resource['port'],len(body))).encode('ascii')
                    channel.sendall(headers+body)
                    stage='read'
                    line=channel.recv(2048).split(b'\r\n',1)[0].decode('ascii','replace')
                    print('TLS_DIAGNOSTIC',version.name,'status',line[:160])
        except Exception as error:print('TLS_DIAGNOSTIC',version.name,'failed_stage',stage,'error',type(error).__name__,str(error)[:300])


def probe_binding(folder):
    resource=B.decode((folder/'target.json').read_bytes())
    try:
        with B.PSRP(resource) as client:binding=client.invoke('Get-DevopsEndpointBinding',{})
        assert binding=={'target_id':'fixture-target','binding_digest':resource['binding_digest']}
        print('MAPPING_BINDING_PROBE authenticated_named_endpoint')
        return 0
    except Exception as error:
        print('MAPPING_BINDING_PROBE refused',type(error).__name__,str(error)[:500])
        return 3


def main():
    parser=argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('action',choices=('certificates','digest','diagnose-tls','probe-binding','exercise'))
    parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--username')
    args=parser.parse_args()
    if args.action=='certificates':certificates(args.folder,args.username)
    elif args.action=='digest':print(B.digest(B.decode((args.folder/'target.json').read_bytes())))
    elif args.action=='diagnose-tls':diagnose_tls(args.folder)
    elif args.action=='probe-binding':return probe_binding(args.folder)
    else:exercise(args.folder)


if __name__=='__main__':raise SystemExit(main())
