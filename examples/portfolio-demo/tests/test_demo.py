from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


DEMO_DIR = Path(__file__).resolve().parents[1]
RUNNER = DEMO_DIR / "run_demo.py"


class PortfolioDemoTests(unittest.TestCase):
    def test_end_to_end_demo_is_fail_closed_and_reversible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="portfolio-demo-test-") as temporary:
            evidence_path = Path(temporary) / "evidence.json"
            result = subprocess.run(
                [sys.executable, str(RUNNER), "--output", str(evidence_path)],
                cwd=DEMO_DIR.parents[1],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            repeated = subprocess.run(
                [sys.executable, str(RUNNER), "--output", str(evidence_path)],
                cwd=DEMO_DIR.parents[1],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("refusing to overwrite existing evidence", repeated.stdout)

        self.assertEqual(evidence["status"], "verified")
        self.assertEqual(evidence["mode"], "local-simulation-only")
        self.assertFalse(evidence["live_target_contacted"])
        self.assertTrue(evidence["approval_negative_test"].startswith("BLOCKED:"))
        self.assertTrue(evidence["approval_exact_test"].startswith("ALLOWED:"))
        self.assertTrue(evidence["verification"]["post_change"])
        self.assertTrue(evidence["verification"]["rollback_triggered"])
        self.assertTrue(evidence["verification"]["rollback_verified"])


if __name__ == "__main__":
    unittest.main()
