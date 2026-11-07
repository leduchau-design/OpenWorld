"""P6 tests: hard per-donor risk cap, censored returns and W3 negative controls."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"benchmarks"))
from openworld_superkernel.risk_budget import CAP, POLICIES, DonorBudget, draw
from p6_risk_budget import REGIMES, FEEDBACK, evaluate, run_case, would_return


class TestRiskBudget(unittest.TestCase):
    def test_donor_cap_is_hard_before_issuing_fifth_unrepaid_gift(self):
        b=DonorBudget("always_offer")
        for r in range(CAP):
            self.assertTrue(b.may_issue(8))
            b.accepted(r)
            b.observed_outcome(r, False, r)
        self.assertEqual(b.exposure,CAP)
        self.assertFalse(b.may_issue(8))
        self.assertFalse(b.choose(1,5,"a10",8))
        self.assertEqual(b.blocked,1)
        with self.assertRaises(AssertionError):
            b.accepted(5)

    def test_no_credit_from_unknown_or_missing_feedback(self):
        b=DonorBudget("random_probe")
        for r in range(CAP):
            b.accepted(r)
        self.assertEqual(b.exposure,CAP)
        self.assertFalse(b.may_issue(8))
        self.assertEqual(len(b.observed),0)
        with self.assertRaises(AssertionError):
            b.observed_outcome(19,True,19)
        b.observed_outcome(0,True,5)
        self.assertEqual(b.exposure,CAP-1)
        self.assertTrue(b.may_issue(8))

    def test_confirmed_returns_release_reserved_budget(self):
        b=DonorBudget("always_offer")
        for r in range(20):
            self.assertTrue(b.may_issue(2))
            b.accepted(r)
            b.observed_outcome(r,True,r)
        self.assertEqual(b.peak_exposure,1)
        self.assertEqual(b.known_bad,0)
        self.assertEqual(len(b.observed),20)

    def test_uncapped_reference_is_explicit_only(self):
        b=DonorBudget("uncapped_offer")
        for r in range(8):
            self.assertTrue(b.may_issue(8))
            b.accepted(r)
        self.assertEqual(b.exposure,8)
        self.assertGreater(b.exposure,CAP)

    def test_zero_resource_denies_all_variants(self):
        for p in POLICIES:
            self.assertFalse(DonorBudget(p).choose(3,1,"a10",0))

    def test_fixed_and_seeded_probe_schedules_are_distinct(self):
        fixed=DonorBudget("fixed_probe")
        seeded=DonorBudget("random_probe")
        # Bootstrap with two negative actually observed returns.
        for b in (fixed,seeded):
            for r in (0,1):
                b.accepted(r);b.observed_outcome(r,False,r)
        fixed_decisions=[fixed.choose(9101,r,"a10",8) for r in range(2,20)]
        seeded_decisions=[seeded.choose(9101,r,"a10",8) for r in range(2,20)]
        self.assertNotEqual(fixed_decisions,seeded_decisions)
        self.assertEqual(draw(9101,3,"a10","probe"),draw(9101,3,"a10","probe"))

    def test_pub_schedule_partner_challenges_fixed_schedule(self):
        self.assertTrue(would_return("probe_gamer",9101,0,"a10"))
        self.assertTrue(would_return("probe_gamer",9101,5,"a10"))
        self.assertFalse(would_return("probe_gamer",9101,6,"a10"))
        self.assertEqual(would_return("probe_gamer",9101,5,"a10"),
                         would_return("probe_gamer",11111,5,"a10"))

    def test_hostile_cap_is_respected_in_actual_w3_actions(self):
        for p in POLICIES:
            x=run_case(p,"hostile","immediate",seed=10101)
            self.assertEqual(x["ticks"],40)
            self.assertEqual(x["registered_agents"],30)
            if p!="uncapped_offer":
                self.assertLessEqual(x["max_unreturned_or_pending"],CAP)
                self.assertLessEqual(x["donations"],10*CAP)
            self.assertEqual(x["returns"],0)
            self.assertLessEqual(x["net_reward"],0)

    def test_no_action_world_and_actual_resource_replay(self):
        x=run_case("hold","collapse","immediate",seed=10101)
        self.assertEqual(x["donations"],0)
        self.assertEqual(x["returns"],0)
        self.assertEqual(x["net_reward"],0)
        self.assertEqual(x["ticks"],40)

    def test_delayed_or_missing_return_never_invents_learning_feedback(self):
        a=run_case("always_offer","cooperative","immediate",seed=10101)
        b=run_case("always_offer","cooperative","delayed_censored",seed=10101)
        self.assertEqual(a["returns"],a["donations"])
        self.assertEqual(b["returns"],b["donations"])
        self.assertGreater(b["unresolved"],0)
        self.assertLess(b["policy_observations"],b["donations"])
        self.assertLessEqual(b["max_unreturned_or_pending"],CAP)

    def test_known_real_W3_receipt_but_no_notification_retains_reserve(self):
        x=run_case("always_offer","cooperative","delayed_censored",seed=10102)
        self.assertGreater(x["unresolved"],0)
        self.assertEqual(x["known_unreturned"],0)
        self.assertLessEqual(x["max_unreturned_or_pending"],CAP)

    def test_reproducible_excluding_wall_clock_timing(self):
        a=run_case("change_point","mixed","delayed_censored",seed=10103)
        b=run_case("change_point","mixed","delayed_censored",seed=10103)
        for key in ("donations","returns","probes","unresolved","known_unreturned",
                    "net_reward","phase_rewards","cap_denials"):
            self.assertEqual(a[key],b[key])

    def test_invalid_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            DonorBudget("arbitrary")
        with self.assertRaises(ValueError):
            run_case("random_probe","nonsense","immediate",seed=1)
        with self.assertRaises(ValueError):
            run_case("random_probe","hostile","unknown",seed=1)
        with self.assertRaises(ValueError):
            evaluate(seeds=11)
        with self.assertRaises(ValueError):
            evaluate(regimes=("hostile","hostile"))

    @unittest.skipUnless(os.environ.get("OPENWORLD_SLOW_TESTS") == "1",
                         "slow multi-seed research benchmark; set OPENWORLD_SLOW_TESTS=1")
    def test_full_ten_seed_matrix_without_claiming_policy_winner(self):
        data=evaluate()
        cases=data["cases"]
        self.assertEqual(len(cases),10*len(POLICIES)*len(REGIMES)*len(FEEDBACK))
        self.assertEqual(len({c["seed"] for c in cases}),10)
        for c in cases:
            self.assertEqual(c["ticks"],40)
            self.assertEqual(c["active_donors"],10)
            if c["policy"]!="uncapped_offer":
                self.assertLessEqual(c["max_unreturned_or_pending"],CAP)
            self.assertLessEqual(c["returns"],c["donations"])
        for seed in range(10101,10111):
            subset=[c for c in cases if c["seed"]==seed]
            self.assertEqual(len({c["world_initial_hash"] for c in subset}),1)
        print("P6_MEASURED_META="+json.dumps({
            "cases":len(cases),"seeds":10,"regimes":list(REGIMES),
            "feedback":list(FEEDBACK),"policies":list(POLICIES),
            "environment":data["environment"],
            "wall_seconds":data["wall_seconds"]},sort_keys=True),flush=True)
        for item in cases:
            print("P6_MEASURED_CASE="+json.dumps(item,sort_keys=True),flush=True)

    def test_cli_small_json(self):
        cli=ROOT/"benchmarks"/"p6_risk_budget.py"
        p=subprocess.run([sys.executable,str(cli),"--seeds","1"],
                         capture_output=True,text=True,timeout=60)
        self.assertEqual(p.returncode,0,p.stderr[-1000:])
        result=json.loads(p.stdout)
        self.assertEqual(result["schema"],"openworld.p6.capped-probe-experiment.v0")
        self.assertEqual(len(result["cases"]),len(POLICIES)*len(REGIMES)*len(FEEDBACK))


if __name__=="__main__":
    unittest.main()
