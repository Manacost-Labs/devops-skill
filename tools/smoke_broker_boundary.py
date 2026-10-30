#!/usr/bin/env python3
"""Run actual broker workers and agent UIDs inside an owned offline CI container."""
import importlib.util
from pathlib import Path
import re
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from container_fixture import DockerFixture, IMAGE, OWNER


def main():
    fixture=DockerFixture()
    try:
        context=fixture.folder/'build'; context.mkdir()
        spec=importlib.util.spec_from_file_location('broker_fixture_release',ROOT/'tools/build_release.py')
        release=importlib.util.module_from_spec(spec); spec.loader.exec_module(release)
        import json
        for path in release.files_for_release(json.loads((ROOT/'catalog.json').read_text())):
            destination=context/'runtime'/path.relative_to(ROOT); destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(release.safe_read(path))
        for name in ('native_broker_cases.py','broker_fixture.py'):
            (context/name).write_bytes((ROOT/'tests'/name).read_bytes())
        # Fixture helper computes its source root; /tests sits alongside /runtime.
        text=(context/'broker_fixture.py').read_text().replace('ROOT = Path(__file__).resolve().parents[1]',"ROOT = Path('/runtime')")
        (context/'broker_fixture.py').write_text(text)
        (context/'Dockerfile').write_text('FROM '+IMAGE+'\nCOPY runtime /runtime\nRUN python -m pip install --isolated --disable-pip-version-check --no-input --require-hashes -r /runtime/requirements.txt\nCOPY native_broker_cases.py broker_fixture.py /tests/\n')
        tag=fixture.tag+'-broker'
        fixture.docker('build','--tag',tag,'--label',OWNER+'='+fixture.tag,str(context),timeout=300)
        fixture.image_tag=tag; fixture.image_id=fixture.inspect('image',tag)['Id']
        identity=fixture.docker('create','--name',fixture.tag+'-broker','--label',OWNER+'='+fixture.tag,
            '--network','none','--read-only','--tmpfs','/fixture:rw,nosuid,nodev,size=64m,mode=0755',
            '--memory','256m','--memory-swap','256m','--cpus','2','--pids-limit','96','--cap-drop','ALL',
            '--cap-add','SETUID','--cap-add','SETGID','--cap-add','CHOWN','--cap-add','KILL',
            '--cap-add','DAC_OVERRIDE',
            '--security-opt','no-new-privileges','--env','DEVOPS_OWNED_BROKER_FIXTURE=1',
            tag,'python','-B','/tests/native_broker_cases.py').stdout.strip()
        if not re.fullmatch('[0-9a-f]{64}',identity): raise RuntimeError('full owned container identity required')
        fixture.containers.append(identity); fixture.owned_container(identity)
        fixture.docker('start',identity)
        result=fixture.docker('wait',identity,timeout=180)
        logs=fixture.docker('logs',identity).stdout
        # Docker preserves unittest stderr separately.
        details=fixture.docker('logs',identity)
        print(details.stdout); print(details.stderr)
        if int(result.stdout.strip())!=0: raise RuntimeError('native broker isolation checks failed')
    finally: fixture.cleanup()
    return 0


if __name__=='__main__': raise SystemExit(main())
