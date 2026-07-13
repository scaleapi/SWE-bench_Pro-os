"""Tests for scripts/swebench_preflight.py"""

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "scripts"))
from swebench_preflight import run_preflight  # noqa: E402


class TestSwebenchPreflight(unittest.TestCase):
    def _layout(self):
        tmp = Path(tempfile.mkdtemp())
        scripts = tmp / "run_scripts"
        inst = scripts / "instance_demo__repo-abc"
        inst.mkdir(parents=True)
        (inst / "run_script.sh").write_text("#!/bin/bash\ntrue\n")
        (inst / "parser.py").write_text("def parse(): return {}\n")
        patches = tmp / "patches.json"
        patches.write_text(
            json.dumps(
                [
                    {
                        "instance_id": "instance_demo__repo-abc",
                        "patch": "diff --git a/foo b/foo\n",
                        "prefix": "gold",
                    }
                ]
            )
        )
        return tmp, patches, scripts

    def test_passes_valid_layout(self):
        tmp, patches, scripts = self._layout()
        report = run_preflight(patches, scripts)
        self.assertTrue(report["passed"])

    def test_fails_duplicate_instance_id(self):
        tmp, patches, scripts = self._layout()
        patches.write_text(
            json.dumps(
                [
                    {
                        "instance_id": "instance_demo__repo-abc",
                        "patch": "diff\n",
                        "prefix": "gold",
                    },
                    {
                        "instance_id": "instance_demo__repo-abc",
                        "patch": "diff\n",
                        "prefix": "gold",
                    },
                ]
            )
        )
        report = run_preflight(patches, scripts)
        self.assertFalse(report["passed"])

    def test_fails_missing_run_script(self):
        tmp, patches, scripts = self._layout()
        (scripts / "instance_demo__repo-abc" / "run_script.sh").unlink()
        report = run_preflight(patches, scripts)
        self.assertFalse(report["passed"])

    def test_fails_missing_parser(self):
        tmp, patches, scripts = self._layout()
        (scripts / "instance_demo__repo-abc" / "parser.py").unlink()
        report = run_preflight(patches, scripts)
        self.assertFalse(report["passed"])

    def test_malformed_patch_does_not_crash(self):
        tmp, patches, scripts = self._layout()
        patches.write_text(
            json.dumps(
                [
                    {"patch": "diff\n", "prefix": "gold"},
                    {
                        "instance_id": "instance_demo__repo-abc",
                        "patch": "diff --git a/foo b/foo\n",
                        "prefix": "gold",
                    },
                ]
            )
        )
        report = run_preflight(patches, scripts)
        self.assertFalse(report["passed"])
        self.assertTrue(any("missing keys" in err for err in report["errors"]))

    def test_non_dict_patch_entry_does_not_crash(self):
        tmp, patches, scripts = self._layout()
        patches.write_text(
            json.dumps(
                [
                    42,
                    {
                        "instance_id": "instance_demo__repo-abc",
                        "patch": "diff --git a/foo b/foo\n",
                        "prefix": "gold",
                    },
                ]
            )
        )
        report = run_preflight(patches, scripts)
        self.assertFalse(report["passed"])
        self.assertTrue(any("expected object" in err for err in report["errors"]))

    def test_warns_nodebb_sendmail(self):
        tmp, patches, scripts = self._layout()
        inst = scripts / "instance_NodeBB__NodeBB-deadbeef"
        inst.mkdir()
        (inst / "run_script.sh").write_text("#!/bin/bash\ntrue\n")
        (inst / "parser.py").write_text("pass\n")
        patches.write_text(
            json.dumps(
                [
                    {
                        "instance_id": "instance_NodeBB__NodeBB-deadbeef",
                        "patch": "diff\n",
                        "prefix": "gold",
                    }
                ]
            )
        )
        report = run_preflight(patches, scripts)
        self.assertTrue(report["passed"])
        self.assertTrue(any("sendmail" in w["warning"] for w in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
