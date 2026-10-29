from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = "a" * 64
UID = "87654321-1234-4321-9876-123456789abc"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


D = load("docker_snapshot", "docker-operations/scripts/inspect-container-state.py")
K = load("pod_snapshot", "kubernetes-operations/scripts/inspect-pod-state.py")


def docker():
    return [{"Id": IDENTITY, "Image": "sha256:" + "b"*64, "RestartCount": 2,
             "State": {"Status": "exited", "ExitCode": 137, "OOMKilled": False, "Running": False,
                       "Error": "sensitive-marker", "Health": {"Status": "unhealthy", "Log": ["sensitive-marker"]}},
             "HostConfig": {"Memory": 67108864, "MemorySwap": -1, "PidsLimit": 0, "NanoCpus": 1000000000},
             "Mounts": [{"Type": "volume", "RW": True, "Source": "sensitive-marker"}],
             "NetworkSettings": {"Networks": {"sensitive-marker": {"IPAddress": "sensitive-marker"}}},
             "Config": {"Env": ["sensitive-marker"], "Labels": {"instruction": "sensitive-marker"}}}]


def pod():
    return {"apiVersion": "v1", "kind": "Pod", "metadata": {"namespace": "fixture", "name": "api", "uid": UID,
            "annotations": {"instruction": "sensitive-marker"}},
            "spec": {"resources": {"limits": {"memory": "128Mi"}},
                     "containers": [{"name": "api", "resources": {"requests": {"cpu": "100m"}, "limits": {"memory": "64Mi"}},
                                     "env": [{"name": "TOKEN", "value": "sensitive-marker"}]}]},
            "status": {"phase": "Running", "message": "sensitive-marker",
                       "conditions": [{"type": "Ready", "status": "False", "message": "sensitive-marker"}],
                       "containerStatuses": [{"name": "api", "ready": False, "restartCount": 4,
                         "state": {"waiting": {"reason": "CrashLoopBackOff", "message": "sensitive-marker"}},
                         "lastState": {"terminated": {"reason": "OOMKilled", "exitCode": 137, "signal": 9, "message": "sensitive-marker"}}}]}}


class SnapshotInputTests(unittest.TestCase):
    def test_bounded_strict_json_and_generic_cli_errors(self):
        for module, relative, args in [(D, "docker-operations/scripts/inspect-container-state.py", ["--id", IDENTITY]),
                                      (K, "kubernetes-operations/scripts/inspect-pod-state.py", ["--namespace", "fixture", "--name", "api", "--uid", UID])]:
            for raw in [b"", b'{"secret":"sensitive-marker",', b'{"x":1,"x":2}', b'{"x":NaN}', b"x"*(module.MAX_BYTES+1), b"\xff", b"["*1500+b"]"*1500]:
                with self.subTest(module=module.__name__, raw_length=len(raw)):
                    result = subprocess.run([sys.executable, str(ROOT/relative), *args], input=raw, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    report = json.loads(result.stdout)
                    self.assertEqual(report["status"], "unknown")
                    self.assertNotIn(b"sensitive-marker", result.stdout+result.stderr)
            class LimitedRead:
                def read(self, count):
                    self.count = count
                    return b"x"*count
            stream = LimitedRead()
            with self.assertRaises(ValueError): module.read_snapshot(stream)
            self.assertEqual(stream.count, module.MAX_BYTES+1)


class DockerSnapshotTests(unittest.TestCase):
    def test_sigkill_is_not_an_oom_diagnosis_and_sensitive_fields_omitted(self):
        result = D.summarize(docker(), IDENTITY)
        self.assertEqual(result["exit_code"], 137)
        self.assertFalse(result["oom_killed"])
        self.assertEqual(result["oom_cause"], "not_determined")
        self.assertEqual(result["verification"], "not_assessed")
        self.assertEqual(result["limits"]["memory_swap_setting_bytes"], -1)
        self.assertNotIn("sensitive-marker", json.dumps(result))
        data = docker(); data[0]["State"]["OOMKilled"] = True
        self.assertTrue(D.summarize(data, IDENTITY)["oom_killed"])

    def test_absent_metadata_stays_unknown_not_zero(self):
        result = D.summarize([{"Id": IDENTITY}], IDENTITY)
        for key in ("exit_code", "restart_count", "oom_killed", "mount_count", "network_count", "running"):
            self.assertIsNone(result[key])
        self.assertEqual(result["completeness"], "partial")
        self.assertIsNone(result["limits"]["memory_bytes"])

    def test_identity_types_and_ambiguity_rejected(self):
        cases = [[], docker()*2, docker()[0]]
        for key, value in [("Id", "b"*64), ("State", []), ("Mounts", {}), ("Image", "sensitive-marker"), ("RestartCount", True)]:
            data = docker(); data[0][key] = value; cases.append(data)
        for key, value in [("OOMKilled", "false"), ("ExitCode", True), ("Running", 0), ("Error", [])]:
            data = docker(); data[0]["State"][key] = value; cases.append(data)
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValueError): D.summarize(data, IDENTITY)

    def test_mount_bound_and_unknown_enum_redaction(self):
        data = docker(); data[0]["Mounts"] *= 33
        data[0]["State"]["Health"]["Status"] = "sensitive-marker"
        result = D.summarize(data, IDENTITY)
        self.assertTrue(result["mounts_truncated"])
        self.assertEqual(len(result["mounts"]), 32)
        self.assertNotIn("sensitive-marker", json.dumps(result))


