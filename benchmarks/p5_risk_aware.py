"""P5: risk-aware abstention and capped probing under partner behavior changes.

Research-only, one synthetic owner, all transfers through the existing guarded
W3 PopulationRouter. Scripted receiver policies are not authenticated owners.
All policy updates use only accepted SIMULATED transfer/return events.
"""
from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass, field
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
from p2_stateful_cooperation import OPPORTUNITIES, OWNER, deterministic_seed
from p3_mutual_learning_w3 import make_router, _exchange
from openworld_superkernel.world_fixture import Agent, World, create_world, verify_replay

POLICIES = ("hold", "always_offer", "all_history", "risk_window")
REGIMES = ("cooperative", "hostile", "collapse", "recovery", "mixed")
SCHEMA = "openworld.p5.local-risk-probing.v0"
ROUND_COUNT = 20
SPLIT = 10
REWARD_GOOD = 0.60
REWARD_BAD = -0.25
BREAK_EVEN = 0.25 / 0.85


def _probability(regime: str, round_index: int) -> int:
    """Return integer partner response probability on 0..10000 scale."""
    if regime not in REGIMES or type(round_index) is not int or not 0 <= round_index < ROUND_COUNT:
        raise ValueError("invalid scripted partner regime")
    if regime == "cooperative":
        return 10000
    if regime == "hostile":
        return 0
    if regime == "mixed":
        return 5000
    if regime == "collapse":
        return 10000 if round_index < SPLIT else 0
    return 0 if round_index < SPLIT else 10000


def partner_returns(regime: str, seed: int, round_index: int, recipient: str) -> bool:
    """Fixed exogenous partner trial, independent of the donor's decisions."""
    # Derived from seed and recipient, not the policy name or observed donation,
    # so all methods share the same response potential outcomes.
    return deterministic_seed("p5-partner", seed, round_index, recipient) % 10000 < _probability(
        regime, round_index)


def _lower_wilson(successes: int, attempts: int, z: float = 1.0) -> float:
    """A cautious finite-window score, NOT a calibrated safety guarantee."""
    if type(successes) is not int or type(attempts) is not int or (
            attempts < 1 or not 0 <= successes <= attempts):
        raise ValueError("invalid observed Bernoulli counts")
    mean = successes / attempts
    zz = z * z
    return (mean + zz / (2 * attempts) -
            z * math.sqrt(mean * (1 - mean) / attempts + zz / (4 * attempts**2))) / (
                1 + zz / attempts)


@dataclass
class DonorPolicy:
    """One donor's local observed ledger; never includes partner's hidden type."""
    method: str
    history: list[int] = field(default_factory=list)
    recent: deque[int] = field(default_factory=lambda: deque(maxlen=3))
    observations: int = 0
    probes: int = 0

    def __post_init__(self) -> None:
        if self.method not in POLICIES:
            raise ValueError("unknown policy")

    def choose(self, round_index: int, available: int) -> tuple[bool, bool]:
        if type(round_index) is not int or not 0 <= round_index < ROUND_COUNT:
            raise ValueError("invalid decision round")
        if type(available) is not int or available < 0:
            raise ValueError("invalid local resources")
        if available == 0 or self.method == "hold":
            return False, False
        if self.method == "always_offer":
            return True, False
        if self.method == "all_history":
            # Initial optimistic prior (1 observed yes, 1 observed no).
            estimate = (1 + sum(self.history)) / (2 + len(self.history))
            return estimate > BREAK_EVEN, False
        # Explicit, bounded *probing* handles missing counterfactual feedback.
        # No partner response can be observed after abstention.
        probe = len(self.history) < 2 or round_index % 5 == 0
        recent = tuple(self.recent)
        reliable = (len(recent) >= 2 and
                    _lower_wilson(sum(recent), len(recent)) > BREAK_EVEN)
        decision = probe or reliable
        if decision and probe and not reliable:
            self.probes += 1
        return decision, bool(decision and probe and not reliable)

    def record(self, *, donated: bool, returned: bool) -> None:
        # Only a *committed accepted* W3 donation provides a partner sample.
        if returned and not donated:
            raise ValueError("cannot observe a return without a donation")
        if donated:
            result = int(returned)
            self.history.append(result)
            self.recent.append(result)
            self.observations += 1


def genesis_world(seed: int) -> World:
    """Enough resources to expose unreciprocated donations, but finite."""
    if type(seed) is not int or seed < 0:
        raise ValueError("invalid world seed")
    donor_ids = {op.actor for op in OPPORTUNITIES}
    recipient_ids = {op.recipient for op in OPPORTUNITIES}
    agents = tuple(
        Agent(f"a{i:02d}", OWNER, f"region-{i//10}",
              8 if f"a{i:02d}" in donor_ids else
              4 if f"a{i:02d}" in recipient_ids else 2)
        for i in range(30)
    )
    edges = tuple((op.actor, op.recipient) for op in OPPORTUNITIES)
    world = create_world(agents, edges, seed=seed)
    if len(agents) != 30 or len(donor_ids) != 10 or len(recipient_ids) != 10:
        raise AssertionError("invalid P5 population")
    return world


