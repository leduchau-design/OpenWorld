"""P3 integration gates: independent donor and recipient learning on W3."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "src"))
from p3_mutual_learning_w3 import (
    AgentBandit, METHODS, LEARNED, OPPORTUNITIES, build_world,
    donor_context, make_router, receiver_context, run_case, run_episode,
)
from openworld_superkernel.population_links import Exchange
from openworld_superkernel.world_fixture import Agent, Action, create_world


class P3MutualLearnersTests(unittest.TestCase):
    def setUp(self):
        self.router, self.tokens = make_router()
        self.world, self.needs = build_world(seed=6101, episode=0)

    def policies(self):
        return {x: AgentBandit()
                for op in OPPORTUNITIES for x in (op.actor, op.recipient)}

    def test_twenty_distinct_deciders_thirty_registered(self):
        ids = [x for op in OPPORTUNITIES for x in (op.actor, op.recipient)]
        self.assertEqual(len(set(ids)), 20)
        self.assertEqual(len(self.world.agents), 30)
        self.assertEqual(len({a.owner_id for a in self.world.agents}), 1)

    def test_each_individual_has_independent_policy(self):
        p = self.policies()
        self.assertIsNot(p["a00"], p["a01"])
        p["a00"].update((1,), 1, 0.6)
        self.assertEqual(p["a00"].updates, 1)
        self.assertEqual(p["a01"].updates, 0)
        self.assertFalse(any(hasattr(p["a00"], k) for k in
                             ("owner_id", "token", "private_memory", "oracle")))

    def test_receiver_can_learn_from_its_own_new_balance(self):
        world = self.world
        a = receiver_context(world, "a10", got_offer=False)
        b = receiver_context(world, "a10", got_offer=True)
        self.assertEqual(a[-1], 0)
        self.assertEqual(b[-1], 1)
        self.assertNotEqual(a, b)

    def test_authorized_donation_changes_later_world(self):
        hold, give = (run_episode(
            self.router, self.tokens, self.world, mode, None,
            seed=6101, episode=0, rounds=4,
        ) for mode in ("hold", "always_reciprocate"))
        self.assertEqual(hold["ticks"], 8)
        self.assertEqual(give["ticks"], 8)
        self.assertEqual(len(hold["per_round_fingerprints"]), 8)
        self.assertEqual(len(give["per_round_fingerprints"]), 8)
        self.assertNotEqual(hold["final_fingerprint"], give["final_fingerprint"])
        self.assertEqual(hold["total_resources"], give["total_resources"])
        self.assertEqual(hold["accepted_offers"], 0)
        self.assertGreater(give["accepted_offers"], 0)
        self.assertEqual(give["returns"], give["accepted_offers"])

    def test_both_donor_and_receiver_learn_after_ten_pairs(self):
        policies = self.policies()
        output = run_episode(self.router, self.tokens, self.world,
                             "histogram4", policies,
                             seed=6101, episode=0, rounds=4, training=True)
        self.assertEqual(output["ticks"], 8)
        self.assertEqual({p.updates for p in policies.values()}, {4})
        self.assertEqual(sum(p.updates for p in policies.values()), 80)

    def test_holdout_freezes_all_twenty_policy_tables(self):
        policies = self.policies()
        run_episode(self.router, self.tokens, self.world, "no_summary",
                    policies, seed=6101, episode=0, training=True)
        before = {a: (p.updates, deepcopy(p.q))
                  for a, p in policies.items()}
        run_episode(self.router, self.tokens, self.world, "no_summary",
                    policies, seed=6102, episode=0, training=False)
        self.assertEqual(before, {a: (p.updates, deepcopy(p.q))
                                  for a, p in policies.items()})

    def test_identical_world_seed_is_replay_deterministic(self):
        a = run_episode(self.router, self.tokens, self.world,
                        "always_reciprocate", None, seed=6101, episode=0)
        b = run_episode(self.router, self.tokens, self.world,
                        "always_reciprocate", None, seed=6101, episode=0)
        self.assertEqual(a, b)

    def test_group_mean_can_hide_different_need_patterns(self):
        cases = [build_world(seed=6101, episode=i) for i in range(60)]
        # Hold the first destination group's mode fixed: otherwise donor a15's
        # *own* balance changes, confounding the intended mean-collapse test.
        modes = {pair: world for world, pair in cases}
        donor_mode = next(mode for mode in (0, 1)
                          if (mode, 0) in modes and (mode, 1) in modes)
        needy = modes[(donor_mode, 1)]
        funded = modes[(donor_mode, 0)]
        mean_n = donor_context(needy, "a15", "guild-2", "group_mean",
                               previous_return=0)
        mean_f = donor_context(funded, "a15", "guild-2", "group_mean",
                               previous_return=0)
        self.assertEqual(mean_n, mean_f)
        hist_n = donor_context(needy, "a15", "guild-2", "histogram4",
                               previous_return=0)
        hist_f = donor_context(funded, "a15", "guild-2", "histogram4",
                               previous_return=0)
        self.assertNotEqual(hist_n, hist_f)

    def test_reject_cross_owner_even_if_reciprocity_reward_is_positive(self):
        agents = tuple(Agent(a.agent_id,
                             "attacker" if a.agent_id == "a10" else a.owner_id,
                             a.region, a.resources) for a in self.world.agents)
        cross = create_world(agents,
                             tuple((op.actor, op.recipient) for op in OPPORTUNITIES),
                             seed=6101)
        with self.assertRaises(PermissionError):
            self.router.advance(cross, exchanges=(
                Exchange("guild-0", "guild-1",
                         Action("cross", 0, "synthetic-owner", "a00",
                                "a10", "transfer", 1),
                         self.tokens["a00"], self.tokens["a10"]),
            ), max_actions=10)
        self.assertEqual(cross.tick, 0)

    def test_no_hidden_oracle_for_training_and_no_genome_privilege(self):
        policies = self.policies()
        self.assertNotIn("oracle", vars(policies["a00"]))
        self.assertEqual(tuple(sorted(METHODS)),
                         tuple(sorted(("hold", "always_reciprocate",
                                       "no_summary", "group_mean",
                                       "histogram4", "ecf"))))
        self.assertFalse(hasattr(self.world.agents[0], "genome_id"))

    def test_bounded_config_failure(self):
        with self.assertRaises(ValueError):
            run_case("unknown", seed=6101)
        with self.assertRaises(ValueError):
            run_case("ecf", seed=6101, train_episodes=0)
        with self.assertRaises(ValueError):
            run_case("ecf", seed=6101, rounds=20)
        with self.assertRaises(ValueError):
            run_episode(self.router, self.tokens, self.world, "ecf", None,
                        seed=6101, episode=0)

    def test_same_world_seeds_for_all_holdout_methods(self):
        for method in ("hold", "no_summary", "histogram4"):
            data = run_case(method, seed=6101, train_episodes=2,
                            holdout_episodes=2, rounds=3)
            self.assertEqual(data["registered_agents"], 30)
            self.assertEqual(data["decision_agents"], 20)
            self.assertEqual(data["ticks_per_episode"], 6)
            self.assertEqual(data["train_updates"],
                             120 if method in LEARNED else 0)
            self.assertEqual(len(data["holdout_final_fingerprints"]), 2)

    def test_cli_tiny_json_run(self):
        script = ROOT / "benchmarks" / "p3_mutual_learning_w3.py"
        result = subprocess.run(
            [sys.executable, str(script), "--train-episodes", "2",
             "--holdout-episodes", "1", "--rounds", "2",
             "--seeds", "1", "--methods", "hold", "histogram4"],
            capture_output=True, text=True, check=False, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema"], "openworld.p3.mutual-learning.v0")
        self.assertEqual(len(report["cases"]), 2)


if __name__ == "__main__":
    unittest.main()
