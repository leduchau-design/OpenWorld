"""P3 W3 multi-learner cooperation: twenty independently updated toy policies.

Research-only, one synthetic owner. Donors and receivers both choose actions;
each four-round episode persists for eight W3 ticks. Every accepted transfer
uses the existing guarded PopulationRouter, with exact W3 replay per episode.
No authentication provider, independent consent, untrusted code, general MARL,
or real resource economy. Rewards are explicitly designed for this toy task.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
import random
import statistics
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from p2_stateful_cooperation import (
    GROUPS, OPPORTUNITIES, OWNER, PRINCIPAL, build_world, deterministic_seed,
    make_router as make_p2_router, target_summary,
)
from openworld_superkernel.population_links import (
    Exchange, PopulationLink, PopulationRouter,
)
from openworld_superkernel.world_fixture import Action, World, verify_replay

METHODS = ("hold", "always_reciprocate", "no_summary", "group_mean",
           "histogram4", "ecf")
LEARNED = METHODS[2:]
FORMAT = "openworld.p3.mutual-learning.v0"


class AgentBandit:
    """Two-arm independent value estimate updated from own observed reward."""

    def __init__(self):
        self.q: dict[tuple[int, ...], list[list[float]]] = {}
        self.updates = 0

    def choose(self, context: tuple[int, ...], *, seed: int, epsilon: float) -> int:
        if not isinstance(context, tuple) or not 0 <= epsilon <= 1:
            raise ValueError("bad policy input")
        rng = random.Random(seed)
        if epsilon and rng.random() < epsilon:
            return rng.randrange(2)
        arms = self.q.get(context)
        if arms is None:
            return 0
        a = [s / n if n else 0.0 for n, s in arms]
        return int(a[1] > a[0])

    def update(self, context: tuple[int, ...], action: int, reward: float) -> None:
        if action not in (0, 1) or not -1.0 <= reward <= 1.0:
            raise ValueError("invalid reward or action")
        arm = self.q.setdefault(context, [[0.0, 0.0], [0.0, 0.0]])[action]
        arm[0] += 1
        arm[1] += reward
        self.updates += 1


def make_router():
    """Use only pre-existing local same-owner links and grants, adding no power."""
    old, write_tokens = make_p2_router()
    current = tuple(old.links.values())
    links = tuple(
        PopulationLink(link.source, link.destination, ("transfer",),
                       max_transfer=1, max_actions_per_tick=5)
        for link in current
    )
    # Both reverse directions exist in P2 but previously allowed only a signal.
    # This new local contract is host-specified and has no cross-owner rights.
    router = PopulationRouter(old.gateway, old.populations, links)
    return router, write_tokens


def donor_context(world: World, actor: str, destination: str,
                  method: str, *, previous_return: int) -> tuple[int, ...]:
    """Own resources and own prior outcome; group feature only in same-owner host."""
    own = min(12, dict(world.balances)[actor])
    summary = target_summary(world, destination, method) if method in LEARNED else ()
    return (min(6, own // 2), int(previous_return)) + summary


def receiver_context(world: World, recipient: str, *, got_offer: bool) -> tuple[int, ...]:
    """Own resource level and whether the immediately prior W3 tick donated."""
    return (min(6, dict(world.balances)[recipient] // 2), int(got_offer))


def _exchange(world: World, tokens: dict[str, str], *,
              actor: str, recipient: str, source: str, target: str,
              round_index: int, label: str) -> Exchange:
    return Exchange(
        source, target,
        Action(f"p3-{label}-{round_index}-{actor}", world.tick, OWNER,
               actor, recipient, "transfer", 1),
        tokens[actor], tokens[recipient],
    )


def run_episode(router: PopulationRouter, tokens: dict[str, str],
                world: World, method: str,
                policies: dict[str, AgentBandit] | None, *,
                seed: int, episode: int, rounds: int = 4,
                training: bool = False, receiver_override: str | None = None,
                observation_mode: str = "full",
                measure_timing: bool = False) -> dict:
    """Freeze each role's choices before its W3 tick; feedback after response tick.

    Donors are OPPORTUNITIES.actor and receivers are OPPORTUNITIES.recipient.
    A receiver observes only its own resources and whether a transfer to it
    was accepted; there are no oracle needs, unseen opponents or private W1.
    """
    if method not in METHODS or type(rounds) is not int or not 2 <= rounds <= 8:
        raise ValueError("invalid episode config")
    if (receiver_override not in (None, "fixed_hold", "fixed_reciprocate", "mixed")
            or (training and receiver_override is not None)):
        raise ValueError("partner override is holdout-only and must be supported")
    if observation_mode not in ("full", "binary") or (
            observation_mode == "binary" and method != "no_summary"):
        raise ValueError("binary local observation applies only to no_summary")
    if type(measure_timing) is not bool:
        raise TypeError("measure_timing must be a boolean")
    if method in LEARNED and policies is None:
        raise ValueError("learned policy map required")
    genesis = world
    active = tuple(a for o in OPPORTUNITIES for a in (o.actor, o.recipient))
    if len(active) != len(set(active)) or len(active) != 20:
        raise AssertionError("exactly 20 independent learning actors expected")
    if policies is not None and set(policies) != set(active):
        raise ValueError("policy roster must exactly cover the 20 decision agents")

    last_return = {op.actor: 0 for op in OPPORTUNITIES}
    donor_rewards = []
    receiver_rewards = []
    offered_count = returned_count = accepted_count = 0
    fingerprints = []
    tick_times = []
    rejected_count = 0
    for round_index in range(rounds):
        # DONOR PHASE: all decide without within-phase reward access.
        offers = []
        donor_decisions = []
        for op in OPPORTUNITIES:
            own_balance = dict(world.balances)[op.actor]
            context = (donor_context(world, op.actor, op.target_group, method,
                                     previous_return=last_return[op.actor])
                       if method in LEARNED else ())
            if observation_mode == "binary":
                context = (int(own_balance >= 2), last_return[op.actor])
            if method == "hold":
                action = 0
            elif method == "always_reciprocate":
                action = 1
            else:
                action = policies[op.actor].choose(
                    context, seed=deterministic_seed(seed, episode, round_index,
                                                     op.actor, "donor"),
                    epsilon=0.20 if training else 0,
                )
            # Safety layer prevents overdraw, independently of the learned policy.
            action = int(bool(action) and own_balance >= 1)
            donor_decisions.append((op, context, action))
            if action:
                offers.append(_exchange(
                    world, tokens, actor=op.actor, recipient=op.recipient,
                    source=op.source_group, target=op.target_group,
                    round_index=round_index, label="give",
                ))
        started = time.perf_counter() if measure_timing else 0.0
        first = router.advance(world, exchanges=tuple(offers), max_actions=10)
        if measure_timing:
            tick_times.append(time.perf_counter() - started)
        rejected_count += len(first.state.rejected)
        world = first.state.world
        accepted = set(first.state.accepted)
        offered_count += len(offers)
        accepted_count += len(accepted)
        fingerprints.append(world.fingerprint())

        # RECEIVER PHASE: each independently chooses whether to reciprocate.
        # Its only cross-agent signal is the authorized W3 transfer to itself.
        responses = []
        receiver_decisions = []
        for op in OPPORTUNITIES:
            got = f"p3-give-{round_index}-{op.actor}" in accepted
            context = receiver_context(world, op.recipient, got_offer=got)
            if observation_mode == "binary":
                context = (int(dict(world.balances)[op.recipient] >= 2), int(got))
            if receiver_override == "fixed_hold":
                action = 0
            elif receiver_override == "fixed_reciprocate":
                action = int(got)
            elif receiver_override == "mixed":
                action = int(bool(got) and
                             deterministic_seed(seed, episode, round_index,
                                                op.recipient, "partner-shift") % 2 == 0)
            elif method == "hold":
                action = 0
            elif method == "always_reciprocate":
                action = int(got)
            else:
                action = policies[op.recipient].choose(
                    context, seed=deterministic_seed(seed, episode, round_index,
                                                     op.recipient, "receiver"),
                    epsilon=0.20 if training else 0,
                )
            action = int(bool(action) and dict(world.balances)[op.recipient] >= 1)
            receiver_decisions.append((op, context, action, got))
            if action:
                responses.append(_exchange(
                    world, tokens, actor=op.recipient, recipient=op.actor,
                    source=op.target_group, target=op.source_group,
                    round_index=round_index, label="back",
                ))
        started = time.perf_counter() if measure_timing else 0.0
        second = router.advance(world, exchanges=tuple(responses), max_actions=10)
        if measure_timing:
            tick_times.append(time.perf_counter() - started)
        rejected_count += len(second.state.rejected)
        world = second.state.world
        back = set(second.state.accepted)
        returned_count += len(back)
        fingerprints.append(world.fingerprint())

        # Both role rewards are functions of accepted, real SIMULATED W3
        # transfer IDs, not latent needs or an oracle's preferred action.
        for (op, ctx, offer), (_, recv_ctx, reply, got) in zip(
                donor_decisions, receiver_decisions):
            donation = f"p3-give-{round_index}-{op.actor}" in accepted
            returned = f"p3-back-{round_index}-{op.recipient}" in back
            donor_reward = (0.85 if donation and returned else 0.0) - (
                0.25 if donation else 0.0)
            receiver_reward = (
                (0.70 if donation and returned else 0.0)
                - (0.15 if returned else 0.0)
                - (0.20 if donation and not returned else 0.0)
            )
            donor_rewards.append(donor_reward)
            receiver_rewards.append(receiver_reward)
            last_return[op.actor] = int(returned)
            if training and policies is not None:
                policies[op.actor].update(ctx, offer, donor_reward)
                policies[op.recipient].update(recv_ctx, reply, receiver_reward)
    if not verify_replay(genesis, world):
        raise AssertionError("world replay failed")
    if sum(dict(world.balances).values()) != sum(dict(genesis.balances).values()):
        raise AssertionError("resource conservation failed")
    if any(e.provenance != "SIMULATED" for e in world.events):
        raise AssertionError("unsupported provenance")
    return {
        "ticks": world.tick,
        "initial_fingerprint": genesis.fingerprint(),
        "final_fingerprint": world.fingerprint(),
        "total_resources": sum(dict(world.balances).values()),
        "offers": offered_count,
        "accepted_offers": accepted_count,
        "returns": returned_count,
        "donor_reward_mean": statistics.fmean(donor_rewards),
        "receiver_reward_mean": statistics.fmean(receiver_rewards),
        "joint_reward_mean": statistics.fmean(donor_rewards + receiver_rewards),
        "per_round_fingerprints": tuple(fingerprints),
        "rejected_actions": rejected_count,
        **({"tick_router_wall_seconds": tuple(tick_times)} if measure_timing else {}),
    }


def run_case(method: str, *, seed: int, train_episodes: int = 20,
             holdout_episodes: int = 8, rounds: int = 4) -> dict:
    if (method not in METHODS or type(seed) is not int or seed < 0 or
            type(train_episodes) is not int or not 1 <= train_episodes <= 60 or
            type(holdout_episodes) is not int or not 1 <= holdout_episodes <= 20 or
            type(rounds) is not int or not 2 <= rounds <= 8):
        raise ValueError("bounded P3 configuration required")
    router, tokens = make_router()
    actors = tuple(a for op in OPPORTUNITIES for a in (op.actor, op.recipient))
    policies = {a: AgentBandit() for a in actors} if method in LEARNED else None
    train_results = []
    holdout = []
    for phase, count in (("train", train_episodes), ("holdout", holdout_episodes)):
        for episode in range(count):
            world_seed = seed if phase == "train" else seed + 1000003
            world, _ = build_world(seed=world_seed, episode=episode)
            result = run_episode(
                router, tokens, world, method, policies, seed=world_seed,
                episode=episode, rounds=rounds,
                training=(phase == "train" and method in LEARNED),
            )
            (train_results if phase == "train" else holdout).append(result)
    updates = sum(p.updates for p in policies.values()) if policies else 0
    expected_updates = 20 * rounds * train_episodes if policies else 0
    if updates != expected_updates:
        raise AssertionError("holdout changed policy updates")
    return {
        "method": method, "seed": seed, "holdout_seed": seed + 1000003,
        "registered_agents": 30, "learning_agents": 20 if policies else 0,
        "decision_agents": 20, "rounds": rounds, "ticks_per_episode": rounds * 2,
        "training_episodes": train_episodes,
        "holdout_episodes": holdout_episodes,
        "train_updates": updates, "train_donor_reward":
            statistics.fmean(x["donor_reward_mean"] for x in train_results),
        "holdout_donor_reward":
            statistics.fmean(x["donor_reward_mean"] for x in holdout),
        "holdout_receiver_reward":
            statistics.fmean(x["receiver_reward_mean"] for x in holdout),
        "holdout_joint_reward":
            statistics.fmean(x["joint_reward_mean"] for x in holdout),
        "holdout_offers": sum(x["offers"] for x in holdout),
        "holdout_accepted_offers": sum(x["accepted_offers"] for x in holdout),
        "holdout_returns": sum(x["returns"] for x in holdout),
        "holdout_initial_fingerprints":
            [x["initial_fingerprint"] for x in holdout],
        "holdout_final_fingerprints":
            [x["final_fingerprint"] for x in holdout],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--train-episodes", type=int, default=20)
    p.add_argument("--holdout-episodes", type=int, default=8)
    p.add_argument("--rounds", type=int, default=4)
    p.add_argument("--seed-start", type=int, default=6101)
    p.add_argument("--seeds", type=int, default=3)
    p.add_argument("--methods", nargs="+", choices=METHODS, default=METHODS)
    args = p.parse_args()
    if not 1 <= args.seeds <= 5:
        p.error("seed count must be 1..5")
    started = time.perf_counter()
    cases = [run_case(method, seed=args.seed_start+i,
                      train_episodes=args.train_episodes,
                      holdout_episodes=args.holdout_episodes,
                      rounds=args.rounds)
             for i in range(args.seeds) for method in args.methods]
    print(json.dumps({
        "schema": FORMAT, "scope": "20 independently learned toy actor policies; "
          "8-tick W3 world per episode; synthetic one-owner reset scenarios",
        "wall_seconds": time.perf_counter()-started,
        "cases": cases,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