def run_case(policy: str, regime: str, *, seed: int) -> dict:
    if (policy not in POLICIES or regime not in REGIMES or
            type(seed) is not int or seed < 0 or seed >= 2**31):
        raise ValueError("invalid bounded P5 case")
    router, tokens = make_router()
    world = genesis_world(seed)
    genesis = world
    strategies = {op.actor: DonorPolicy(policy) for op in OPPORTUNITIES}
    events_per_phase = [[], []]
    offered = [0, 0]
    donations = [0, 0]
    returns = [0, 0]
    refused = [0, 0]
    probes = [0, 0]
    tick_latencies = []
    for round_index in range(ROUND_COUNT):
        phase = int(round_index >= SPLIT)
        before = dict(world.balances)
        batch = []
        decision_records = []
        for op in OPPORTUNITIES:
            act, is_probe = strategies[op.actor].choose(round_index, before[op.actor])
            decision_records.append((op, act, is_probe))
            if act:
                batch.append(_exchange(
                    world, tokens, actor=op.actor, recipient=op.recipient,
                    source=op.source_group, target=op.target_group,
                    round_index=round_index, label="p5-give"))
                offered[phase] += 1
                probes[phase] += int(is_probe)
        start = time.perf_counter()
        result = router.advance(world, exchanges=tuple(batch), max_actions=10)
        tick_latencies.append(time.perf_counter() - start)
        world = result.state.world
        accepted = set(result.state.accepted)
        if result.state.rejected:
            raise AssertionError("unexpected W3 donor transfer rejection")

        response_batch = []
        for op, proposed, _ in decision_records:
            donated = (f"p3-p5-give-{round_index}-{op.actor}" in accepted)
            if donated and partner_returns(regime, seed, round_index, op.recipient):
                response_batch.append(_exchange(
                    world, tokens, actor=op.recipient, recipient=op.actor,
                    source=op.target_group, target=op.source_group,
                    round_index=round_index, label="p5-back"))
        start = time.perf_counter()
        reply = router.advance(world, exchanges=tuple(response_batch), max_actions=10)
        tick_latencies.append(time.perf_counter() - start)
        world = reply.state.world
        accepted_return = set(reply.state.accepted)
        if reply.state.rejected:
            raise AssertionError("unexpected W3 return rejection")
        for op, proposed, _ in decision_records:
            donated = f"p3-p5-give-{round_index}-{op.actor}" in accepted
            returned = f"p3-p5-back-{round_index}-{op.recipient}" in accepted_return
            if returned and not donated:
                raise AssertionError("return event without accepted donation")
            strategies[op.actor].record(donated=donated, returned=returned)
            donations[phase] += int(donated)
            returns[phase] += int(returned)
            refused[phase] += int(donated and not returned)
            events_per_phase[phase].append(REWARD_GOOD if donated and returned
                                           else REWARD_BAD if donated else 0.0)
    if world.tick != 2 * ROUND_COUNT or not verify_replay(genesis, world):
        raise AssertionError("P5 state replay mismatch")
    if sum(v for _, v in world.balances) != sum(v for _, v in genesis.balances):
        raise AssertionError("resource conservation violated")
    if any(e.provenance != "SIMULATED" for e in world.events):
        raise AssertionError("unsupported event provenance")
    if any(p.observations != len(p.history) for p in strategies.values()):
        raise AssertionError("feedback leaked from non-donations")
    return {
        "policy": policy, "regime": regime, "seed": seed,
        "input_world_sha256": genesis.fingerprint(),
        "final_world_sha256": world.fingerprint(),
        "registered_agents": 30, "acting_donors": 10,
        "rounds": ROUND_COUNT, "ticks": world.tick,
        "phase_reward_per_decision": [statistics.fmean(x) for x in events_per_phase],
        "reward_per_decision": statistics.fmean(events_per_phase[0] + events_per_phase[1]),
        "offered_by_phase": offered, "accepted_by_phase": donations,
        "returned_by_phase": returns, "unreciprocated_by_phase": refused,
        "probes_by_phase": probes,
        "worst_phase_reward": min(statistics.fmean(x) for x in events_per_phase),
        "observed_feedback_count": sum(p.observations for p in strategies.values()),
        "router_tick_p50_seconds": statistics.median(tick_latencies),
        "router_tick_p95_seconds": sorted(tick_latencies)[math.ceil(.95 * len(tick_latencies)) - 1],
    }


def evaluate(*, seeds: int = 5, start: int = 9101,
             policies: tuple[str, ...] = POLICIES,
             regimes: tuple[str, ...] = REGIMES) -> dict:
    if (type(seeds) is not int or not 1 <= seeds <= 5 or
            type(start) is not int or not 0 <= start < 2**31 - seeds or
            not isinstance(policies, tuple) or not policies or
            len(set(policies)) != len(policies) or any(p not in POLICIES for p in policies)
            or not isinstance(regimes, tuple) or not regimes or
            len(set(regimes)) != len(regimes) or any(r not in REGIMES for r in regimes)):
        raise ValueError("bounded P5 evaluation parameters required")
    t0, cpu0 = time.perf_counter(), time.process_time()
    records = [run_case(p, r, seed=start+i) for i in range(seeds)
               for r in regimes for p in policies]
    return {
        "schema": SCHEMA,
        "environment": {
            "python": sys.version.split()[0], "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "ru_maxrss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "ru_maxrss_units": "KiB on Linux; bytes on macOS",
        },
        "registered_agents": 30, "acting_donors": 10,
        "rounds": ROUND_COUNT, "ticks_per_case": ROUND_COUNT*2,
        "policy_families": list(policies), "partner_regimes": list(regimes),
        "wall_seconds": time.perf_counter() - t0,
        "process_cpu_seconds": time.process_time() - cpu0,
        "cases": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--seed-start", type=int, default=9101)
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=POLICIES)
    parser.add_argument("--regimes", nargs="+", choices=REGIMES, default=REGIMES)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    data = evaluate(seeds=args.seeds, start=args.seed_start,
                    policies=tuple(args.policies), regimes=tuple(args.regimes))
    output = json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n"
    if args.out is None:
        print(output, end="")
    else:
        args.out.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
