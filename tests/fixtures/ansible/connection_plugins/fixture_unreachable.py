"""Lose the synthetic local connection once its owned sentinel exists."""
import os
from pathlib import Path

from ansible.errors import AnsibleConnectionFailure
from ansible.plugins.connection.local import Connection as LocalConnection


class Connection(LocalConnection):
    transport = "fixture_unreachable"
    has_pipelining = False

    def check_connection(self):
        if Path(os.environ["ANSIBLE_LAB_DISCONNECT"]).is_file():
            raise AnsibleConnectionFailure("synthetic unreachable node")

    def exec_command(self, cmd, in_data=None, sudoable=True):
        self.check_connection()
        return super().exec_command(cmd, in_data=in_data, sudoable=sudoable)

    def put_file(self, in_path, out_path):
        self.check_connection()
        return super().put_file(in_path, out_path)

    def fetch_file(self, in_path, out_path):
        self.check_connection()
        return super().fetch_file(in_path, out_path)
