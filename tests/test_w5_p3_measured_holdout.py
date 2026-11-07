"""W5 pinned P3 multi-seed result; numerical results MUST come from real CI.

Unlike a unit test for reward improvement, this test never imposes a
favorable ranking: it stores negative results too. Only synthetic W3 worlds.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class P3MeasuredHoldoutTest(unittest.TestCase):
    def test_three_seed_six_method_frozen_holdout(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "benchmarks" / "p3_mutual_learning_w3.py"),
             "--train-episodes", "8", "--holdout-episodes", "4",
             "--rounds", "4", "--seeds", "3", "--seed-start", "7101"],
            capture_output=True, text=True, check=False, timeout=180,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["schema"], "openworld.p3.mutual-learning.v0")
        rows = result["cases"]
        self.assertEqual(len(rows), 18)
        methods = ("hold", "always_reciprocate", "no_summary",
                   "group_mean", "histogram4", "ecf")
        compact = []
        for seed in (7101, 7102, 7103):
            group = [x for x in rows if x["seed"] == seed]
            self.assertEqual({x["method"] for x in group}, set(methods))
            inputs = {tuple(x["holdout_initial_fingerprints"]) for x in group}
            self.assertEqual(len(inputs), 1,
                             "Compared methods must have exact same initial W3 worlds")
            values = {}
            for case in group:
                self.assertEqual(case["registered_agents"], 30)
                self.assertEqual(case["decision_agents"], 20)
                self.assertEqual(case["holdout_episodes"], 4)
                self.assertEqual(case["ticks_per_episode"], 8)
                self.assertEqual(case["learning_agents"],
                                 20 if case["method"] in methods[2:] else 0)
                self.assertEqual(case["train_updates"],
                                 8 * 4 * 20 if case["method"] in methods[2:] else 0)
                self.assertEqual(len(case["holdout_final_fingerprints"]), 4)
                values[case["method"]] = {
                    "joint_reward": case["holdout_joint_reward"],
                    "donor_reward": case["holdout_donor_reward"],
                    "receiver_reward": case["holdout_receiver_reward"],
                    "offers": case["holdout_accepted_offers"],
                    "returns": case["holdout_returns"],
                }
            compact.append({"seed": seed, "initial_world_hashes": list(inputs.pop()),
                            "methods": values})
        summary = {method: {
            metric: sum(x["methods"][method][metric] for x in compact) / len(compact)
            for metric in ("joint_reward", "donor_reward", "receiver_reward")
        } for method in methods}
        evidence = {
            "schema": "openworld.w5.p3.three-seed.v0",
            "scope": "synthetic single-owner 20 independent learners, 8 ticks/episode",
            "train_episodes_per_seed": 8,
            "holdout_episodes_per_seed": 4,
            "rounds_per_episode": 4,
            "cases": compact,
            "mean_holdout_reward": summary,
            "wall_seconds": result["wall_seconds"],
        }
        print("P3_W5_RAW_EVIDENCE=" + json.dumps(evidence, sort_keys=True), flush=True)


if __name__ == "__main__":
    unittest.main()
