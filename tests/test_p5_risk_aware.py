"""P5 W3 risk abstention: chosen-action outcomes and real state transitions."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "src"))
from p5_risk_aware import (
    BREAK_EVEN, POLICIES, REGIMES, ROUND_COUNT, DonorPolicy, _lower_wilson,
    _probability, evaluate, genesis_world, partner_returns, run_case,
)


class P5RiskTests(unittest.TestCase):
    def test_four_controls_include_safe_hold(self):
        self.assertEqual(POLICIES, ("hold", "always_offer", "all_history", "risk_window"))
        self.assertLess(BREAK_EVEN, .3)

    def test_schedule_has_known_midpoint_for_host_only(self):
        self.assertEqual(_probability("collapse", 9), 10000)
        self.assertEqual(_probability("collapse", 10), 0)
        self.assertEqual(_probability("recovery", 9), 0)
        self.assertEqual(_probability("recovery", 10), 10000)
        self.assertEqual(_probability("mixed", 2), 5000)

    def test_partner_potential_outcome_does_not_depend_on_policy(self):
        vals = [partner_returns("mixed", 9101, i, "a10")
                for i in range(ROUND_COUNT)]
        self.assertEqual(vals, [partner_returns("mixed", 9101, i, "a10")
                                for i in range(ROUND_COUNT)])
        self.assertTrue(any(vals) and not all(vals))

    def test_lower_score_bounds_and_requires_actual_sample(self):
        self.assertGreater(_lower_wilson(2, 2), BREAK_EVEN)
        self.assertLess(_lower_wilson(0, 3), BREAK_EVEN)
        with self.assertRaises(ValueError):
            _lower_wilson(1, 0)
        with self.assertRaises(ValueError):
            _lower_wilson(4, 3)

    def test_abstention_cannot_infer_unobserved_partner_returns(self):
        p = DonorPolicy("risk_window")
        choose, probe = p.choose(0, 8)
        self.assertTrue(choose and probe)
        p.record(donated=False, returned=False)
        self.assertEqual(p.observations, 0)
        self.assertEqual(p.history, [])
        with self.assertRaises(ValueError):
            p.record(donated=False, returned=True)

    def test_initial_probe_then_stop_after_consecutive_refusals(self):
        p = DonorPolicy("risk_window")
        for r in (0, 1):
            act, is_probe = p.choose(r, 8)
            self.assertTrue(act and is_probe)
            p.record(donated=True, returned=False)
        self.assertEqual(p.choose(2, 8), (False, False))
        self.assertEqual(p.choose(3, 8), (False, False))
        self.assertEqual(p.choose(5, 8), (True, True))

    def test_cautious_policy_accepts_consistently_returning_partner(self):
        p = DonorPolicy("risk_window")
        for r in (0, 1):
            act, _ = p.choose(r, 8)
            self.assertTrue(act)
            p.record(donated=True, returned=True)
        self.assertEqual(p.choose(2, 8), (True, False))

    def test_recent_window_detects_collapse_after_negative_observations(self):
        p = DonorPolicy("risk_window")
        for r in (0, 1, 2, 3):
            chosen, _ = p.choose(r, 8)
            self.assertTrue(chosen)
            p.record(donated=True, returned=True)
        for r in (4, 5):
            chosen, _ = p.choose(r, 8)
            self.assertTrue(chosen)
            p.record(donated=True, returned=False)
        # Two recent failures suffice to stop: the third one must not be
        # fabricated as an observation from an unmade donation.
        self.assertEqual(p.choose(6, 8), (False, False))
        self.assertEqual(p.choose(7, 8), (False, False))
        self.assertEqual(len(p.recent), 3)
        self.assertEqual(sum(p.recent), 1)

    def test_hard_resource_zero_prevents_probing_or_transfer(self):
        for name in POLICIES:
            self.assertEqual(DonorPolicy(name).choose(0, 0), (False, False))

    def test_single_host_has_thirty_real_w3_agents_and_balances(self):
        world = genesis_world(9101)
        self.assertEqual(len(world.agents), 30)
        self.assertEqual(len({a.owner_id for a in world.agents}), 1)
        self.assertEqual(len(world.graph), 30)
        self.assertGreater(sum(v for _, v in world.balances), 0)

    def test_cooperative_partner_returns_every_accepted_transfer(self):
        outcome = run_case("always_offer", "cooperative", seed=9101)
        self.assertEqual(outcome["ticks"], 40)
        self.assertEqual(outcome["accepted_by_phase"],
                         outcome["returned_by_phase"])
        self.assertEqual(outcome["unreciprocated_by_phase"], [0, 0])
        self.assertAlmostEqual(outcome["reward_per_decision"], 0.60)

    def test_always_hold_never_exposes_resources(self):
        result = run_case("hold", "hostile", seed=9101)
        self.assertEqual(result["reward_per_decision"], 0)
        self.assertEqual(result["accepted_by_phase"], [0, 0])
        self.assertEqual(result["observed_feedback_count"], 0)
        self.assertEqual(result["ticks"], 40)

    def test_hostile_partner_probing_has_smaller_loss_than_always_offer(self):
        bad = run_case("always_offer", "hostile", seed=9101)
        cautious = run_case("risk_window", "hostile", seed=9101)
        self.assertGreater(cautious["reward_per_decision"],
                           bad["reward_per_decision"])
        self.assertLess(sum(cautious["accepted_by_phase"]),
                        sum(bad["accepted_by_phase"]))
        self.assertEqual(cautious["returned_by_phase"], [0, 0])
        self.assertLessEqual(sum(cautious["probes_by_phase"]), 10 * 5)

    def test_collapse_is_action_dependent_not_policy_oracle(self):
        hold = run_case("hold", "collapse", seed=9101)
        aggressive = run_case("always_offer", "collapse", seed=9101)
        risk = run_case("risk_window", "collapse", seed=9101)
        self.assertEqual(hold["input_world_sha256"],
                         aggressive["input_world_sha256"])
        self.assertEqual(hold["input_world_sha256"],
                         risk["input_world_sha256"])
        self.assertNotEqual(hold["final_world_sha256"],
                            aggressive["final_world_sha256"])
        self.assertEqual(hold["reward_per_decision"], 0)
        self.assertGreater(aggressive["unreciprocated_by_phase"][1], 0)
        self.assertLessEqual(risk["unreciprocated_by_phase"][1],
                             aggressive["unreciprocated_by_phase"][1])

    def test_same_world_seed_yields_same_event_rewards_not_wall_timing(self):
        a = run_case("risk_window", "mixed", seed=9101)
        b = run_case("risk_window", "mixed", seed=9101)
        for field in ("reward_per_decision", "accepted_by_phase",
                      "returned_by_phase", "unreciprocated_by_phase",
                      "probes_by_phase", "final_world_sha256"):
            self.assertEqual(a[field], b[field])

    def test_no_owner_capabilities_ever_emitted_in_result(self):
        result = run_case("risk_window", "recovery", seed=9101)
        self.assertNotIn("capability", result)
        self.assertNotIn("token", result)
        self.assertNotIn("owner_id", result)
        self.assertEqual(result["acting_donors"], 10)
        self.assertEqual(len(result["phase_reward_per_decision"]), 2)

    def test_invalid_config_rejects_without_running_world(self):
        with self.assertRaises(ValueError):
            DonorPolicy("unknown")
        with self.assertRaises(ValueError):
            run_case("unknown", "collapse", seed=1)
        with self.assertRaises(ValueError):
            run_case("risk_window", "wrong", seed=1)
        with self.assertRaises(ValueError):
            evaluate(seeds=6)
        with self.assertRaises(ValueError):
            evaluate(regimes=("collapse", "collapse"))

    def test_small_cli_emits_real_json(self):
        proc = subprocess.run([
            sys.executable, str(ROOT / "benchmarks" / "p5_risk_aware.py"),
            "--seeds", "1", "--regimes", "cooperative", "hostile",
            "--policies", "hold", "risk_window"],
            capture_output=True, text=True, check=False, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["schema"], "openworld.p5.local-risk-probing.v0")
        self.assertEqual(len(payload["cases"]), 4)

    def test_five_seed_measured_results_without_assumed_winner(self):
        proc = subprocess.run([
            sys.executable, str(ROOT / "benchmarks" / "p5_risk_aware.py"),
            "--seeds", "5", "--seed-start", "9101"],
            capture_output=True, text=True, check=False, timeout=180)
        self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
        report = json.loads(proc.stdout)
        self.assertEqual(len(report["cases"]), 5 * len(REGIMES) * len(POLICIES))
        for seed in range(9101, 9106):
            for regime in REGIMES:
                cases = [c for c in report["cases"] if c["seed"] == seed
                         and c["regime"] == regime]
                self.assertEqual(len(cases), len(POLICIES))
                self.assertEqual(len({c["input_world_sha256"] for c in cases}), 1)
                for row in cases:
                    self.assertEqual(row["registered_agents"], 30)
                    self.assertEqual(row["ticks"], 40)
                    self.assertEqual(row["acting_donors"], 10)
                    # Every observed accepted transfer can be counted,
                    # including scripted fixed-offer baselines. Abstention
                    # reveals no response, irrespective of policy family.
                    self.assertEqual(row["observed_feedback_count"],
                                     sum(row["accepted_by_phase"]))
                    self.assertEqual(sum(row["unreciprocated_by_phase"]) +
                                     sum(row["returned_by_phase"]),
                                     sum(row["accepted_by_phase"]))
        # Preserve complete results in CI logs, including losses, with one line
        # per case to avoid a giant truncated log-line.
        print("P5_W5_META=" + json.dumps({
            "schema": report["schema"], "environment": report["environment"],
            "wall_seconds": report["wall_seconds"],
            "process_cpu_seconds": report["process_cpu_seconds"],
            "cases": len(report["cases"]), "seeds": list(range(9101, 9106)),
        }, sort_keys=True, separators=(",", ":")), flush=True)
        for case in report["cases"]:
            print("P5_W5_CASE=" + json.dumps(case, sort_keys=True,
                                             separators=(",", ":")), flush=True)


if __name__ == "__main__":
    unittest.main()
