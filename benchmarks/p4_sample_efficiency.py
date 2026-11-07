"""P4: sample-efficiency and partner-shift ablations in the existing W3 fixture.

No new policies run outside the trusted offline host. Shared-by-role policies
pool chosen-action reward but do not inherit resource grants or agent identity.
All scenarios are SIMULATED, single-owner and non-deployable.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from p2_stateful_cooperation import OPPORTUNITIES, build_world, deterministic_seed
from p3_mutual_learning_w3 import AgentBandit, make_router, run_episode
from openworld_superkernel.world_fixture import Agent, create_world

MODELS = ("fixed_hold", "fixed_cooperate", "independent_full",
          "independent_compact", "shared_full", "shared_compact",
          "shared_histogram", "shared_ecf")
LEARNED = MODELS[2:]
PARTNERS = ("native", "fixed_hold", "fixed_reciprocate", "mixed")
REGIMES = ("original", "shuffled")
SCHEMA = "openworld.p4.sample-efficiency-partner-shift.v0"
ACTORS = tuple(actor for op in OPPORTUNITIES for actor in (op.actor, op.recipient))
if len(ACTORS) != 20 or len(set(ACTORS)) != 20:
    raise RuntimeError("P4 requires 20 distinct donor and recipient actors")


def plan(model: str) -> tuple[str, str, bool]:
    if model not in MODELS:
        raise ValueError("unknown learning configuration")
    if model == "fixed_hold":
        return ("hold", "full", False)
    if model == "fixed_cooperate":
        return ("always_reciprocate", "full", False)
    if model == "independent_compact":
        return ("no_summary", "binary", False)
    if model == "shared_compact":
        return ("no_summary", "binary", True)
    if model == "shared_histogram":
        return ("histogram4", "full", True)
    if model == "shared_ecf":
        return ("ecf", "full", True)
    return ("no_summary", "full", model.startswith("shared_"))


def policies_for(model: str) -> dict[str, AgentBandit] | None:
    _, _, shared = plan(model)
    if model not in LEARNED:
        return None
    if shared:
        donors, recipients = AgentBandit(), AgentBandit()
        return {actor: (donors if i % 2 == 0 else recipients)
                for i, actor in enumerate(ACTORS)}
    return {actor: AgentBandit() for actor in ACTORS}


def distinct_policy_objects(policies: dict[str, AgentBandit] | None):
    if policies is None:
        return ()
    return tuple({id(p): p for p in policies.values()}.values())


def policy_snapshot(policies: dict[str, AgentBandit] | None) -> str:
    """Hash every actor's policy content; tuple contexts are not JSON object keys."""
    if policies is None:
        return "fixed"
    rows = []
    for agent in sorted(policies):
        p = policies[agent]
        contexts = [(list(ctx), tuple(tuple(float(v) for v in arm) for arm in arms))
                    for ctx, arms in sorted(p.q.items())]
        rows.append((agent, p.updates, contexts))
    return sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def training_diagnostics(policies: dict[str, AgentBandit] | None) -> dict:
    objects = distinct_policy_objects(policies)
    counts = [sum(int(arm[0]) for arm in arms)
              for p in objects for arms in p.q.values()]
    return {
        "distinct_policy_tables": len(objects),
        "total_updates": sum(p.updates for p in objects),
        "table_context_keys": len(counts),
        "contexts_with_fewer_than_two_visits": sum(v < 2 for v in counts),
        "median_visits_per_context": statistics.median(counts) if counts else 0,
    }


