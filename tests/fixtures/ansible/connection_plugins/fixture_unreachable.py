"""Inject a controller-observed connection failure; no network or credentials."""
from ansible.errors import AnsibleConnectionFailure
from ansible.plugins.connection import ConnectionBase


class Connection(ConnectionBase):
    transport = "fixture_unreachable"
    has_pipelining = False

    def _connect(self):
        raise AnsibleConnectionFailure("synthetic unreachable node")

    def exec_command(self, cmd, in_data=None, sudoable=True):
        self._connect()

    def put_file(self, in_path, out_path):
        self._connect()

    def fetch_file(self, in_path, out_path):
        self._connect()

    def close(self):
        pass
