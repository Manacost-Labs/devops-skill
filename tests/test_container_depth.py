from __future__ import annotations

import importlib.util
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock
from pathlib import Path
from contextlib import redirect_stdout

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
NATIVE_K = load("native_pod_evidence", "tests/smoke_kubernetes.py")


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


class NativeBackoffEvidenceTests(unittest.TestCase):
    def failure(self):
        value = pod(); row = value["status"]["containerStatuses"][0]
        row["state"] = {"terminated": {"reason": "Error", "exitCode": 42}}
        row["lastState"] = {"terminated": {"reason": "Error", "exitCode": 42}}
        event = {"involvedObject": {"kind": "Pod", "namespace": "fixture", "name": "api", "uid": UID, "fieldPath": "spec.containers{api}"},
                 "source": {"component": "kubelet"}, "type": "Warning", "reason": "BackOff", "message": "Back-off restarting failed container api in pod api_fixture("+UID+")"}
        return value, event

    def observed(self, value, events):
        return NATIVE_K.crash_backoff_evidence(value, events, "fixture", "api", UID, "api")

    def test_live_terminated_state_keeps_truth_while_event_proves_restart_backoff(self):
        value, event = self.failure(); original = copy.deepcopy(value)
        self.assertEqual(self.observed(value, [event]), "uid-bound-kubelet-event")
        row = K.summarize(value, "fixture", "api", UID)["containers"]["containers"][0]
        self.assertEqual(row["current"], {"kind": "terminated", "reason": "Error", "exit_code": 42, "signal": None})
        self.assertEqual(row["previous"]["exit_code"], 42)
        self.assertEqual(value, original)

    def test_real_waiting_backoff_still_has_native_status_proof(self):
        value, _ = self.failure(); value["status"]["containerStatuses"][0]["state"] = {"waiting": {"reason": "CrashLoopBackOff"}}
        self.assertEqual(self.observed(value, []), "container-status")

    def test_wrong_event_identity_image_pull_or_reporter_cannot_substitute(self):
        value, event = self.failure()
        self.assertIsNone(self.observed(value, []))
        for section, field, wrong in (("involvedObject", "uid", "other-uid"), ("involvedObject", "namespace", "other"),
                                      ("involvedObject", "name", "other"), ("involvedObject", "fieldPath", "spec.containers{other}"),
                                      ("involvedObject", "kind", "Node"), ("source", "component", "other-reporter")):
            changed = copy.deepcopy(event); changed[section][field] = wrong
            self.assertIsNone(self.observed(value, [changed]), (section, field))
        for field, wrong in (("type", "Normal"), ("reason", "Pulled"), ("message", "Back-off pulling image synthetic")):
            changed = dict(event, **{field: wrong})
            self.assertIsNone(self.observed(value, [changed]), field)

    def test_actual_repeated_exit_42_and_pod_identity_are_required(self):
        value, event = self.failure()
        for field, wrong in (("uid", "other"), ("name", "other"), ("namespace", "other")):
            changed = copy.deepcopy(value); changed["metadata"][field] = wrong
            self.assertIsNone(self.observed(changed, [event]))
        for count in (None, True, 0):
            changed = copy.deepcopy(value); changed["status"]["containerStatuses"][0]["restartCount"] = count
            self.assertIsNone(self.observed(changed, [event]))
        for section in ("state", "lastState"):
            changed = copy.deepcopy(value); changed["status"]["containerStatuses"][0][section]["terminated"]["exitCode"] = 137
            self.assertIsNone(self.observed(changed, [event]))


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
    def test_api_dns_subdomain_names_and_quantity_units(self):
        for name in ("a"*64, "a"*253, "api.example"):
            data = pod(); data["metadata"]["name"] = name
            self.assertEqual(K.summarize(data, "fixture", name, UID)["pod_name"], name)
        for name in ("a"*254, "a..b", ".a", "a.", "a_B", "-api"):
            data = pod(); data["metadata"]["name"] = name
            with self.assertRaises(ValueError): K.summarize(data, "fixture", name, UID)
        for quantity in ("1E", "1Ei", "100m", "1e+6", "0", "0.5Gi"):
            data = pod(); data["spec"]["resources"]["limits"]["memory"] = quantity
            self.assertEqual(K.summarize(data, "fixture", "api", UID)["pod_resources"]["limits"]["memory"], quantity)

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
    def test_partial_kind_creation_cleanup_only_accepts_empty_before_identity_capture(self):
        import smoke_kubernetes as native
        fixture = object.__new__(native.KubernetesFixture)
        fixture.tag = "devops-owned"; fixture.folder = Path("/synthetic-owned"); fixture.environment = {}
        fixture.node_ids = None
        with mock.patch.object(native, "command", return_value=SimpleNamespace(stdout="")):
            self.assertEqual(fixture.check_nodes(allow_empty=True), {})
            with self.assertRaises(RuntimeError): fixture.check_nodes()
            fixture.node_ids = {"devops-owned-control-plane": IDENTITY}
            with self.assertRaises(RuntimeError): fixture.check_nodes(allow_empty=True)

    def test_fixture_environment_pins_runtime_network_selection_and_kubeconfig(self):
        import container_fixture as native
        folder = Path("owned-scratch")
        result = native.fixture_environment({"DOCKER_HOST": "tcp://unrelated", "DOCKER_CONTEXT": "prod",
                 "KUBECONFIG": "unrelated", "KIND_EXPERIMENTAL_PROVIDER": "podman",
                 "KIND_EXPERIMENTAL_DOCKER_NETWORK": "unrelated", "PATH": "trusted-path"}, folder)
        self.assertEqual(result["DOCKER_HOST"], "unix:///var/run/docker.sock")
        self.assertEqual(result["KIND_EXPERIMENTAL_PROVIDER"], "docker")
        self.assertNotIn("KIND_EXPERIMENTAL_DOCKER_NETWORK", result)
        self.assertNotIn("DOCKER_CONTEXT", result)
        self.assertEqual(result["KUBECONFIG"], str(folder/"kubeconfig"))
        self.assertEqual(result["PATH"], "trusted-path")

    def test_fixture_refuses_operating_environment_before_any_docker_call(self):
        import container_fixture as native
        with mock.patch.dict(native.os.environ, {}, clear=True), mock.patch.object(native, "command") as command:
            with self.assertRaises(RuntimeError): native.DockerFixture()
            command.assert_not_called()

    def test_fixture_rejects_self_hosted_and_missing_runner_environment(self):
        import container_fixture as native
        for environment in ("self-hosted", None):
            values = {"GITHUB_ACTIONS": "true", "RUNNER_OS": "Linux"}
            if environment is not None: values["RUNNER_ENVIRONMENT"] = environment
            with mock.patch.dict(native.os.environ, values, clear=True), mock.patch.object(native, "command") as command:
                with self.assertRaises(RuntimeError): native.DockerFixture()
                command.assert_not_called()

    def test_daemon_drift_stops_docker_command_before_mutation(self):
        import container_fixture as native
        fixture = object.__new__(native.DockerFixture)
        fixture.daemon_id = "original"
        fixture.check_daemon = mock.Mock(side_effect=RuntimeError("daemon changed"))
        with mock.patch.object(native, "command") as command:
            with self.assertRaises(RuntimeError): fixture.docker("volume", "rm", "synthetic")
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
        fixture.cluster_network_id = "network-owned"
        fixture.node_ids = {"devops-owned-control-plane": IDENTITY}
        fixture.inspect = mock.Mock(return_value={"Id": "b"*64, "Config": {"Labels": {"io.x-k8s.kind.cluster": "devops-owned"}},
                                   "NetworkSettings": {"Networks": {"devops-owned": {"NetworkID": "network-owned"}}}})
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


