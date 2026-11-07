"""W5 oracle validation independent of adaptive model outputs."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
from w5_memory import SCENARIOS, probability, generate, brier, p95, run


class SyntheticOracleTests(unittest.TestCase):
    def test_seed_replay(self):
        self.assertEqual(list(generate(5, 12, 2026, "abrupt")),
                         list(generate(5, 12, 2026, "abrupt")))

    def test_different_seed(self):
        self.assertNotEqual(list(generate(5, 12, 1, "stable")),
                            list(generate(5, 12, 2, "stable")))

    def test_scenario_bounds(self):
        for scenario in SCENARIOS:
            for day in range(15):
                for agent in range(4):
                    self.assertTrue(0 <= probability(agent, day, 15, scenario) <= 1)

    def test_abrupt_is_a_change(self):
        self.assertNotEqual(probability(0, 14, 30, "abrupt"),
                            probability(0, 15, 30, "abrupt"))

    def test_stationary_is_constant(self):
        self.assertEqual(probability(0, 0, 30, "stable"),
                         probability(0, 29, 30, "stable"))

    def test_one_event_per_agent_day(self):
        batches = list(generate(6, 10, 2026, "noise"))
        self.assertEqual(len(batches), 10)
        for day, rows in enumerate(batches):
            self.assertEqual(set(a for a, _, _ in rows), set(range(6)))
            self.assertTrue(all(d == day for _, d, _ in rows))

    def test_invalid_scenario_rejected(self):
        with self.assertRaises(ValueError):
            probability(0, 0, 10, "invalid")

    def test_invalid_population_rejected(self):
        with self.assertRaises(ValueError):
            list(generate(0, 10, 10, "stable"))

    def test_brier_calculation(self):
        self.assertAlmostEqual(brier([0.25, 0.5], [0, 1]), 0.15625)

    def test_brier_length_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            brier([0.5], [])

    def test_p95_bounded(self):
        self.assertTrue(1 <= p95([1, 2, 3, 4]) <= 4)

    def test_tiny_integrated_run(self):
        data = run(agents=3, days=4, seed=2026, scenario="abrupt")
        self.assertEqual(data["updates"], 12)
        self.assertEqual(sum(data["gate_choices"].values()), 12)
        self.assertGreater(data["storage_bytes"]["end_online"]["full_history"], 0)
        self.assertGreater(data["storage_bytes"]["end_online"]["hyper_memory"], 0)
        for value in data["brier"].values():
            self.assertTrue(0 <= value <= 1)


if __name__ == "__main__":
    unittest.main()
