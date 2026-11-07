"""Reference mathematical tests, including a deliberately lossy-memory example."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openworld_superkernel.math_kernel import (
    FiniteKernel, ControlledKernel, ImpossibleObservation, bayes_filter, condition_on_observation,
    predict_belief, task_relative_equivalence, total_variation, two_sign_process,
    exact_outcome_from_counts,
)
from openworld_superkernel.online_ensemble import ExponentialWeights


class KernelTests(unittest.TestCase):
    def setUp(self):
        self.states = ("sun", "rain")
        self.k = FiniteKernel(self.states, self.states,
                              ((0.8, 0.2), (0.3, 0.7)))

    def assertRowsClose(self, a, b):
        self.assertEqual(a.source, b.source)
        self.assertEqual(a.target, b.target)
        for x, y in zip(a.rows, b.rows):
            for v, w in zip(x, y):
                self.assertAlmostEqual(v, w)

    def test_identity_right(self):
        self.assertRowsClose(self.k.compose(FiniteKernel.identity(self.states)), self.k)

    def test_identity_left(self):
        self.assertRowsClose(FiniteKernel.identity(self.states).compose(self.k), self.k)

    def test_composition_hand_calculated(self):
        row = self.k.compose(self.k).rows[0]
        self.assertAlmostEqual(row[0], 0.70)
        self.assertAlmostEqual(row[1], 0.30)

    def test_associativity(self):
        b = FiniteKernel(self.states, self.states, ((0.7, 0.3), (0.9, 0.1)))
        c = FiniteKernel(self.states, self.states, ((0.1, 0.9), (0.4, 0.6)))
        self.assertRowsClose(self.k.compose(b).compose(c), self.k.compose(b.compose(c)))

    def test_controlled_kernel_actions(self):
        stay = FiniteKernel.identity(self.states)
        controlled = ControlledKernel(("evolve", "stay"), (self.k, stay))
        self.assertEqual(controlled.for_action("stay"), stay)
        self.assertEqual(controlled.for_action("evolve"), self.k)

    def test_unknown_controlled_action_rejected(self):
        controlled = ControlledKernel(("evolve",), (self.k,))
        with self.assertRaises(ValueError):
            controlled.for_action("unknown")

    def test_controlled_kernel_support_mismatch_rejected(self):
        other = FiniteKernel(("other",), ("other",), ((1.0,),))
        with self.assertRaises(ValueError):
            ControlledKernel(("evolve", "other"), (self.k, other))

    def test_mismatched_support_rejected(self):
        x = FiniteKernel(("a",), ("b",), ((1.0,),))
        with self.assertRaises(ValueError):
            self.k.compose(x)

    def test_bad_rows_rejected(self):
        for rows in (((1.1, -0.1), (0.2, 0.8)),
                     ((float("nan"), 0.0), (0.2, 0.8)),
                     ((0.7, 0.1), (0.2, 0.8)),
                     ((float("inf"), 0.0), (0.2, 0.8))):
            with self.assertRaises(ValueError):
                FiniteKernel(self.states, self.states, rows)

    def test_duplicate_states_rejected(self):
        with self.assertRaises(ValueError):
            FiniteKernel(("x", "x"), self.states, ((0.5, 0.5), (0.3, 0.7)))

    def test_belief_prediction(self):
        p = predict_belief((0.6, 0.4), self.k)
        self.assertAlmostEqual(p[0], 0.6)
        self.assertAlmostEqual(p[1], 0.4)

    def test_hand_bayes_filter(self):
        result = bayes_filter((0.6, 0.4), self.k, (0.2, 0.9))
        self.assertAlmostEqual(result[0], 0.25)
        self.assertAlmostEqual(result[1], 0.75)

    def test_zero_evidence_errors(self):
        with self.assertRaises(ImpossibleObservation):
            condition_on_observation((0.5, 0.5), (0.0, 0.0))

    def test_likelihood_is_not_distribution(self):
        p = condition_on_observation((0.5, 0.5), (0.8, 0.8))
        self.assertEqual(p, (0.5, 0.5))

    def test_tv_distance(self):
        self.assertAlmostEqual(total_variation((0.8, 0.2), (0.3, 0.7)), 0.5)

    def test_query_relative_fidelity(self):
        self.assertTrue(task_relative_equivalence((0.8, 0.2), (0.79, 0.21), epsilon=0.02))
        self.assertFalse(task_relative_equivalence((0.8, 0.2), (0.79, 0.21), epsilon=0.005))

    def test_marginal_cf_does_not_encode_correlation(self):
        a = two_sign_process(0.9, 0.7)
        b = two_sign_process(0.1, 0.7)
        self.assertAlmostEqual(a["marginal_cf_real"], b["marginal_cf_real"])
        self.assertAlmostEqual(a["lag_one_correlation"] - b["lag_one_correlation"], 1.6)

    def test_lossy_counts_cannot_answer_exact_history_query(self):
        history_a = (1, 0, 1)
        history_b = (0, 1, 1)
        self.assertEqual((len(history_a), sum(history_a)),
                         (len(history_b), sum(history_b)))
        self.assertNotEqual(history_a[0], history_b[0])
        self.assertEqual(exact_outcome_from_counts(3, 2, 0), "UNAVAILABLE")

    def test_degenerate_count_summary_determines_bit(self):
        self.assertEqual(exact_outcome_from_counts(3, 3, 1), 1)
        self.assertEqual(exact_outcome_from_counts(3, 0, 2), 0)

    def test_invalid_count_query_rejected(self):
        with self.assertRaises(ValueError):
            exact_outcome_from_counts(3, 4, 0)

    def test_invalid_keep_probability(self):
        with self.assertRaises(ValueError):
            two_sign_process(float("nan"), 0.2)


class OnlineEnsembleTests(unittest.TestCase):
    def test_initial_uniform(self):
        model = ExponentialWeights(("static", "fast", "slow"))
        self.assertEqual(model.weights, (1/3, 1/3, 1/3))
        self.assertAlmostEqual(model.predict((0.2, 0.5, 0.8)), 0.5)

    def test_learning_shifts_toward_good_expert(self):
        model = ExponentialWeights(("good", "bad"), eta=0.7)
        for _ in range(40):
            _ = model.predict((0.9, 0.1))
            model.observe((0.9, 0.1), 1)
        self.assertGreater(model.weights[0], 0.999)

    def test_weights_stable_under_long_updates(self):
        model = ExponentialWeights(("correct", "incorrect"), eta=1.0)
        for _ in range(2000):
            model.observe((1.0, 0.0), 1)
        self.assertAlmostEqual(sum(model.weights), 1.0)
        self.assertTrue(all(math.isfinite(w) for w in model.weights))

    def test_prequential_regret_bound(self):
        model = ExponentialWeights(("one", "two", "three"), eta=0.3)
        mixture_loss = 0.0
        expert_losses = [0.0] * 3
        for t in range(240):
            outcome = 1 if t % 5 in (0, 1, 2) else 0
            predictions = (0.65, 0.35, 0.5)
            p = model.predict(predictions)
            mixture_loss += (p - outcome) ** 2
            for k in range(3):
                expert_losses[k] += (predictions[k] - outcome) ** 2
            model.observe(predictions, outcome)
        self.assertLessEqual(mixture_loss - min(expert_losses),
                             model.fixed_expert_regret_bound() + 1e-9)

    def test_invalid_observation_rejected_without_update(self):
        model = ExponentialWeights(("x", "y"))
        with self.assertRaises(ValueError):
            model.observe((0.4, 0.6), True)
        self.assertEqual(model.steps, 0)

    def test_invalid_predictions_rejected(self):
        model = ExponentialWeights(("x", "y"))
        for probs in ((float("nan"), 0.5), (0.2,), (1.5, 0.0)):
            with self.assertRaises(ValueError):
                model.predict(probs)

    def test_bounded_state_dimensions(self):
        model = ExponentialWeights(("a", "b", "c"), eta=0.8)
        original_size = len(model.weights)
        for t in range(200):
            model.observe((0.2, 0.5, 0.8), t % 2)
        self.assertEqual(len(model.weights), original_size)
        self.assertEqual(model.steps, 200)


if __name__ == "__main__":
    unittest.main()