class PodSnapshotTests(unittest.TestCase):
    def test_previous_oom_and_current_backoff_are_separate(self):
        result = K.summarize(pod(), "fixture", "api", UID)
        row = result["containers"]["containers"][0]
        self.assertEqual((row["current"]["kind"], row["current"]["reason"]), ("waiting", "CrashLoopBackOff"))
        self.assertEqual((row["previous"]["reason"], row["previous"]["exit_code"]), ("OOMKilled", 137))
        self.assertEqual(row["resources"]["limits"]["memory"], "64Mi")
        self.assertEqual(result["pod_resources"]["limits"]["memory"], "128Mi")
        self.assertFalse(row["ready"])
        self.assertEqual(result["verification"], "not_assessed")
        self.assertNotIn("sensitive-marker", json.dumps(result))

    def test_init_and_ephemeral_states_and_unknown_fields(self):
        data = pod()
        for spec_key, status_key in [("initContainers", "initContainerStatuses"), ("ephemeralContainers", "ephemeralContainerStatuses")]:
            data["spec"][spec_key] = [{"name": "helper", "restartPolicy": "Always"}]
            data["status"][status_key] = [{"name": "helper", "state": {"running": {}}, "lastState": {}, "restartCount": 0, "ready": True}]
        result = K.summarize(data, "fixture", "api", UID)
        self.assertEqual(result["containers"]["initContainers"][0]["init_restart_policy"], "Always")
        self.assertIsNone(result["containers"]["ephemeralContainers"][0]["previous"]["reason"])
        del data["status"]["containerStatuses"]
        result = K.summarize(data, "fixture", "api", UID)
        self.assertIsNone(result["containers"]["containers"])
        self.assertIn("containerStatuses", result["unknown_fields"])
        self.assertEqual(result["completeness"], "partial")

    def test_uid_scope_kind_and_malformed_states_rejected(self):
        cases = []
        for key, value in [("uid", "12345678-1234-4321-9876-123456789abc"), ("namespace", "other"), ("name", "other")]:
            data = pod(); data["metadata"][key] = value; cases.append(data)
        for key, value in [("apiVersion", "v2"), ("kind", "PodList"), ("spec", []), ("status", [])]:
            data = pod(); data[key] = value; cases.append(data)
        for key, value in [("ready", "false"), ("restartCount", True), ("state", {"running": {}, "terminated": {}})]:
            data = pod(); data["status"]["containerStatuses"][0][key] = value; cases.append(data)
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValueError): K.summarize(data, "fixture", "api", UID)

    def test_missing_status_duplicate_and_output_bounds(self):
        data = pod(); data.pop("status")
        self.assertEqual(K.summarize(data, "fixture", "api", UID)["completeness"], "partial")
        data = pod(); data["status"]["containerStatuses"] *= 2
        with self.assertRaises(ValueError): K.summarize(data, "fixture", "api", UID)
        data = pod()
        data["spec"]["containers"] = [{"name": "c"+str(i)} for i in range(33)]
        data["status"]["containerStatuses"] = [{"name": "c"+str(i), "ready": False, "restartCount": 0, "state": {"running": {}}} for i in range(33)]
        result = K.summarize(data, "fixture", "api", UID)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["containers"]["containers"]), 32)

    def test_quantity_and_unknown_text_are_not_unbounded_payloads(self):
        for bad in ["sensitive-marker", True, [], "1"*41]:
            data = pod(); data["spec"]["resources"]["limits"]["memory"] = bad
            with self.assertRaises(ValueError): K.summarize(data, "fixture", "api", UID)
        data = pod(); data["status"]["containerStatuses"][0]["state"]["waiting"]["reason"] = "sensitive-marker"
        self.assertNotIn("sensitive-marker", json.dumps(K.summarize(data, "fixture", "api", UID)))


