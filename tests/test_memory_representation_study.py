"""Test W5 synthetic memory representations and measurement integrity."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks"))

from openworld_superkernel.memory_representation_study import (
    BetaCounts, Discounted, FullHistory, Markov, MarkovFourier, make_model,
)
from hm_representation_study import (
    MODELS, POLICIES, decisions, forecast, response_tape, run, storage_profile,
)


class TestRepresentationStudy(unittest.TestCase):
    def test_positive_and_negative_observation_controls(self):
        for model in (FullHistory(), BetaCounts(), Discounted(), Markov(), MarkovFourier()):
            self.assertEqual(model.predict(0), 0.5)
            for invalid in (True, False, -1, 2, 0.25, None):
                with self.subTest(model=type(model).__name__, invalid=invalid):
                    with self.assertRaises(ValueError):
                        model.observe(0, invalid)
            model.observe(0, 1)
            with self.assertRaises(ValueError):
                model.observe(0, 0)
            with self.assertRaises(ValueError):
                model.predict(-1)

    def test_full_history_and_beta_have_identical_forecast(self):
        h, beta = FullHistory(), BetaCounts()
        for step, y in enumerate((1, 0, 0, 1, 1, 0, 1, 0, 1)):
            self.assertEqual(h.predict(step), beta.predict(step))
            h.observe(step, y)
            beta.observe(step, y)
        self.assertEqual(h.exact_observed_outcome(2), 0)
        self.assertEqual(h.exact_observed_outcome(3), 1)
        self.assertEqual(h.exact_observed_outcome(120), "UNAVAILABLE")
        self.assertEqual(beta.exact_observed_outcome(2), "UNAVAILABLE")
        self.assertGreater(len(json.dumps(h.snapshot())), len(json.dumps(beta.snapshot())))

    def test_markov_tracks_only_adjacent_observed_transitions(self):
        m = Markov()
        for step, y in ((0, 1), (1, 1), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0)):
            m.observe(step, y)
        # Transition across missing t=2 MUST NOT be hallucinated.
        self.assertEqual(m.transitions[1][0], 0)
        self.assertEqual(m.transitions[1][1], 1)
        self.assertEqual(m.transitions[0][0], 4)
        self.assertLess(m.predict(8), BetaCountsForecast(2, 7))
        # On a gap, use global marginal instead of stale last-state transition.
        self.assertAlmostEqual(m.predict(9), (1 + 2) / (2 + 7))

    def test_fourier_is_bounded_and_phase_sensitive(self):
        with self.assertRaises(ValueError):
            MarkovFourier(period=2)
        a, b = MarkovFourier(period=12), MarkovFourier(period=7)
        tape = response_tape("periodic", 41001, 48)
        for tick, y in enumerate(tape):
            a.observe(tick, y)
            b.observe(tick, y)
        self.assertTrue(0 < a.predict(48) < 1)
        self.assertTrue(0 < b.predict(48) < 1)
        self.assertNotEqual(a.snapshot()["period"], b.snapshot()["period"])
        self.assertEqual(len(a.snapshot()["weights"]), 3)
        self.assertTrue(all(abs(v) <= 1 for v in a.weights))

    def test_tape_reproducibility_and_independent_process_laws(self):
        self.assertEqual(response_tape("collapse", 123, 50),
                         response_tape("collapse", 123, 50))
        self.assertNotEqual(response_tape("markov_flip", 123, 50),
                            response_tape("markov_persist", 123, 50))
        with self.assertRaises(ValueError):
            response_tape("unknown", 123, 40)
        with self.assertRaises(ValueError):
            response_tape("stable", -1, 40)
        with self.assertRaises(ValueError):
            response_tape("stable", 123, 10000)

    def test_prequential_equal_information_positive_control(self):
        result = forecast((1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1))
        self.assertEqual(set(result), set(MODELS))
        self.assertAlmostEqual(result["full_history"]["brier"],
                               result["beta_counts"]["brier"], places=14)
        self.assertAlmostEqual(result["full_history"]["log_loss"],
                               result["beta_counts"]["log_loss"], places=14)
        for value in result.values():
            self.assertGreaterEqual(value["brier"], 0)
            self.assertLessEqual(value["brier"], 1)
            self.assertGreaterEqual(value["log_loss"], 0)

    def test_partial_feedback_no_oracle_after_abstention(self):
        outcomes = (1, 0, 1, 1, 0, 0, 0, 1, 1, 0, 1, 0, 0, 1)
        a = decisions(outcomes)
        self.assertEqual(set(a), set(POLICIES))
        self.assertEqual(a["fixed_hold"]["offers"], 0)
        self.assertEqual(a["fixed_hold"]["observed_feedback"], 0)
        self.assertEqual(a["fixed_hold"]["utility"], 0)
        self.assertEqual(a["fixed_offer"]["offers"], len(outcomes))
        self.assertEqual(a["fixed_offer"]["observed_feedback"], len(outcomes))
        self.assertEqual(a["fixed_offer"]["model_updates"], 0)
        for name in MODELS:
            d = a[name]
            self.assertEqual(d["observed_feedback"], d["offers"])
            self.assertEqual(d["model_updates"], d["offers"])
            self.assertEqual(d["successes"] + d["failures"], d["offers"])
            self.assertLessEqual(d["forced_probes"], d["offers"])
            self.assertLessEqual(d["offers"], len(outcomes))

    def test_malformed_benchmark_configuration_fails_closed(self):
        for config in (
            {"seed_count": 0}, {"steps": 7}, {"period": 1},
            {"seed_start": -1}, {"scenarios": ()},
            {"scenarios": ("unknown",)}, {"profile_disk": "false"},
        ):
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    run(**config)

    def test_small_complete_report_and_negative_controls(self):
        report = run(
            seed_start=41001, seed_count=2, steps=24,
            scenarios=("periodic", "markov_flip", "noise"),
            profile_disk=False,
        )
        self.assertEqual(len(report["cases"]), 6)
        self.assertIsNone(report["storage_single_representative_case"])
        self.assertEqual(set(report["summary"]), {"periodic", "markov_flip", "noise"})
        for case in report["cases"]:
            self.assertEqual(len(case["synthetic_tape_sha256"]), 64)
            self.assertEqual(set(case["forecast_fully_observed"]), set(MODELS))
            self.assertEqual(set(case["decisions_censored"]), set(POLICIES))
            self.assertAlmostEqual(
                case["forecast_fully_observed"]["full_history"]["brier"],
                case["forecast_fully_observed"]["beta_counts"]["brier"], places=14,
            )
        changed_period = run(
            seed_start=41001, seed_count=1, steps=24,
            scenarios=("periodic",), profile_disk=False, period=7,
        )
        self.assertNotEqual(
            report["cases"][0]["forecast_fully_observed"]["markov_fourier"]["brier"],
            changed_period["cases"][0]["forecast_fully_observed"]["markov_fourier"]["brier"],
        )

    def test_sqlite_physical_footprint_includes_wal_shm(self):
        footprint = storage_profile((1, 0, 1, 1, 0, 0, 1, 1))
        self.assertEqual(set(footprint), set(MODELS))
        for values in footprint.values():
            self.assertEqual(values["writes"], 8)
            self.assertGreater(values["peak_online_bytes_incl_wal_shm"], 0)
            self.assertGreater(values["end_online_bytes_incl_wal_shm"], 0)
            self.assertGreaterEqual(values["p95_snapshot_write_ms"], 0)

    def test_one_command_smoke_and_no_evidence_clobber(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "raw.json"
            command = [
                sys.executable, str(ROOT / "benchmarks" / "hm_representation_study.py"),
                "--scenario", "stable", "--steps", "8", "--seeds", "1",
                "--no-disk-profile", "--out", str(path),
            ]
            done = subprocess.run(command, cwd=ROOT, capture_output=True,
                                  text=True, timeout=30, check=True)
            payload = json.loads(done.stdout)
            self.assertEqual(payload["parameters"]["steps"], 8)
            self.assertEqual(json.loads(path.read_text()), payload)
            repeated = subprocess.run(command, cwd=ROOT, capture_output=True,
                                      text=True, timeout=30, check=False)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(json.loads(path.read_text()), payload)


def BetaCountsForecast(successes: int, total: int) -> float:
    return (successes + 1) / (total + 2)


if __name__ == "__main__":
    unittest.main()
