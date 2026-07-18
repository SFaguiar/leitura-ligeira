"""Contracts for the single-command R7 release gate."""

import json
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from scripts import release_gate


BASE_DIR = Path(__file__).resolve().parents[1]
TEST_ROOT = BASE_DIR / "data" / "test-release-gate"


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        TEST_ROOT.mkdir(parents=True, exist_ok=True)
        self.root = TEST_ROOT / str(uuid4())
        self.root.mkdir()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        try:
            TEST_ROOT.rmdir()
        except OSError:
            pass

    def test_gate_contains_every_required_release_layer(self):
        steps = release_gate.build_steps(include_docker=False)
        names = [step.name for step in steps]
        self.assertEqual(len(names), len(set(names)))
        for required in (
            "runtime-lock",
            "python-tests",
            "python-compile",
            "dependency-check",
            "js-rsvp-syntax",
            "js-tts-syntax",
            "js-app-syntax",
            "tts-regression",
            "frontend-contract",
            "frontend-accessibility",
            "frontend-screenreader",
            "frontend-axe",
            "tts-4x-soak",
            "git-whitespace",
            "git-staged-whitespace",
        ):
            self.assertIn(required, names)
        self.assertNotIn("compose-contract", names)
        self.assertTrue(all(step.timeout_seconds > 0 for step in steps))
        docker_names = [step.name for step in release_gate.build_steps(include_docker=True)]
        self.assertIn("compose-contract", docker_names)

    def test_report_and_latest_are_written_atomically(self):
        report = {
            "gate_version": 1,
            "status": "passed",
            "started_at": "2026-07-18T20:00:00Z",
            "steps": [],
        }
        path = release_gate.write_report(self.root, report)
        latest = self.root / "release-gate-latest.json"
        self.assertTrue(path.is_file())
        self.assertTrue(latest.is_file())
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), report)
        self.assertEqual(json.loads(latest.read_text(encoding="utf-8")), report)
        self.assertEqual(list(self.root.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()