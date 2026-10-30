"""Native isolated kind fixture; explicit local daemon, kubeconfig/context and owned resources."""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request

from container_fixture import APP, HTTP, REQUEST, IMAGE, ROOT, DockerFixture, command
import sys

# Official release assets/checksums verified 2026-10-29; never download "latest".
BINARIES = {
    "kind": ("https://github.com/kubernetes-sigs/kind/releases/download/v0.31.0/kind-linux-amd64",
             "eb244cbafcc157dff60cf68693c14c9a75c4e6e6fedaf9cd71c58117cb93e3fa"),
    "kubectl": ("https://dl.k8s.io/release/v1.35.0/bin/linux/amd64/kubectl",
                "a2e984a18a0c063279d692533031c1eff93a262afcc0afdc517375432d060989"),
}
NODE = "kindest/node:v1.35.0@sha256:452d707d4862f52530247495d180205e029056831160e22870e37e3f6c1ac31f"


class KubernetesFixture(DockerFixture):
    def start_cluster(self):
        if os.uname().machine not in {"x86_64", "amd64"}:
            raise RuntimeError("pinned fixture binaries require amd64")
        self.cluster_attempted = False
        self.cluster_uid = None
        self.namespace_uid = None
        self.node_ids = None
        for name, (url, digest) in BINARIES.items():
            path = self.folder/name
            sha = hashlib.sha256()
            count = 0
            with urllib.request.urlopen(url, timeout=45) as response, path.open("xb") as output:
                while block := response.read(1048576):
                    count += len(block)
                    if count > 100*1048576:
                        raise RuntimeError("binary download size exceeded")
                    sha.update(block); output.write(block)
            if sha.hexdigest() != digest:
                raise RuntimeError("pinned binary hash mismatch")
            path.chmod(0o700)
        self.image_tag = self.tag+":base"
        self.docker("tag", self.image_id, self.image_tag)
        existing = command([str(self.folder/"kind"), "get", "clusters"], environment=self.environment).stdout.splitlines()
        if self.tag in existing:
            raise RuntimeError("cluster name collision")
        # kind's pinned node entrypoint needs a default gateway for DNS setup.
        # Keep a unique owned bridge with normal routing; API binds only loopback.
        self.cluster_network_id = self.network(internal=False)
        self.environment["KIND_EXPERIMENTAL_DOCKER_NETWORK"] = self.tag
        network = self.inspect("network", self.cluster_network_id)
        if network.get("Name") != self.tag or network.get("Labels", {}).get("devops.fixture.owner") != self.tag:
            raise RuntimeError("fixture cluster network ownership changed")
        config = self.folder/"cluster.json"
        config.write_text(json.dumps({"kind": "Cluster", "apiVersion": "kind.x-k8s.io/v1alpha4",
                                     "networking": {"apiServerAddress": "127.0.0.1"},
                                     "nodes": [{"role": "control-plane"}]}), encoding="utf-8")
        self.cluster_attempted = True
        command([str(self.folder/"kind"), "create", "cluster", "--name", self.tag, "--image", NODE,
                 "--config", str(config), "--kubeconfig", str(self.folder/"kubeconfig"), "--wait", "120s"],
                environment=self.environment, timeout=300)
        self.node_ids = self.check_nodes()
        configuration = json.loads(self.kubectl("config", "view", "--raw", "-o", "json").stdout)
        clusters = configuration.get("clusters", [])
        if len(clusters) != 1 or not clusters[0]["cluster"]["server"].startswith("https://127.0.0.1:"):
            raise RuntimeError("fixture API endpoint mismatch")
        self.ca_digest = hashlib.sha256(clusters[0]["cluster"]["certificate-authority-data"].encode()).hexdigest()
        self.cluster_uid = json.loads(self.kubectl("get", "namespace", "kube-system", "-o", "json").stdout)["metadata"]["uid"]
        self.kubectl("--namespace", "kube-system", "rollout", "status", "deployment/coredns", "--timeout=120s", timeout=150)
        command([str(self.folder/"kind"), "load", "docker-image", "--name", self.tag, self.image_tag],
                environment=self.environment, timeout=180)
        self.apply({"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": self.tag, "labels": {
            "devops-fixture-owner": self.tag, "pod-security.kubernetes.io/enforce": "restricted",
            "pod-security.kubernetes.io/enforce-version": "v1.35"}}})
        self.namespace_uid = self.get("namespace", self.tag)["metadata"]["uid"]

    def kubectl(self, *args, **kwargs):
        return command([str(self.folder/"kubectl"), "--kubeconfig", str(self.folder/"kubeconfig"),
                        "--context", "kind-"+self.tag, "--namespace", self.tag,
                        "--request-timeout", "15s", *args], environment=self.environment, **kwargs)

    def get(self, kind, name):
        return json.loads(self.kubectl("get", kind, name, "-o", "json").stdout)

    def check_cluster(self):
        self.check_daemon()
        if self.get("namespace", "kube-system")["metadata"]["uid"] != self.cluster_uid:
            raise RuntimeError("cluster UID changed")
        configuration = json.loads(self.kubectl("config", "view", "--raw", "-o", "json").stdout)
        clusters = configuration.get("clusters", [])
        if len(clusters) != 1 or hashlib.sha256(clusters[0]["cluster"]["certificate-authority-data"].encode()).hexdigest() != self.ca_digest:
            raise RuntimeError("cluster CA changed")
        if self.namespace_uid:
            namespace = self.get("namespace", self.tag)["metadata"]
            if namespace["uid"] != self.namespace_uid or namespace.get("labels", {}).get("devops-fixture-owner") != self.tag:
                raise RuntimeError("namespace ownership changed")

    def apply(self, value):
        self.check_cluster()
        self.kubectl("apply", "--server-side", "--field-manager=devops-fixture", "-f", "-", input=json.dumps(value))

    def pod(self, name, code, arguments=(), *, mounts=(), restart="Never", labels=None):
        volumes, volume_mounts = [], []
        for claim, destination, readonly in mounts:
            volumes.append({"name": claim, "persistentVolumeClaim": {"claimName": claim, "readOnly": readonly}})
            volume_mounts.append({"name": claim, "mountPath": destination, "readOnly": readonly})
        self.apply({"apiVersion": "v1", "kind": "Pod", "metadata": {"name": name, "namespace": self.tag,
                    "labels": {"devops-fixture-owner": self.tag, **(labels or {})}},
                    "spec": {"restartPolicy": restart, "automountServiceAccountToken": False,
                    "securityContext": {"runAsNonRoot": True, "runAsUser": 1000, "runAsGroup": 1000,
                                        "fsGroup": 1000, "seccompProfile": {"type": "RuntimeDefault"}},
                    "volumes": volumes, "containers": [{"name": "app", "image": self.image_tag, "imagePullPolicy": "Never",
                    "command": ["python", "-c", code, *arguments], "volumeMounts": volume_mounts,
                    "resources": {"requests": {"cpu": "25m", "memory": "16Mi"}, "limits": {"cpu": "1", "memory": "64Mi"}},
                    "securityContext": {"allowPrivilegeEscalation": False, "capabilities": {"drop": ["ALL"]}}}]}})
        return self.get("pod", name)["metadata"]["uid"]

    def wait(self, name, predicate, timeout=120):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            value = self.get("pod", name)
            if predicate(value):
                return value
            time.sleep(2)
        # Only this owned fixture Pod; keep a bounded failure explanation before cleanup.
        status = value.get("status", {})
        diagnostic = {"name": name, "phase": status.get("phase"), "conditions": status.get("conditions", [])[:8],
                      "containers": [{key: row.get(key) for key in ("name", "restartCount", "state", "lastState")}
                                     for row in status.get("containerStatuses", [])[:8]]}
        print("FIXTURE POD TIMEOUT: "+json.dumps(diagnostic, ensure_ascii=True)[:6000], flush=True)
        try:
            events = json.loads(self.kubectl("get", "events", "--field-selector", "involvedObject.uid="+value["metadata"]["uid"], "-o", "json").stdout)
            rows = [{key: event.get(key) for key in ("reason", "message", "count")} for event in events.get("items", [])[-8:]]
            print("FIXTURE POD EVENTS: "+json.dumps(rows, ensure_ascii=True)[:6000], flush=True)
        except Exception:
            print("FIXTURE POD EVENTS: unavailable", flush=True)
        raise RuntimeError("fixture Pod did not reach expected state: "+name)

    def execute(self, name, code, arguments=(), *, expected=0, mounts=()):
        uid = self.pod(name, code, arguments, mounts=mounts)
        value = self.wait(name, lambda p: p.get("status", {}).get("phase") in {"Succeeded", "Failed"})
        state = value["status"]["containerStatuses"][0]["state"]["terminated"]
        if value["metadata"]["uid"] != uid or state["exitCode"] != expected:
            raise RuntimeError("fixture Pod identity/exit mismatch")
        logs = self.kubectl("logs", name, "-c", "app", "--tail=30", "--limit-bytes=4096").stdout.strip()
        return value, logs

    def snapshot(self, value):
        result = command([sys.executable, str(ROOT/"kubernetes-operations/scripts/inspect-pod-state.py"),
                          "--namespace", self.tag, "--name", value["metadata"]["name"], "--uid", value["metadata"]["uid"]],
                         input=json.dumps(value))
        return json.loads(result.stdout)

    def check_nodes(self, *, allow_empty=False):
        names = command([str(self.folder/"kind"), "get", "nodes", "--name", self.tag], environment=self.environment).stdout.splitlines()
        # kind removes partial nodes itself on a failed create. Never treat a
        # missing node from an already captured successful cluster as that case.
        if not names and allow_empty and self.node_ids is None:
            return {}
        if names != [self.tag+"-control-plane"]:
            raise RuntimeError("unexpected fixture node set")
        nodes = {}
        for name in names:
            value = self.inspect("container", name)
            if value.get("Config", {}).get("Labels", {}).get("io.x-k8s.kind.cluster") != self.tag:
                raise RuntimeError("fixture node ownership changed")
            if value.get("NetworkSettings", {}).get("Networks", {}).get(self.tag, {}).get("NetworkID") != self.cluster_network_id:
                raise RuntimeError("fixture node network identity changed")
            nodes[name] = value["Id"]
        if self.node_ids is not None and nodes != self.node_ids:
            raise RuntimeError("fixture node identity changed")
        return nodes

    def cleanup_cluster(self):
        if getattr(self, "cluster_attempted", False):
            self.check_daemon()
            nodes = self.check_nodes(allow_empty=True)
            if not nodes:
                return
            if self.namespace_uid:
                self.check_cluster()
                self.kubectl("delete", "namespace", self.tag, "--wait=true", "--timeout=60s", timeout=90)
            command([str(self.folder/"kind"), "delete", "cluster", "--name", self.tag,
                     "--kubeconfig", str(self.folder/"kubeconfig")],
                    environment=self.environment, timeout=120)


