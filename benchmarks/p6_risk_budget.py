"""P6: bounded W3 donation risk with delayed, censored outcome notifications.

A pure synthetic fixture: no new owner rights, network trust, actual economics,
or strategically learning partner. W3 holds authoritative SIMULATED transfers.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
import resource
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from p2_stateful_cooperation import OPPORTUNITIES
from p3_mutual_learning_w3 import _exchange, make_router
from p5_risk_aware import genesis_world, partner_returns
from openworld_superkernel.risk_budget import CAP, POLICIES, DonorBudget, draw
from openworld_superkernel.world_fixture import verify_replay

REGIMES = ("cooperative", "hostile", "collapse", "recovery", "mixed", "probe_gamer")
FEEDBACK = ("immediate", "delayed_censored")
SCHEMA = "openworld.p6.capped-probe-experiment.v0"


def would_return(regime: str, seed: int, origin: int, recipient: str) -> bool:
    if regime not in REGIMES or not 0 <= origin < 20:
        raise ValueError("unknown partner regime")
    # The test opponent recognizes the PUBLIC fixed fifth-round schedule,
    # not hidden policy state, and selectively returns on those rounds.
    if regime == "probe_gamer":
        return origin in (0, 1) or origin % 5 == 0
    return partner_returns(regime, seed, origin, recipient)


def receipt_due(feedback: str, seed: int, origin: int, recipient: str) -> int:
    if feedback not in FEEDBACK:
        raise ValueError("unknown feedback channel")
    return (origin if feedback == "immediate"
            else origin + 1 + draw(seed, origin, recipient, "delay") % 2)


def receipt_dropped(feedback: str, seed: int, origin: int, recipient: str) -> bool:
    if feedback not in FEEDBACK:
        raise ValueError("unknown feedback channel")
    return feedback == "delayed_censored" and (
        draw(seed, origin, recipient, "drop") % 7 == 0)


def run_case(policy: str, regime: str, feedback: str, *, seed: int) -> dict:
    if (policy not in POLICIES or regime not in REGIMES or feedback not in FEEDBACK
            or type(seed) is not int or not 0 <= seed < 2**31):
        raise ValueError("invalid P6 scenario")
    router, tokens = make_router()
    genesis = genesis_world(seed)
    world = genesis
    budgets = {op.actor: DonorBudget(policy) for op in OPPORTUNITIES}
    # W3 return is immediate; only the *notification to the policy* is
    # delayed/lost in the second feedback scenario. A lost notification keeps
    # the transfer reserved, even if the W3 state shows a return.
    notices: list[tuple[int, int, str, bool, bool]] = []
    first_half: list[float] = []
    last_half: list[float] = []
    accepted_donations = accepted_returns = 0
    intervals = []
    worst_resource_exposure = 0
    for rnd in range(20):
        # Drain only delivered notices, never consult hidden future outcomes.
        for due, origin, donor, returned, dropped in tuple(notices):
            if due == rnd:
                if not dropped:
                    budgets[donor].observed_outcome(origin, returned, rnd)
                notices.remove((due, origin, donor, returned, dropped))
        balance = dict(world.balances)
        asks, selected = [], []
        for op in OPPORTUNITIES:
            if budgets[op.actor].choose(seed, rnd, op.recipient, balance[op.actor]):
                if not budgets[op.actor].may_issue(balance[op.actor]):
                    raise AssertionError("cap bypass before W3 invocation")
                asks.append(_exchange(
                    world, tokens, actor=op.actor, recipient=op.recipient,
                    source=op.source_group, target=op.target_group,
                    round_index=rnd, label="p6-give"))
                selected.append(op)
        t0 = time.perf_counter()
        outgoing = router.advance(world, exchanges=tuple(asks), max_actions=10)
        intervals.append(time.perf_counter()-t0)
        if outgoing.state.rejected:
            raise AssertionError("unexpected W3 transfer rejection")
        world = outgoing.state.world
        accepted_ids = set(outgoing.state.accepted)
        for op in selected:
            if f"p3-p6-give-{rnd}-{op.actor}" not in accepted_ids:
                raise AssertionError("unrecorded gift")
            budgets[op.actor].accepted(rnd)
        accepted_donations += len(selected)
        responses = [op for op in selected if would_return(
            regime, seed, rnd, op.recipient)]
        replies = [
            _exchange(world, tokens, actor=op.recipient, recipient=op.actor,
                      source=op.target_group, target=op.source_group,
                      round_index=rnd, label="p6-back")
            for op in responses
        ]
        t0 = time.perf_counter()
        returned = router.advance(world, exchanges=tuple(replies), max_actions=10)
        intervals.append(time.perf_counter()-t0)
        if returned.state.rejected:
            raise AssertionError("unexpected W3 return rejection")
        world = returned.state.world
        back_ids = set(returned.state.accepted)
        if len(back_ids) != len(responses):
            raise AssertionError("W3 return not committed")
        accepted_returns += len(responses)
        reward = (-0.25*len(selected)+0.85*len(responses))/len(OPPORTUNITIES)
        (first_half if rnd < 10 else last_half).append(reward)
        for op in selected:
            success = f"p3-p6-back-{rnd}-{op.recipient}" in back_ids
            due = receipt_due(feedback, seed, rnd, op.recipient)
            dropped = receipt_dropped(feedback, seed, rnd, op.recipient)
            if due == rnd:
                if not dropped:
                    budgets[op.actor].observed_outcome(rnd, success, rnd)
            else:
                notices.append((due, rnd, op.actor, success, dropped))
        for ledger in budgets.values():
            if policy != "uncapped_offer" and ledger.exposure > CAP:
                raise AssertionError("hard donor exposure cap breached")
        worst_resource_exposure = max(worst_resource_exposure,
                                      max(x.peak_exposure for x in budgets.values()))
    if not verify_replay(genesis, world) or world.tick != 40:
        raise AssertionError("P6 world replay/tick failed")
    if sum(v for _,v in world.balances) != sum(v for _,v in genesis.balances):
        raise AssertionError("P6 resource conservation failed")
    if any(e.provenance != "SIMULATED" for e in world.events):
        raise AssertionError("P6 invalid evidence provenance")
    return {
        "policy":policy,"regime":regime,"feedback":feedback,"seed":seed,
        "world_initial_hash":genesis.fingerprint(),
        "registered_agents":30,"active_donors":10,"ticks":40,
        "donations":accepted_donations,"returns":accepted_returns,
        "net_reward":statistics.fmean(first_half+last_half),
        "phase_rewards":[statistics.fmean(first_half),statistics.fmean(last_half)],
        "worst_phase_reward":min(statistics.fmean(first_half),statistics.fmean(last_half)),
        "max_unreturned_or_pending":worst_resource_exposure,
        "known_unreturned":sum(x.known_bad for x in budgets.values()),
        "unresolved":sum(len(x.pending) for x in budgets.values()),
        "notices_waiting":len(notices),
        "probes":sum(x.probes for x in budgets.values()),
        "cap_denials":sum(x.blocked for x in budgets.values()),
        "policy_observations":sum(len(x.observed) for x in budgets.values()),
        "router_p95_seconds":sorted(intervals)[math.ceil(len(intervals)*.95)-1],
    }


def evaluate(*, start_seed: int = 10101, seeds: int = 10,
             policies: tuple[str,...] = POLICIES,
             regimes: tuple[str,...] = REGIMES,
             feedbacks: tuple[str,...] = FEEDBACK) -> dict:
    if (type(start_seed) is not int or type(seeds) is not int
            or not 0 <= start_seed < 2**31-10 or not 1 <= seeds <= 10
            or any(not isinstance(x,tuple) or not x or len(set(x)) != len(x)
                   for x in (policies,regimes,feedbacks))
            or any(p not in POLICIES for p in policies)
            or any(r not in REGIMES for r in regimes)
            or any(f not in FEEDBACK for f in feedbacks)):
        raise ValueError("invalid bounded evidence matrix")
    t0,c0=time.perf_counter(),time.process_time()
    cases=[run_case(p,r,f,seed=start_seed+i)
           for i in range(seeds) for r in regimes for f in feedbacks
           for p in policies]
    return {"schema":SCHEMA,"cases":cases,
            "environment":{"python":sys.version.split()[0],
                           "platform":platform.platform(),"cpu_count":os.cpu_count(),
                           "peak_rss_os_units":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                           "rss_units":"KiB on Linux; bytes on macOS"},
            "wall_seconds":time.perf_counter()-t0,
            "process_cpu_seconds":time.process_time()-c0}


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--seeds",type=int,default=10)
    ap.add_argument("--seed-start",type=int,default=10101)
    ap.add_argument("--out",type=Path)
    a=ap.parse_args()
    result=evaluate(seeds=a.seeds,start_seed=a.seed_start)
    output=json.dumps(result,sort_keys=True,separators=(",",":"))+"\n"
    if a.out: a.out.write_text(output,encoding="utf-8")
    else: print(output,end="")
