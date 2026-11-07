"""W5 P4: sample efficiency, changed receiver policy, state shift, honest evidence."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "src"))
from p2_stateful_cooperation import build_world
from p3_mutual_learning_w3 import make_router, run_episode
from p4_sample_efficiency import (
    ACTORS, LEARNED, MODELS, PARTNERS, REGIMES, plan, policies_for,
    policy_snapshot, run_case, training_diagnostics, world_for,
)


class P4LearningAblationTests(unittest.TestCase):
    def test_models_are_fixed_and_role_sharing_has_two_distinct_tables(self):
        independent = policies_for("independent_full")
        shared = policies_for("shared_full")
        self.assertEqual(len(independent), 20)
        self.assertEqual(len({id(x) for x in independent.values()}), 20)
        self.assertEqual(len(shared), 20)
        self.assertEqual(len({id(x) for x in shared.values()}), 2)
        self.assertIs(shared[ACTORS[0]], shared[ACTORS[2]])
        self.assertIsNot(shared[ACTORS[0]], shared[ACTORS[1]])
        self.assertEqual(training_diagnostics(shared)["total_updates"], 0)
        self.assertIsNone(policies_for("fixed_hold"))
        self.assertEqual(plan("shared_histogram")[0], "histogram4")

    def test_shared_roles_pool_reward_but_keep_unique_agent_identity(self):
        shared = policies_for("shared_full")
        shared[ACTORS[0]].update((2, 1), 1, 0.6)
        self.assertEqual(shared[ACTORS[2]].updates, 1)
        self.assertEqual(shared[ACTORS[1]].updates, 0)
        self.assertFalse(hasattr(shared[ACTORS[0]], "owner_id"))

    def test_snapshot_not_identity_and_detects_real_parameter_change(self):
        shared = policies_for("shared_full")
        before = policy_snapshot(shared)
        shared[ACTORS[0]].update((2, 1), 1, 0.6)
        self.assertNotEqual(before, policy_snapshot(shared))
        frozen = deepcopy(shared[ACTORS[0]].q)
        self.assertEqual(frozen, shared[ACTORS[0]].q)

    def test_equal_training_action_budgets_for_learners(self):
        rows = [run_case(model, seed=8101, train_episodes=2,
                         holdout_episodes=1, rounds=2,
                         partners=("native",), regimes=("original",))
                for model in ("independent_full", "independent_compact",
                              "shared_full", "shared_compact")]
        self.assertEqual({r["training"]["total_updates"] for r in rows}, {80})
        self.assertEqual(rows[0]["training"]["distinct_policy_tables"], 20)
        self.assertEqual(rows[2]["training"]["distinct_policy_tables"], 2)
        self.assertEqual(rows[1]["observation_mode"], "binary")
        self.assertEqual(rows[3]["observation_mode"], "binary")
        self.assertTrue(all(r["holdout"][0]["router_tick_p95_seconds"] >= 0
                            for r in rows))

    def test_original_and_shuffled_worlds_have_same_resource_totals(self):
        orig = world_for(8101, 0, "original")
        perm = world_for(8101, 0, "shuffled")
        self.assertEqual(sum(x for _,x in orig.balances),
                         sum(x for _,x in perm.balances))
        for g in range(3):
            indexes = [f"a{i:02d}" for i in range(g * 10, g * 10 + 10)]
            self.assertEqual(sum(dict(orig.balances)[i] for i in indexes),
                             sum(dict(perm.balances)[i] for i in indexes))
        self.assertEqual(perm, world_for(8101, 0, "shuffled"))

    def test_paired_same_start_world_across_methods_and_train_budgets(self):
        args = dict(seed=8102, holdout_episodes=2, rounds=2,
                    partners=("native", "fixed_hold"),
                    regimes=("original", "shuffled"))
        rows = [run_case(model, train_episodes=budget, **args)
                for model,budget in (("fixed_hold", 2),
                                     ("independent_full", 2),
                                     ("shared_full", 4))]
        self.assertEqual([[(x["regime"], x["partner"], x["input_sha256"])
                           for x in row["holdout"]] for row in rows][0],
                         [(x["regime"], x["partner"], x["input_sha256"])
                          for x in rows[1]["holdout"]])
        self.assertEqual([x["input_sha256"] for x in rows[0]["holdout"]],
                         [x["input_sha256"] for x in rows[2]["holdout"]])
        self.assertNotEqual(rows[0]["holdout"][0]["input_sha256"],
                            rows[0]["holdout"][2]["input_sha256"])

    def test_partner_refusal_changes_scripted_cooperation_outcome(self):
        data = run_case("fixed_cooperate", seed=8101, train_episodes=2,
                        holdout_episodes=2, rounds=3,
                        partners=("native", "fixed_hold", "fixed_reciprocate", "mixed"),
                        regimes=("original",))
        env = {x["partner"]: x for x in data["holdout"]}
        self.assertGreater(env["native"]["returns"], 0)
        self.assertEqual(env["fixed_hold"]["returns"], 0)
        self.assertEqual(env["native"]["returns"],
                         env["fixed_reciprocate"]["returns"])
        self.assertGreater(env["native"]["joint_reward"],
                           env["fixed_hold"]["joint_reward"])
        self.assertGreaterEqual(env["mixed"]["returns"], 0)

    def test_partner_override_not_allowed_during_learning(self):
        router, tokens = make_router()
        world, _ = build_world(seed=8101, episode=0)
        with self.assertRaisesRegex(ValueError, "holdout-only"):
            run_episode(router, tokens, world, "no_summary",
                        policies_for("shared_full"), seed=8101, episode=0,
                        training=True, receiver_override="fixed_hold")
        with self.assertRaisesRegex(ValueError, "binary"):
            run_episode(router, tokens, world, "ecf",
                        policies_for("shared_ecf"), seed=8101, episode=0,
                        observation_mode="binary")

    def test_frozen_evaluation_policy_and_w3_replay(self):
        data = run_case("shared_compact", seed=8101, train_episodes=3,
                        holdout_episodes=2, rounds=4)
        self.assertEqual(data["training"]["total_updates"], 240)
        self.assertEqual(data["decision_agents"], 20)
        self.assertEqual(data["registered_agents"], 30)
        self.assertEqual(len(data["holdout"]), len(PARTNERS) * len(REGIMES))
        self.assertTrue(all(x["router_tick_p50_seconds"] >= 0 for x in data["holdout"]))
        self.assertTrue(all(x["router_tick_p95_seconds"] >= x["router_tick_p50_seconds"]
                            for x in data["holdout"]))
        self.assertTrue(all(x["rejected_actions"] >= 0 for x in data["holdout"]))

    def test_invalid_training_and_partner_inputs_rejected(self):
        with self.assertRaises(ValueError):
            run_case("nonexistent", seed=8101, train_episodes=2)
        with self.assertRaises(ValueError):
            run_case("shared_full", seed=8101, train_episodes=129)
        with self.assertRaises(ValueError):
            run_case("shared_full", seed=8101, train_episodes=2,
                     partners=("invented",))
        with self.assertRaises(ValueError):
            run_case("shared_full", seed=8101, train_episodes=2,
                     regimes=("unknown",))
        with self.assertRaises(ValueError):
            world_for(8101, 0, "hidden_future")
        with self.assertRaises(ValueError):
            plan("made_up")

    def test_tiny_cli_smoke(self):
        proc = subprocess.run([
            sys.executable, str(ROOT / "benchmarks" / "p4_sample_efficiency.py"),
            "--seeds", "1", "--budgets", "8", "--holdout-episodes", "1",
            "--rounds", "2", "--models", "fixed_hold", "shared_compact",
            "--partners", "native", "fixed_hold", "--regimes", "original"],
            capture_output=True, text=True, check=False, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["schema"], "openworld.p4.sample-efficiency-partner-shift.v0")
        self.assertEqual(len(data["cases"]), 2)

    @unittest.skipUnless(os.environ.get("OPENWORLD_SLOW_TESTS") == "1",
                         "slow multi-seed research benchmark; set OPENWORLD_SLOW_TESTS=1")
    def test_five_seed_measured_full_matrix_no_assumed_winner(self):
        """CI produces original data, including negative outcomes, without thresholds."""
        proc = subprocess.run([
            sys.executable, str(ROOT / "benchmarks" / "p4_sample_efficiency.py"),
            "--seeds", "5", "--seed-start", "8101",
            "--budgets", "8", "32", "128", "--holdout-episodes", "3",
            "--rounds", "4"],
            capture_output=True, text=True, check=False, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stderr[-4000:])
        report = json.loads(proc.stdout)
        self.assertEqual(report["schema"], "openworld.p4.sample-efficiency-partner-shift.v0")
        cases = report["cases"]
        self.assertEqual(len(cases), 5 * 3 * len(MODELS))
        self.assertEqual(len({x["seed"] for x in cases}), 5)
        self.assertEqual({x["train_episodes"] for x in cases}, {8, 32, 128})
        for seed in range(8101, 8106):
            for budget in (8, 32, 128):
                matched = [x for x in cases if x["seed"] == seed
                           and x["train_episodes"] == budget]
                self.assertEqual({x["model"] for x in matched}, set(MODELS))
                world_inputs = {
                    (h["regime"], h["partner"]): h["input_sha256"]
                    for h in matched[0]["holdout"]
                }
                self.assertEqual(len(world_inputs), len(PARTNERS) * len(REGIMES))
                for row in matched:
                    self.assertEqual(
                        {(h["regime"], h["partner"]): h["input_sha256"]
                         for h in row["holdout"]}, world_inputs)
                    self.assertEqual(row["training"]["total_updates"],
                                     20 * 4 * budget if row["model"] in LEARNED else 0)
                    self.assertEqual(row["ticks_per_episode"], 8)
                    self.assertTrue(all(h["router_tick_p95_seconds"] >= 0
                                        for h in row["holdout"]))
        # Emit complete evidence as independently parseable case lines to avoid
        # truncation of a single giant GitHub Actions log line.
        print("P4_W5_META=" + json.dumps({
            "schema": report["schema"], "environment": report["environment"],
            "wall_seconds": report["wall_seconds"], "cases": len(cases),
            "budgets": [8, 32, 128], "seeds": list(range(8101, 8106)),
        }, sort_keys=True, separators=(",", ":")), flush=True)
        for case in cases:
            print("P4_W5_CASE=" + json.dumps(case, sort_keys=True, separators=(",", ":")),
                  flush=True)


if __name__ == "__main__":
    unittest.main()
