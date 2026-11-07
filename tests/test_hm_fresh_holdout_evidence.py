"""Predeclared fresh-seed W5 HyperMemory holdout, never policy auto-selection.

This is an independent-seed CI fixture, NOT independent human replication.
All observations are SIMULATED; no private or real records are used.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
from hm_representation_study import MODELS, POLICIES, SCENARIOS, run


SEED_START = 73101     # disjoint from study design seeds 41001+
SEED_COUNT = 5
STEPS = 120
PERIOD = 12


class HyperMemoryFreshHoldout(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("OPENWORLD_SLOW_TESTS") == "1",
        "fresh-seed evaluation; set OPENWORLD_SLOW_TESTS=1 to run",
    )
    def test_all_regimes_predeclared_with_wrong_period_control(self):
        full = run(
            seed_start=SEED_START, seed_count=SEED_COUNT,
            steps=STEPS, period=PERIOD, scenarios=SCENARIOS,
            profile_disk=True,
        )
        wrong_period = run(
            seed_start=SEED_START, seed_count=SEED_COUNT,
            steps=STEPS, period=7, scenarios=("periodic",),
            profile_disk=False,
        )
        self.assertEqual(full["schema"], "openworld.hm.representation-study.v0")
        self.assertEqual(len(full["cases"]), SEED_COUNT * len(SCENARIOS))
        self.assertEqual(len(wrong_period["cases"]), SEED_COUNT)
        self.assertIsNotNone(full["storage_single_representative_case"])

        cases = {}
        for case in full["cases"]:
            key = (case["scenario"], case["seed"])
            self.assertNotIn(key, cases)
            cases[key] = case
            self.assertEqual(len(case["synthetic_tape_sha256"]), 64)
            self.assertEqual(set(case["forecast_fully_observed"]), set(MODELS))
            self.assertEqual(set(case["decisions_censored"]), set(POLICIES))
            self.assertAlmostEqual(
                case["forecast_fully_observed"]["full_history"]["brier"],
                case["forecast_fully_observed"]["beta_counts"]["brier"], places=14,
            )
            self.assertAlmostEqual(
                case["forecast_fully_observed"]["full_history"]["log_loss"],
                case["forecast_fully_observed"]["beta_counts"]["log_loss"], places=14,
            )
            self.assertEqual(case["decisions_censored"]["fixed_hold"]["utility"], 0)
            self.assertEqual(
                case["decisions_censored"]["fixed_hold"]["observed_feedback"], 0,
            )
            for name in MODELS:
                row = case["decisions_censored"][name]
                self.assertEqual(row["offers"], row["observed_feedback"])
                self.assertEqual(row["offers"], row["model_updates"])
                self.assertEqual(row["offers"], row["successes"] + row["failures"])

        # Never assert that Markov/Fourier must be the winner. Show losing cases.
        losing = {
            scenario: {
                model: sum(
                    int(c["forecast_fully_observed"][model]["brier"] >
                        c["forecast_fully_observed"]["beta_counts"]["brier"] + 1e-12)
                    for c in full["cases"] if c["scenario"] == scenario
                )
                for model in MODELS if model not in ("beta_counts", "full_history")
            }
            for scenario in SCENARIOS
        }
        record = {
            "status": "CI-generated synthetic fresh-seed evidence; not independently replicated",
            "source": "hm_representation_study.py",
            "full_report": full,
            "wrong_period_negative_control": wrong_period,
            "brier_losses_to_beta_by_regime": losing,
            "cautions": [
                "Full-history and beta counts forecast identically under the given IID estimator",
                "Spectral period 12 is privileged information on the periodic positive control",
                "Frequencies and hyperparameters were selected before these seeds",
                "No real owner identity, irreversible transfers or protected historical evidence involved",
                "Independent second-contributor verification and production cost evaluation remain outstanding",
            ],
        }
        serialized = json.dumps(
            record, sort_keys=True, separators=(",", ":"), allow_nan=False,
        )
        print("OPENWORLD_HM_FRESH_HOLDOUT_SHA256=" +
              hashlib.sha256(serialized.encode("utf-8")).hexdigest(), flush=True)
        print("OPENWORLD_HM_FRESH_HOLDOUT_JSON=" + serialized, flush=True)


if __name__ == "__main__":
    unittest.main()
