"""Only synthetic fixture outcomes; never a production task-result logger."""
import json
import os

from ansible.plugins.callback import CallbackBase


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "aggregate"
    CALLBACK_NAME = "fixture_evidence"
    CALLBACK_NEEDS_ENABLED = True

    def emit(self, value):
        with open(os.environ["ANSIBLE_LAB_EVIDENCE"], "a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, sort_keys=True) + "\n")

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self.emit({"event": "failed", "host": result._host.get_name(), "ignored": bool(ignore_errors)})

    def v2_runner_on_unreachable(self, result):
        self.emit({"event": "unreachable", "host": result._host.get_name()})

    def v2_playbook_on_stats(self, stats):
        self.emit({"event": "stats", "hosts": {host: stats.summarize(host) for host in sorted(stats.processed)}})