class ComposeAndInstallationTests(unittest.TestCase):
    def test_named_volume_and_sensitive_default(self):
        import yaml
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"compose.yaml"
            data = {"services": {"api": {"image": "fixture@sha256:"+"a"*64, "volumes": [{"type": "volume", "source": "owned", "target": "/data"}]}}}
            def run():
                path.write_text(yaml.safe_dump(data), encoding="utf-8")
                return subprocess.run([sys.executable, str(ROOT/"docker-operations/scripts/compose-preflight.py"), str(path)], capture_output=True, text=True, timeout=15)
            self.assertEqual(run().returncode, 0)
            data["services"]["api"]["environment"] = {"PASSWORD": "${PASSWORD:-sensitive-marker}"}
            rejected = run()
            self.assertEqual(rejected.returncode, 1)
            self.assertNotIn("sensitive-marker", rejected.stdout+rejected.stderr)
            data["services"]["api"]["environment"] = {"PASSWORD": "${PASSWORD:?required}"}
            self.assertEqual(run().returncode, 0)

    def test_installed_profile_runs_both_offline_helpers(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/"skills"
            result = subprocess.run([sys.executable, str(ROOT/"tools/install.py"), "--profile", "kubernetes", "--destination", str(target), "--apply"], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            for relative, data, args in [
                ("docker-operations/scripts/inspect-container-state.py", docker(), ["--id", IDENTITY]),
                ("kubernetes-operations/scripts/inspect-pod-state.py", pod(), ["--namespace", "fixture", "--name", "api", "--uid", UID])]:
                result = subprocess.run([sys.executable, str(target/relative), *args], input=json.dumps(data), capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["verification"], "not_assessed")
                self.assertNotIn("sensitive-marker", result.stdout+result.stderr)


class NativeFixtureBoundaryTests(unittest.TestCase):
    def test_fixture_refuses_operating_environment_before_any_docker_call(self):
        import container_fixture as native
        with mock.patch.dict(native.os.environ, {}, clear=True), mock.patch.object(native, "command") as command:
            with self.assertRaises(RuntimeError): native.DockerFixture()
            command.assert_not_called()

    def test_cleanup_rejects_foreign_containers_networks_and_volumes(self):
        import container_fixture as native
        for kind in ("container", "network", "volume"):
            fixture = object.__new__(native.DockerFixture)
            fixture.tag = "devops-owned"
            fixture.containers = [IDENTITY] if kind == "container" else []
            fixture.networks = [IDENTITY] if kind == "network" else []
            fixture.volumes = ["devops-owned-data"] if kind == "volume" else []
            fixture.image_tag = None
            fixture.check_daemon = mock.Mock()
            fixture.inspect = mock.Mock(return_value={"Id": IDENTITY, "Name": "devops-owned-data", "Labels": {}, "Config": {"Labels": {}}})
            fixture.docker = mock.Mock()
            with self.subTest(kind=kind), self.assertRaises(RuntimeError): fixture.cleanup()
            fixture.docker.assert_not_called()

    def test_kind_node_drift_refuses_cluster_cleanup(self):
        import smoke_kubernetes as native
        fixture = object.__new__(native.KubernetesFixture)
        fixture.tag = "devops-owned"; fixture.folder = Path("/synthetic-owned"); fixture.environment = {}
        fixture.node_ids = {"devops-owned-control-plane": IDENTITY}
        fixture.inspect = mock.Mock(return_value={"Id": "b"*64, "Config": {"Labels": {"io.x-k8s.kind.cluster": "devops-owned"}}})
        with mock.patch.object(native, "command", return_value=SimpleNamespace(stdout="devops-owned-control-plane\n")) as command:
            with self.assertRaises(RuntimeError): fixture.check_nodes()
            self.assertEqual(command.call_count, 1)
            self.assertIn("get", command.call_args.args[0])

    def test_cluster_uid_drift_prevents_followup_api_actions(self):
        import smoke_kubernetes as native
        fixture = object.__new__(native.KubernetesFixture)
        fixture.cluster_uid = UID
        fixture.check_daemon = mock.Mock()
        fixture.get = mock.Mock(return_value={"metadata": {"uid": "different"}})
        fixture.kubectl = mock.Mock()
        with self.assertRaises(RuntimeError): fixture.check_cluster()
        fixture.kubectl.assert_not_called()
