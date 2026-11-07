"""P1 learning gate: deterministic synthetic bandit training, honest negative controls."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
from p1_population_learning import (
    METHODS, TASKS, BAD_REWARD, GOOD_REWARD, OnlineBandit,
    expected_reward, make_scene, observe, optimal_action, population,
    population_features, realized_reward, role_state, run_case, true_signal,
)


class P1PopulationBanditTests(unittest.TestCase):
    def setUp(self):
        self.agents = population(30)
        self.scene = make_scene(self.agents, seed=3101, tick=0, task="mean")

    def test_thirty_distinct_agents_with_typed_genomes(self):
        self.assertEqual(len(self.agents), 30)
        self.assertEqual(len({a.agent_id for a in self.agents}), 30)
        self.assertGreaterEqual(len({a.genome_id for a in self.agents}), 3)
        self.assertTrue(all(a.genome_id.startswith("sha256:") for a in self.agents))
        self.assertFalse(hasattr(self.agents[0], "owner_id"))
        self.assertFalse(hasattr(self.agents[0], "capabilities"))

    def test_scene_is_deterministic_given_world_seed_and_tick(self):
        a = make_scene(self.agents, seed=3101, tick=0, task="mean")
        b = make_scene(self.agents, seed=3101, tick=0, task="mean")
        c = make_scene(self.agents, seed=3102, tick=0, task="mean")
        self.assertEqual(a, b)
        self.assertNotEqual(a.states, c.states)

    def test_private_observation_has_no_other_agent_identity_or_rewards(self):
        for method in METHODS:
            shared = population_features(self.scene, method)
            observed = observe(self.scene, 0, shared)
            self.assertEqual(observed[0], 1.0)
            self.assertEqual(observed[1], self.scene.private_obs[0])
            self.assertTrue(all(type(value) is float for value in observed))
            self.assertFalse(any(hasattr(observed, key) for key in
                                 ("owner", "reward", "history", "token")))

    def test_group_mean_preserves_mean_control(self):
        shared = population_features(self.scene, "group_mean")
        for role in shared:
            self.assertAlmostEqual(shared[role][0],
                                   true_signal(self.scene, role, "mean"))

    def test_ecf_spectral_control_is_exact(self):
        scene = make_scene(self.agents, seed=3101, tick=0, task="spectral")
        shared = population_features(scene, "ecf")
        for role in shared:
            self.assertAlmostEqual(shared[role][0],
                                   true_signal(scene, role, "spectral"))
            self.assertLessEqual(shared[role][0]**2 + shared[role][1]**2,
                                 1.000000001)

    def test_no_summary_cannot_see_group_state(self):
        a = make_scene(self.agents, seed=3111, tick=0, task="mean")
        b = make_scene(self.agents, seed=3112, tick=0, task="mean")
        for method in ("no_summary",):
            self.assertEqual(population_features(a, method),
                             population_features(b, method))
        self.assertNotEqual(population_features(a, "group_mean"),
                            population_features(b, "group_mean"))

    def test_rare_group_is_two_agents_not_census(self):
        agents = population(30, regime="rare")
        self.assertEqual(len([a for a in agents if a.role == "trader"]), 2)
        scene = make_scene(agents, seed=3101, tick=1, task="spectral")
        self.assertEqual(len(role_state(scene, "trader")), 2)
        self.assertEqual(len(population_features(scene, "ecf")["trader"]), 2)

    def test_only_chosen_action_reward_reaches_learner(self):
        learner = OnlineBandit(("builder",), 3)
        context = (1., 0.4, -0.2)
        before = [row[:] for row in learner.weights["builder"]]
        learner.update("builder", context, 1, 1)
        self.assertEqual(learner.weights["builder"][0], before[0])
        self.assertNotEqual(learner.weights["builder"][1], before[1])
        self.assertEqual(learner.updates, 1)

    def test_binary_reward_potential_outcome_and_regret(self):
        for i in range(30):
            good = optimal_action(self.scene, i, "mean")
            bad = 1 - good
            self.assertEqual(expected_reward(good, good), GOOD_REWARD)
            self.assertEqual(expected_reward(bad, good), BAD_REWARD)
            self.assertEqual(realized_reward(self.scene, i, good, "mean"),
                             realized_reward(self.scene, i, good, "mean"))
        with self.assertRaises(ValueError):
            expected_reward(2, 1)

    def test_holdout_is_frozen_and_disjoint(self):
        result = run_case(n=30, train_ticks=20, holdout_ticks=10,
                          seed=3101, task="mean", regime="balanced")
        self.assertNotEqual(result["world_seed"], result["holdout_world_seed"])
        self.assertEqual(result["train_ticks"], 20)
        for method in METHODS:
            row = result["methods"][method]
            self.assertEqual(row["train_updates"], 600)
            self.assertEqual(row["holdout_actions"], 300)
            self.assertGreaterEqual(row["holdout_expected_regret_per_action"], 0)
            self.assertLessEqual(row["holdout_expected_regret_per_action"],
                                 GOOD_REWARD - BAD_REWARD + 1e-12)
        self.assertEqual(result["methods"]["no_summary"]["sketch_width"], 0)
        self.assertEqual(result["methods"]["ecf"]["sketch_width"], 2)

    def test_seed_replay_equal_metrics_excluding_wall_clock(self):
        args = dict(n=30, train_ticks=15, holdout_ticks=5,
                    seed=3101, task="spectral", regime="balanced")
        a, b = run_case(**args), run_case(**args)
        self.assertEqual(a["synthetic_data_sha256"], b["synthetic_data_sha256"])
        for method in METHODS:
            for metric in ("holdout_reward_rate", "holdout_action_accuracy",
                           "holdout_expected_regret_per_action", "train_updates"):
                self.assertEqual(a["methods"][method][metric],
                                 b["methods"][method][metric])

    def test_rare_group_negative_must_not_be_claimed_private(self):
        a = population(30, regime="rare")
        scene = make_scene(a, seed=3101, tick=0, task="mean")
        sketch = population_features(scene, "group_mean")
        self.assertIn("trader", sketch)
        self.assertEqual(len(role_state(scene, "trader")), 2)
        # Public release of this small-group aggregate requires an explicit
        # privacy review; lack of identifiers is not k-anonymity.

    def test_online_learning_positive_controls_outperform_no_summary(self):
        # Pre-registered, fixed-seed sanity checks: action feedback must help,
        # not just produce nonzero gradient updates.
        mean = run_case(n=30, train_ticks=140, holdout_ticks=40,
                        seed=3117, task="mean", regime="balanced")
        spectral = run_case(n=30, train_ticks=140, holdout_ticks=40,
                            seed=3117, task="spectral", regime="balanced")
        mean_methods = mean["methods"]
        spectral_methods = spectral["methods"]
        self.assertGreater(mean_methods["group_mean"]["holdout_action_accuracy"],
                           mean_methods["no_summary"]["holdout_action_accuracy"] + 0.10)
        self.assertGreater(spectral_methods["ecf"]["holdout_action_accuracy"],
                           spectral_methods["no_summary"]["holdout_action_accuracy"] + 0.10)

    @unittest.skipUnless(os.environ.get("OPENWORLD_SLOW_TESTS") == "1",
                         "slow multi-seed research benchmark; set OPENWORLD_SLOW_TESTS=1")
    def test_three_seed_measured_learning_benchmark(self):
        # This is a bounded W5 evidence run, not a scaling or MARL claim.
        # Print a machine-readable record to the exact-head CI logs, including
        # every holdout result and measured encoding cost for review.
        proc = subprocess.run(
            [sys.executable, str(ROOT / "benchmarks" / "p1_population_learning.py"),
             "--agents", "30", "--train-ticks", "100",
             "--holdout-ticks", "40", "--seeds", "3",
             "--seed-start", "4103",
             "--tasks", "mean", "spectral", "--regimes", "balanced"],
            capture_output=True, text=True, check=False, timeout=100,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(len(report["cases"]), 6)
        compact = {
            "schema": report["schema"],
            "environment": report["environment"],
            "elapsed_wall_seconds": report["total_wall_seconds"],
            "cases": [],
        }
        for case in report["cases"]:
            self.assertEqual(case["agents"], 30)
            self.assertNotEqual(case["world_seed"], case["holdout_world_seed"])
            self.assertEqual(case["train_ticks"], 100)
            self.assertEqual(case["holdout_ticks"], 40)
            details = {}
            for method, score in case["methods"].items():
                self.assertEqual(score["train_updates"], 3000)
                self.assertEqual(score["holdout_actions"], 1200)
                details[method] = {
                    "accuracy": score["holdout_action_accuracy"],
                    "regret": score["holdout_expected_regret_per_action"],
                    "reward": score["holdout_reward_rate"],
                    "encode_p95_seconds": score["sketch_p95_seconds"],
                }
            compact["cases"].append({
                "task": case["task"],
                "seed": case["world_seed"],
                "input_sha256": case["synthetic_data_sha256"],
                "methods": details,
            })
        print("P1_BOUNDED_EVIDENCE_JSON=" + json.dumps(compact, sort_keys=True),
              flush=True)

    def test_invalid_tasks_and_budget_bounds_fail_closed(self):
        with self.assertRaises(ValueError):
            population(5)
        with self.assertRaises(ValueError):
            population(30, regime="invalid")
        with self.assertRaises(ValueError):
            make_scene(self.agents, seed=3101, tick=0, task="other")
        with self.assertRaises(ValueError):
            run_case(n=1000)
        with self.assertRaises(ValueError):
            run_case(n=30, train_ticks=5)
        with self.assertRaises(ValueError):
            population_features(self.scene, "oracle")

    def test_smoke_cli_emits_json_without_paid_dependencies(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "benchmarks" / "p1_population_learning.py"),
             "--agents", "30", "--train-ticks", "10",
             "--holdout-ticks", "5", "--seeds", "1",
             "--tasks", "mean", "--regimes", "balanced"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        output = json.loads(proc.stdout)
        self.assertEqual(output["schema"], "openworld.p1.population-bandit.v1")
        self.assertEqual(output["cases"][0]["agents"], 30)
        self.assertEqual(set(output["cases"][0]["methods"]), set(METHODS))


if __name__ == "__main__":
    unittest.main()