class OomObservationTests(unittest.TestCase):
    @staticmethod
    def report(**changes):
        return {"container_id": IDENTITY, "state": "exited", "running": False,
                "exit_code": 137, "oom_killed": False, **changes}

    class Clock:
        def __init__(self): self.now = 0
        def __call__(self): return self.now
        def sleep(self, interval): self.now += interval

    def test_late_explicit_oom_uses_same_identity_without_restarting(self):
        import smoke_containers as native
        clock = self.Clock()
        fixture = mock.Mock(runtime_versions={"Engine": "fixture"})
        with mock.patch.object(native, "snapshot", side_effect=[self.report(), self.report(oom_killed=True)]) as snapshot:
            result = native.wait_for_oom_report(fixture, IDENTITY, timeout=1, clock=clock, sleep=clock.sleep)
        self.assertTrue(result["oom_killed"])
        self.assertEqual(snapshot.call_count, 2)
        self.assertTrue(all(call.args == (fixture, IDENTITY) and call.kwargs["deadline"] == 1 for call in snapshot.call_args_list))
        self.assertEqual(fixture.mock_calls, [])

    def test_absent_oom_evidence_times_out_and_prints_only_selected_diagnostics(self):
        import smoke_containers as native
        clock = self.Clock(); output = io.StringIO()
        fixture = mock.Mock(runtime_versions={"Engine": "fixture"})
        with mock.patch.object(native, "snapshot", return_value=self.report(env="sensitive-marker")) as snapshot, redirect_stdout(output):
            with self.assertRaises(RuntimeError):
                native.wait_for_oom_report(fixture, IDENTITY, timeout=.5, clock=clock, sleep=clock.sleep)
        self.assertEqual(snapshot.call_count, 2)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "oom_evidence_not_observed")
        self.assertFalse(report["last_oom_killed"])
        self.assertNotIn("sensitive-marker", output.getvalue())
        self.assertEqual(fixture.mock_calls, [])

    def test_invalid_state_identity_and_collection_errors_fail_without_retry(self):
        import smoke_containers as native
        for change in ({"container_id": "b"*64}, {"state": "running"}, {"running": True},
                       {"exit_code": 0}, {"exit_code": True}, {"oom_killed": None}, {"oom_killed": 1}):
            clock = self.Clock(); fixture = mock.Mock()
            with mock.patch.object(native, "snapshot", return_value=self.report(**change)) as snapshot:
                with self.assertRaises(RuntimeError):
                    native.wait_for_oom_report(fixture, IDENTITY, clock=clock, sleep=clock.sleep)
                self.assertEqual(snapshot.call_count, 1)
        for failure in (RuntimeError("owner/daemon mismatch"), subprocess.TimeoutExpired("synthetic", 1)):
            with mock.patch.object(native, "snapshot", side_effect=failure) as snapshot:
                with self.assertRaises(type(failure)): native.wait_for_oom_report(mock.Mock(), IDENTITY)
                self.assertEqual(snapshot.call_count, 1)

    def test_success_after_deadline_is_rejected(self):
        import smoke_containers as native
        clock = self.Clock(); fixture = mock.Mock(runtime_versions={})
        def late(*args, **kwargs):
            clock.now = 2
            return self.report(oom_killed=True)
        with mock.patch.object(native, "snapshot", side_effect=late), redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                native.wait_for_oom_report(fixture, IDENTITY, timeout=1, clock=clock, sleep=clock.sleep)

    def test_snapshot_binds_owner_inspection_and_passes_deadline(self):
        import smoke_containers as native
        fixture = mock.Mock()
        fixture.owned_container.return_value = docker()[0]
        with mock.patch.object(native, "command", return_value=SimpleNamespace(stdout=json.dumps(self.report(oom_killed=True)))) as command:
            native.snapshot(fixture, IDENTITY, deadline=8)
        fixture.owned_container.assert_called_once_with(IDENTITY, deadline=8)
        self.assertEqual(command.call_args.kwargs["deadline"], 8)
        self.assertEqual(json.loads(command.call_args.kwargs["input"])[0]["Id"], IDENTITY)

    def test_owned_snapshot_runs_actual_offline_helper(self):
        import smoke_containers as native
        fixture = mock.Mock()
        fixture.owned_container.return_value = docker()[0]
        result = native.snapshot(fixture, IDENTITY)
        self.assertEqual(result["container_id"], IDENTITY)
        self.assertEqual(result["exit_code"], 137)
        self.assertIs(result["oom_killed"], False)
        self.assertNotIn("sensitive-marker", json.dumps(result))

    def test_deadline_clamps_subprocess_and_propagates_through_daemon_guard(self):
        import container_fixture as native
        with mock.patch.object(native.time, "monotonic", return_value=3), mock.patch.object(native.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            native.command(["synthetic"], timeout=120, deadline=8)
            self.assertEqual(run.call_args.kwargs["timeout"], 5)
            run.reset_mock()
            with self.assertRaises(TimeoutError): native.command(["synthetic"], deadline=2)
            run.assert_not_called()
        fixture = object.__new__(native.DockerFixture)
        fixture.daemon_id = "fixture"; fixture.folder = Path("owned"); fixture.environment = {}
        with mock.patch.object(native, "command", side_effect=[SimpleNamespace(stdout='{"ID":"fixture","OSType":"linux"}'), SimpleNamespace(stdout="[]")]) as command:
            fixture.docker("container", "inspect", IDENTITY, deadline=8)
            self.assertEqual(command.call_count, 2)
            self.assertTrue(all(call.kwargs["deadline"] == 8 for call in command.call_args_list))