def world_for(seed: int, episode: int, regime: str):
    """Reassign integer resource balances *within group*, preserving totals.

    Group 1 includes both receivers and donors: changing where balances sit can
    break an assumed policy while leaving its group mean unchanged.
    """
    if regime not in REGIMES:
        raise ValueError("unknown population regime")
    original, mode = build_world(seed=seed, episode=episode)
    if regime == "original":
        return original
    balances = dict(original.balances)
    for group in range(3):
        ids = [f"a{i:02d}" for i in range(group * 10, (group + 1) * 10)]
        permuted = [balances[a] for a in ids]
        random.Random(deterministic_seed(seed, episode, regime, group)).shuffle(permuted)
        for a, amount in zip(ids, permuted):
            balances[a] = amount
    # Changing genesis via create_world is permitted in an *offline fixture*.
    # Actual subsequent transfers still pass through the guarded W3 gateway.
    agents = tuple(
        Agent(a.agent_id, a.owner_id, a.region, balances[a.agent_id])
        for a in original.agents
    )
    edges = tuple((o.actor, o.recipient) for o in OPPORTUNITIES)
    modified = create_world(agents, edges, seed=original.seed)
    if (sum(dict(modified.balances).values()) !=
            sum(dict(original.balances).values())):
        raise AssertionError("initial population shift created resources")
    return modified


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def run_case(model: str, *, seed: int, train_episodes: int,
             holdout_episodes: int = 4, rounds: int = 4,
             partners: tuple[str, ...] = PARTNERS,
             regimes: tuple[str, ...] = REGIMES) -> dict:
    if (model not in MODELS or type(seed) is not int or not 0 <= seed < 2**31
            or type(train_episodes) is not int or not 1 <= train_episodes <= 128
            or type(holdout_episodes) is not int or not 1 <= holdout_episodes <= 20
            or type(rounds) is not int or not 2 <= rounds <= 8
            or not isinstance(partners, tuple) or not partners
            or len(set(partners)) != len(partners) or
            any(p not in PARTNERS for p in partners)
            or not isinstance(regimes, tuple) or not regimes
            or len(set(regimes)) != len(regimes) or
            any(r not in REGIMES for r in regimes)):
        raise ValueError("bounded P4 configuration required")
    method, observation_mode, _ = plan(model)
    router, tokens = make_router()
    policies = policies_for(model)
    updates_expected = 20 * rounds * train_episodes if policies else 0
    started_wall, started_cpu = time.perf_counter(), time.process_time()

    # Identical train seeds and initial W3 worlds for every model and budget.
    for episode in range(train_episodes):
        world = world_for(seed, episode, "original")
        run_episode(router, tokens, world, method, policies,
                    seed=seed, episode=episode, rounds=rounds, training=bool(policies),
                    observation_mode=observation_mode)
    diag = training_diagnostics(policies)
    if diag["total_updates"] != updates_expected:
        raise AssertionError("different number of learner update opportunities")
    frozen = policy_snapshot(policies)
    evaluated = []
    for regime in regimes:
        for partner in partners:
            scores = []
            world_hashes = []
            router_tick_latencies = []
            elapsed_full_episode = []
            for episode in range(holdout_episodes):
                world_seed = seed + 1_000_003
                world = world_for(world_seed, episode, regime)
                world_hashes.append(world.fingerprint())
                start = time.perf_counter()
                outcome = run_episode(
                    router, tokens, world, method, policies,
                    seed=world_seed, episode=episode, rounds=rounds,
                    training=False,
                    receiver_override=None if partner == "native" else partner,
                    observation_mode=observation_mode,
                    measure_timing=True,
                )
                elapsed_full_episode.append(time.perf_counter() - start)
                router_tick_latencies.extend(outcome["tick_router_wall_seconds"])
                scores.append(outcome)
            if policy_snapshot(policies) != frozen:
                raise AssertionError("holdout changed policy state")
            denom = holdout_episodes * rounds * len(OPPORTUNITIES)
            joint = statistics.fmean(x["joint_reward_mean"] for x in scores)
            donor = statistics.fmean(x["donor_reward_mean"] for x in scores)
            recv = statistics.fmean(x["receiver_reward_mean"] for x in scores)
            offered = sum(x["offers"] for x in scores)
            accepted = sum(x["accepted_offers"] for x in scores)
            returned = sum(x["returns"] for x in scores)
            rejected = sum(x["rejected_actions"] for x in scores)
            evaluated.append({
                "regime": regime, "partner": partner,
                "input_sha256": sha256("".join(world_hashes).encode()).hexdigest(),
                "donor_reward": donor, "receiver_reward": recv,
                "joint_reward": joint,
                "offers": offered, "accepted_transfers": accepted,
                "returns": returned, "rejected_actions": rejected,
                "return_rate_of_accepted":
                    returned / accepted if accepted else None,
                "accepted_per_decision": accepted / denom,
                "router_tick_p50_seconds":
                    statistics.median(router_tick_latencies),
                "router_tick_p95_seconds":
                    _percentile(router_tick_latencies, 0.95),
                "full_episode_p95_seconds": _percentile(elapsed_full_episode, 0.95),
            })
    if policy_snapshot(policies) != frozen:
        raise AssertionError("frozen policy modified during evaluation")
    return {
        "seed": seed, "model": model,
        "policy_family": method, "observation_mode": observation_mode,
        "train_episodes": train_episodes, "holdout_episodes": holdout_episodes,
        "registered_agents": 30, "decision_agents": 20,
        "rounds": rounds, "ticks_per_episode": rounds * 2,
        "training": diag, "holdout": evaluated,
        "elapsed_wall_seconds": time.perf_counter() - started_wall,
        "elapsed_cpu_seconds": time.process_time() - started_cpu,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--seed-start", type=int, default=8101)
    parser.add_argument("--budgets", type=int, nargs="+", default=(8, 32, 128))
    parser.add_argument("--holdout-episodes", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--models", nargs="+", choices=MODELS, default=MODELS)
    parser.add_argument("--partners", nargs="+", choices=PARTNERS, default=PARTNERS)
    parser.add_argument("--regimes", nargs="+", choices=REGIMES, default=REGIMES)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not (1 <= args.seeds <= 5 and 0 <= args.seed_start < 2**31 - 1_000_020
            and len(args.budgets) == len(set(args.budgets))
            and all(b in (8,32,128) for b in args.budgets)):
        parser.error("bounded seeds/budgets required")
    if not (1 <= args.holdout_episodes <= 20 and 2 <= args.rounds <= 8):
        parser.error("invalid episode budget")
    started = time.perf_counter()
    cases = [run_case(
        model, seed=args.seed_start + offset, train_episodes=budget,
        holdout_episodes=args.holdout_episodes, rounds=args.rounds,
        partners=tuple(args.partners), regimes=tuple(args.regimes),
    ) for offset in range(args.seeds)
        for budget in args.budgets for model in args.models]
    rss_max = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report = {
        "schema": SCHEMA,
        "scope": "offline same-owner W3, twenty policy decisions, no general MARL claim",
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "ru_maxrss_platform_units": rss_max,
            "ru_maxrss_units": "KiB on Linux; bytes on macOS",
        },
        "wall_seconds": time.perf_counter() - started,
        "cases": cases,
    }
    output = json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    if args.out is not None:
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
