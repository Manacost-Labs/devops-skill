"""Fail locally when a workflow cannot reach GitHub's CI scheduler."""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class WorkflowSyntaxTests(unittest.TestCase):
    def test_every_workflow_parses_as_a_mapping_with_jobs(self):
        paths = sorted((ROOT / ".github/workflows").glob("*.yml"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(workflow=path.name):
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                self.assertIsInstance(data, dict)
                self.assertIsInstance(data.get("jobs"), dict)
                self.assertTrue(data["jobs"])


if __name__ == "__main__":
    unittest.main()
