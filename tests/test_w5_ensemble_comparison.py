"""Independent W5 oracle and measurement smoke tests, all synthetic."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
from w5_ensemble_comparison import SCENARIOS, draw, evaluate, oracle, physical_bytes, p95


class W5EnsembleComparisonTests(unittest.TestCase):
    def test_replay_same_seed(self):
        self.assertEqual(list(draw(4, 12, 3101, 'abrupt')),
                         list(draw(4, 12, 3101, 'abrupt')))

    def test_different_seed_changes_observations(self):
        self.assertNotEqual(list(draw(4, 12, 3101, 'stable')),
                            list(draw(4, 12, 3102, 'stable')))

    def test_oracle_probabilities_bounded(self):
        for s in SCENARIOS:
            for a in range(4):
                for t in range(20):
                    self.assertTrue(0 <= oracle(a,t,20,s) <= 1)

    def test_unequal_temporal_environments(self):
        self.assertNotEqual(oracle(0,9,20,'abrupt'),oracle(0,10,20,'abrupt'))

    def test_invalid_scenario_rejected(self):
        with self.assertRaises(ValueError):
            list(draw(2,2,5,'missing'))

    def test_zero_agents_rejected(self):
        with self.assertRaises(ValueError):
            list(draw(0,3,5,'stable'))

    def test_brier_values_and_update_counts(self):
        r=evaluate(agents=3,days=4,seed=32,scenario='abrupt')
        self.assertEqual(r['updates'],12)
        self.assertEqual(sum(r['gate_selections'].values()),12)
        self.assertEqual(set(r['brier']), {'static','fast','slow','gate','ensemble'})
        for score in r['brier'].values():
            self.assertGreaterEqual(score,0)
            self.assertLessEqual(score,1)

    def test_size_includes_wal(self):
        r=evaluate(agents=3,days=4,seed=32,scenario='stable')
        for model in ('full_history','gate','ensemble'):
            self.assertGreater(r['storage_bytes']['end_online'][model],0)
            self.assertGreater(r['storage_bytes']['peak_online'][model],0)

    def test_p95_in_range(self):
        self.assertTrue(1<=p95([1,2,3,4])<=4)
        self.assertEqual(p95([]),0)


if __name__ == '__main__':
    unittest.main()