def main():
    fixture = KubernetesFixture()
    try:
        fixture.start_cluster()
        fixture.pod("crash", "import sys; sys.exit(42)", restart="Always")
        crash = fixture.wait("crash", lambda p: any(
            c.get("restartCount", 0) >= 1 and c.get("state", {}).get("waiting", {}).get("reason") == "CrashLoopBackOff"
            for c in p.get("status", {}).get("containerStatuses", [])))
        row = fixture.snapshot(crash)["containers"]["containers"][0]
        assert row["current"]["reason"] == "CrashLoopBackOff" and row["previous"]["exit_code"] == 42
        oom, _ = fixture.execute("oom", "block=bytearray(256*1024*1024)", expected=137)
        assert fixture.snapshot(oom)["containers"]["containers"][0]["current"]["reason"] == "OOMKilled"
        print("OK: native Pod backoff/previous exit and cgroup OOM snapshot evidence")

        fixture.pod("server", HTTP, ["0.0.0.0"], labels={"app": "fixture-server"})
        fixture.wait("server", lambda p: any(c.get("ready") for c in p.get("status", {}).get("containerStatuses", [])))
        for name, selector in [("peer", "fixture-server"), ("no-endpoint", "missing")]:
            fixture.apply({"apiVersion": "v1", "kind": "Service", "metadata": {"name": name, "namespace": fixture.tag},
                           "spec": {"selector": {"app": selector}, "ports": [{"port": 8080, "targetPort": 8080}]}})
        fixture.execute("client", REQUEST, ["peer"])
        fixture.execute("client-missing", REQUEST, ["no-endpoint"], expected=23)
        slices = json.loads(fixture.kubectl("get", "endpointslices", "-l", "kubernetes.io/service-name=no-endpoint", "-o", "json").stdout)
        assert sum(len(item.get("endpoints") or []) for item in slices["items"]) == 0
        print("OK: Service DNS/request and DNS-resolved missing-endpoint failure; no NetworkPolicy enforcement claim")

        for name in ("data", "backup", "restored"):
            fixture.apply({"apiVersion": "v1", "kind": "PersistentVolumeClaim", "metadata": {"name": name, "namespace": fixture.tag},
                           "spec": {"accessModes": ["ReadWriteOnce"], "resources": {"requests": {"storage": "64Mi"}}}})
        mounts = [("data", "/data", False), ("backup", "/backup", False)]
        for mode in ("init", "backup", "migrate", "write"):
            fixture.execute("data-"+mode, APP, [mode], mounts=mounts)
        old, _ = fixture.execute("data-old", APP, ["old"], mounts=mounts, expected=20)
        assert fixture.snapshot(old)["containers"]["containers"][0]["current"]["exit_code"] == 20
        _, rows = fixture.execute("data-new", APP, ["new"], mounts=mounts)
        assert json.loads(rows) == [[1, "before"], [2, "after"]]
        restoration = [("backup", "/backup", True), ("restored", "/restore", False)]
        fixture.execute("data-restore", APP, ["restore"], mounts=restoration)
        _, rows = fixture.execute("data-restored", APP, ["restored"], mounts=restoration)
        assert json.loads(rows) == [[1, "before"]]
        fixture.execute("data-repair", APP, ["repair"], mounts=mounts)
        for mode in ("old", "new"):
            _, rows = fixture.execute("data-compatible-"+mode, APP, [mode], mounts=mounts)
            assert json.loads(rows) == [[1, "before"], [2, "after"]]
        print("OK: PVC persistence across Pods, incompatible old reader, separate stale restore and forward repair preserving both writes")
    finally:
        # Never delete fixture files/credentials if cluster ownership/cleanup fails.
        fixture.cleanup_cluster()
        fixture.cleanup()
    print("OK: owned namespace/cluster/tag and fixture directory cleaned")


if __name__ == "__main__":
    main()
