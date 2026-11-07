"""P2 W3 two-tick, same-owner cooperative transfer study (research only)."""
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "src"))
from p2_stateful_cooperation import (
    GROUPS, METHODS, OPPORTUNITIES, TabularBandit, build_world, make_router,
    play_episode, run_case, target_summary,
)
from openworld_superkernel.population_links import Exchange
from openworld_superkernel.world_fixture import Agent, Action, create_world, verify_replay


class StatefulPopulationCooperationTests(unittest.TestCase):
    def setUp(self):
        self.router, self.tokens = make_router()
        self.genesis, self.needs = build_world(seed=4103, episode=0)

    def test_thirty_agents_ten_real_deciders_and_three_groups(self):
        self.assertEqual(len(self.genesis.agents), 30)
        self.assertEqual(len(OPPORTUNITIES), 10)
        self.assertEqual({op.source_group for op in OPPORTUNITIES},
                         {GROUPS[0], GROUPS[1]})
        self.assertEqual({op.target_group for op in OPPORTUNITIES},
                         {GROUPS[1], GROUPS[2]})
        self.assertEqual(len(self.genesis.graph), 30)
        self.assertEqual(len({a.owner_id for a in self.genesis.agents}), 1)

    def test_group_means_intentionally_cannot_identify_needs(self):
        worlds = [build_world(seed=4103, episode=i) for i in range(15)]
        needy = next(w for w, modes in worlds if modes[1])
        funded = next(w for w, modes in worlds if not modes[1])
        self.assertEqual(target_summary(needy, GROUPS[2], "group_mean"),
                         target_summary(funded, GROUPS[2], "group_mean"))
        self.assertNotEqual(target_summary(needy, GROUPS[2], "histogram4"),
                            target_summary(funded, GROUPS[2], "histogram4"))
        self.assertNotEqual(target_summary(needy, GROUPS[2], "ecf"),
                            target_summary(funded, GROUPS[2], "ecf"))

    def test_action_changes_future_world_and_recipient_signal(self):
        worlds = [build_world(seed=4103, episode=i) for i in range(15)]
        needy = next(w for w, modes in worlds if modes[1])
        hold, hold_world = play_episode(
            self.router, self.tokens, needy, "rule_hold", None,
            exploration_seed=1)
        give, give_world = play_episode(
            self.router, self.tokens, needy, "rule_transfer", None,
            exploration_seed=1)
        self.assertNotEqual(hold_world.fingerprint(), give_world.fingerprint())
        self.assertEqual(hold_world.tick, give_world.tick)
        self.assertTrue(verify_replay(needy, give_world))
        self.assertTrue(verify_replay(needy, hold_world))
        self.assertNotEqual(hold["signals"], give["signals"])
        self.assertGreater(give["transfers"], hold["transfers"])
        self.assertEqual(sum(v for _,v in give_world.balances),
                         sum(v for _,v in needy.balances))

    def test_delayed_feedback_uses_simulated_tick_one_event(self):
        funded = next(build_world(seed=4103, episode=i)[0] for i in range(15)
                      if not build_world(seed=4103, episode=i)[1][1])
        hold, world = play_episode(
            self.router, self.tokens, funded, "rule_hold", None,
            exploration_seed=1)
        self.assertEqual(hold["ticks"], 2)
        self.assertEqual(len(world.journal), 2)
        self.assertTrue(all(e.provenance == "SIMULATED" for e in world.events))
        self.assertTrue(verify_replay(funded, world))
        self.assertEqual(len(hold["reward_list"]), 10)

    def test_reward_is_not_a_counterfactual_training_label(self):
        learner = TabularBandit()
        result, _ = play_episode(
            self.router, self.tokens, self.genesis, "histogram4", learner,
            exploration_seed=1, train=True)
        self.assertEqual(learner.updates, 10)
        self.assertEqual(len(result["reward_list"]), 10)
        self.assertTrue(all(value in (0., 1., -0.25, 0.75)
                            for value in result["reward_list"]))
        self.assertFalse(any(hasattr(learner, attr) for attr in
                             ("oracle", "hidden_modes", "agent_owner")))

    def test_learner_frozen_during_holdout(self):
        learner = TabularBandit()
        play_episode(self.router, self.tokens, self.genesis, "ecf", learner,
                     exploration_seed=5, train=True)
        before = learner.updates
        play_episode(self.router, self.tokens, self.genesis, "ecf", learner,
                     exploration_seed=6, train=False)
        self.assertEqual(learner.updates, before)

    def test_same_seed_same_outcomes_for_all_methods(self):
        a = run_case(seed=4103, method="histogram4", train_episodes=8,
                     holdout_episodes=6)
        b = run_case(seed=4103, method="histogram4", train_episodes=8,
                     holdout_episodes=6)
        self.assertEqual(a, b)
        self.assertEqual(a["train_updates"], 80)
        self.assertEqual(a["decision_agents_per_episode"], 10)

    def test_method_independent_holdout_modes(self):
        rows = [run_case(seed=4103, method=m, train_episodes=5,
                         holdout_episodes=5) for m in METHODS]
        self.assertEqual(len({r["holdout_mode_hash"] for r in rows}), 1)
        self.assertEqual([r["method"] for r in rows], list(METHODS))
        self.assertEqual(rows[0]["train_updates"], 0)
        self.assertEqual(rows[2]["train_updates"], 50)

    def test_no_cross_owner_or_link_bypass(self):
        agents = tuple(Agent(a.agent_id,
                             "evil-other-owner" if a.agent_id=="a10" else a.owner_id,
                             a.region, a.resources) for a in self.genesis.agents)
        wrong = create_world(agents, tuple((o.actor, o.recipient)
                                           for o in OPPORTUNITIES), seed=4103)
        with self.assertRaises(PermissionError):
            self.router.advance(wrong, exchanges=(
                Exchange(GROUPS[0], GROUPS[1],
                         Action("blocked", 0, "synthetic-owner", "a00", "a10",
                                "transfer", 2),
                         self.tokens["a00"], self.tokens["a10"]),
            ), max_actions=10)
        self.assertEqual(wrong.tick, 0)
        self.assertFalse(wrong.events)

    def test_reject_invalid_trial_size(self):
        with self.assertRaises(ValueError):
            run_case(seed=1, method="ecf", train_episodes=201)
        with self.assertRaises(ValueError):
            run_case(seed=1, method="unknown")
        with self.assertRaises(ValueError):
            target_summary(self.genesis, GROUPS[2], "unknown")

    def test_measured_three_seed_holdout_benchmark(self):
        # Actual W3 action-dependent returns. Keep raw negative results.
        # This is a tiny, pre-declared positive control, not MARL acceptance.
        by_seed = []
        for seed in (5101, 5102, 5103):
            rows = [run_case(seed=seed, method=method, train_episodes=25,
                             holdout_episodes=12) for method in METHODS]
            self.assertEqual(len({r["holdout_mode_hash"] for r in rows}), 1)
            score = {r["method"]: r["holdout_avg_reward"] for r in rows}
            needy = rows[0]["holdout_needs_count"]
            analytical_oracle = 1.0 - 0.25 * needy / 24
            self.assertAlmostEqual(score["rule_transfer"], 0.75)
            self.assertAlmostEqual(score["rule_hold"], 1.0 - needy / 24)
            self.assertTrue(all(-0.25 <= value <= analytical_oracle + 0.001
                                for value in score.values()))
            by_seed.append({
                "seed": seed,
                "mode_hash": rows[0]["holdout_mode_hash"],
                "oracle": analytical_oracle,
                "methods": score,
                "registered_agents": 30,
                "decision_makers": 10,
            })
        mean_scores = {
            method: sum(case["methods"][method] for case in by_seed)/len(by_seed)
            for method in METHODS
        }
        evidence = {"schema": "openworld.p2.three-seed-holdout.v0",
                    "cases": by_seed, "mean_holdout_reward": mean_scores,
                    "test_claim": "scripted 2-tick synthetic W3, not general MARL"}
        print("P2_MEASURED_HOLDOUT_JSON=" + json.dumps(evidence, sort_keys=True),
              flush=True)

    def test_cli_json_smoke(self):
        script = ROOT / "benchmarks" / "p2_stateful_cooperation.py"
        process = subprocess.run(
            [sys.executable, str(script), "--train-episodes", "5",
             "--holdout-episodes", "3", "--seeds", "1",
             "--methods", "rule_hold", "histogram4"],
            capture_output=True, text=True, check=False, timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        data = json.loads(process.stdout)
        self.assertEqual(data["schema"], "openworld.p2.stateful-donation-learning.v0")
        self.assertEqual(len(data["cases"]), 2)


if __name__ == "__main__":
    unittest.main()
