"""Guard the independent-review evidence collector without performing a review."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import gate11_reproduction_bundle as gate


PINNED_SHA = "a" * 40


class TestGate11EvidenceBundle(unittest.TestCase):
    def test_plan_has_required_three_seeds_negative_cases_and_r0(self):
        plan = gate.command_plan()
        self.assertEqual(len(plan), 10)
        labels = [label for label, _ in plan]
        self.assertEqual(len(labels), len(set(labels)))
        self.assertIn("01_full_unittest", labels)
        self.assertIn("03_w5_abrupt_seed2026", labels)
        self.assertIn("04_w5_stable_seed2027", labels)
        self.assertIn("05_w5_noise_seed2028", labels)
        self.assertIn("08_protected_five_agent_replay", labels)
        self.assertIn("09_owner_namespace_and_legacy", labels)
        self.assertIn("10_r0_integrated_agent", labels)
        self.assertTrue(all(command[0] == sys.executable for _, command in plan))
        self.assertTrue(any("--seed" in command and "91101" in command
                            for _, command in plan))

    def test_list_only_cli_has_no_side_effects(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "gate11_reproduction_bundle.py"),
             "--list-only"], cwd=ROOT, check=True, capture_output=True,
            text=True, timeout=10,
        )
        data = json.loads(proc.stdout)
        self.assertFalse(data["executed"])
        self.assertEqual(len(data["plan"]), 10)

    def test_refuses_invalid_or_unpinned_commit(self):
        for value in ("", "abc", "A" * 40, "a" * 39, "g" * 40):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    gate.verify_clean_pinned_main(value)
        with patch.object(gate, "_git", side_effect=[
            "main", PINNED_SHA, "b" * 40, PINNED_SHA,
        ]):
            with self.assertRaises(RuntimeError):
                gate.verify_clean_pinned_main(PINNED_SHA)

    def test_rejects_stale_remote_main_and_detached_head(self):
        with patch.object(gate, "_git", side_effect=[
            "main", PINNED_SHA, PINNED_SHA, "b" * 40,
        ]):
            with self.assertRaisesRegex(RuntimeError, "origin/main"):
                gate.verify_clean_pinned_main(PINNED_SHA)
        with patch.object(gate, "_git", side_effect=[
            "HEAD", PINNED_SHA, PINNED_SHA, PINNED_SHA,
        ]):
            with self.assertRaisesRegex(RuntimeError, "detached"):
                gate.verify_clean_pinned_main(PINNED_SHA)

    def test_accepts_exactly_pinned_fetched_main(self):
        with patch.object(gate, "_git", side_effect=[
            "main", PINNED_SHA, PINNED_SHA, PINNED_SHA,
            "", "Test main subject",
        ]):
            result = gate.verify_clean_pinned_main(PINNED_SHA)
        self.assertEqual(result["head_sha"], PINNED_SHA)
        self.assertEqual(result["origin_main_sha"], PINNED_SHA)
        self.assertEqual(result["checked_out_branch"], "main")

    def test_refuses_dirty_checkout(self):
        with patch.object(gate, "_git", side_effect=[
            "main", PINNED_SHA, PINNED_SHA, PINNED_SHA,
            " M tests/new.py",
        ]):
            with self.assertRaises(RuntimeError):
                gate.verify_clean_pinned_main(PINNED_SHA)

    def test_rejects_source_tree_destination_without_executing(self):
        with patch.object(gate, "verify_clean_pinned_main",
                          return_value={"head_sha": PINNED_SHA}):
            with self.assertRaises(ValueError):
                gate.run_bundle(
                    expected_sha=PINNED_SHA, out_dir=ROOT / "unsafe-report"
                )
        self.assertFalse((ROOT / "unsafe-report").exists())

    def test_refuses_existing_output_before_any_command(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "evidence"
            path.mkdir()
            with patch.object(gate, "verify_clean_pinned_main",
                              return_value={"head_sha": PINNED_SHA}):
                with self.assertRaises(FileExistsError):
                    gate.run_bundle(expected_sha=PINNED_SHA, out_dir=path)


if __name__ == "__main__":
    unittest.main()
