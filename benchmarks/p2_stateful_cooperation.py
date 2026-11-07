"""P2 research: delayed-feedback contextual learning inside a replayable W3 world.

30 registered synthetic agents, 10 acting donors, two transfer boundaries.
A donation changes the receiver's next-tick ability to acknowledge assistance.
The trusted toy host supplies all requests and signed grants. No federation,
untrusted agent code, authenticated real-world evidence or general MARL claim.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import platform
import random
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openworld_superkernel.population_links import (
    Exchange, Population, PopulationLink, PopulationRouter,
)
from openworld_superkernel.population_repr import empirical_cf
from openworld_superkernel.trust_boundaries import CapabilityAuthority
from openworld_superkernel.world_fixture import Agent, Action, World, create_world, verify_replay
from openworld_superkernel.world_guard import GuardedWorldGateway

METHODS = ("rule_hold", "rule_transfer", "no_summary", "group_mean", "histogram4", "ecf")
TRAINABLE = METHODS[2:]
GROUPS = ("guild-0", "guild-1", "guild-2")
OWNER, PRINCIPAL = "synthetic-owner", "trusted-local-host"
SCHEMA = "openworld.p2.stateful-donation-learning.v0"


def deterministic_seed(*args: object) -> int:
    blob = json.dumps(args, separators=(",", ":"), sort_keys=True)
    return int.from_bytes(sha256(blob.encode()).digest()[:8], "big")


@dataclass(frozen=True)
class Opportunity:
    actor: str
    recipient: str
    source_group: str
    target_group: str


OPPORTUNITIES = tuple(
    [Opportunity(f"a{i:02d}", f"a{i+10:02d}", GROUPS[0], GROUPS[1])
     for i in range(5)] +
    [Opportunity(f"a{i+15:02d}", f"a{i+20:02d}", GROUPS[1], GROUPS[2])
     for i in range(5)]
)


def build_world(*, seed: int, episode: int) -> tuple[World, tuple[int, int]]:
    """Modes affect individual balances but NOT either target group's mean."""
    if type(seed) is not int or seed < 0 or type(episode) is not int or episode < 0:
        raise ValueError("invalid seed or episode")
    rng = random.Random(deterministic_seed(seed, episode, "modes"))
    needs = (rng.randrange(2), rng.randrange(2))
    # Each group's total is fixed across needy/funded modes.
    resources = [8] * 5 + [2] * 5
    resources += ([0] * 5 if needs[0] else [2] * 5)
    resources += ([8] * 5 if needs[0] else [6] * 5)
    resources += ([0] * 5 if needs[1] else [2] * 5)
    resources += ([4] * 5 if needs[1] else [2] * 5)
    agents = tuple(Agent(f"a{i:02d}", OWNER, f"region-{i//10}", resources[i])
                   for i in range(30))
    edges = tuple((op.actor, op.recipient) for op in OPPORTUNITIES)
    world = create_world(agents, edges, seed=seed)
    assert len(agents) == 30 and len(edges) == 10
    assert (sum(resources[10:20]), sum(resources[20:30])) == (40, 20)
    return world, needs


def make_router() -> tuple[PopulationRouter, dict[str, str]]:
    # The toy host is the single issuer and caller. Tokens are intentionally
    # NOT replayed or included in the W3 journal; this is not an audit receipt.
    authority = CapabilityAuthority(
        b"offline-p2-experiment-only-not-a-real-secret-of-anyone",
        issuer="p2-research", audience="local-w3",
    )
    now = int(time.time())
    tokens = {
        f"a{i:02d}": authority.issue(
            principal=PRINCIPAL, owner=OWNER, resource=f"a{i:02d}",
            action="write_agent", valid_from=now-10, expires_at=now+3000,
        )
        for i in range(30)
    }
    gateway = GuardedWorldGateway(
        authority, authenticated_principal=lambda: PRINCIPAL,
    )
    groups = tuple(Population(name, tuple(f"a{i:02d}" for i in range(
        g * 10, g * 10 + 10))) for g, name in enumerate(GROUPS))
    links = (
        PopulationLink(GROUPS[0], GROUPS[1], ("transfer",),
                       max_transfer=2, max_actions_per_tick=5),
        PopulationLink(GROUPS[1], GROUPS[2], ("transfer",),
                       max_transfer=2, max_actions_per_tick=5),
        PopulationLink(GROUPS[1], GROUPS[0], ("signal",),
                       max_actions_per_tick=5),
        PopulationLink(GROUPS[2], GROUPS[1], ("signal",),
                       max_actions_per_tick=5),
    )
    return PopulationRouter(gateway, groups, links), tokens


def target_summary(world: World, target_group: str, method: str) -> tuple[int, ...]:
    """Same-owner host aggregate, NEVER a public or private-data-safe API.

    Fixed int buckets permit simple tabular exploration, not a learned
    information bottleneck or a theoretical sufficiency claim.
    """
    if method not in TRAINABLE:
        raise ValueError("unsupported learned representation")
    group = int(target_group[-1])
    values = [v for agent, v in world.balances
              if group * 10 <= int(agent[1:]) < (group+1)*10]
    if len(values) != 10:
        raise AssertionError("invalid group roster")
    if method == "no_summary":
        return ()
    if method == "group_mean":
        return (int(round(statistics.fmean(values) * 10)),)
    if method == "histogram4":
        return tuple(sum(1 for v in values if low <= v < high)
                     for low, high in ((0,1), (1,3), (3,6), (6,100)))
    re, im = empirical_cf(tuple((float(x),) for x in values), (math.pi/4,))
    return (int(round(re * 100)), int(round(im * 100)))


class TabularBandit:
    """Two-action chosen-feedback learner; learns after the *second* world tick."""

    def __init__(self) -> None:
        self.table: dict[tuple[int, ...], list[list[float]]] = {}
        self.updates = 0

    def decide(self, context: tuple[int, ...], rng: random.Random,
               *, explore: float) -> int:
        if not 0 <= explore <= 1:
            raise ValueError("invalid exploration rate")
        if explore and rng.random() < explore:
            return rng.randrange(2)
        arms = self.table.get(context)
        if arms is None:
            return 0  # safety-oriented initial policy: do not transfer
        estimates = [(row[1] / row[0] if row[0] else 0.0) for row in arms]
        return int(estimates[1] > estimates[0])

    def update(self, context: tuple[int, ...], action: int, reward: float) -> None:
        if action not in (0, 1) or not math.isfinite(reward):
            raise ValueError("invalid feedback")
        arms = self.table.setdefault(context, [[0.,0.], [0.,0.]])
        arms[action][0] += 1
        arms[action][1] += reward
        self.updates += 1


def play_episode(router: PopulationRouter, tokens: dict[str, str],
                 world: World, method: str, learner: TabularBandit | None,
                 *, exploration_seed: int, train: bool = False
                 ) -> tuple[dict, World]:
    """All policy decisions freeze before tick 0. Rewards are revealed at tick 1."""
    if method not in METHODS or (method in TRAINABLE and learner is None):
        raise ValueError("invalid learning method")
    genesis = world
    rng = random.Random(exploration_seed)
    decisions = []
    for i, op in enumerate(OPPORTUNITIES):
        # The group summary is made by the same-owner trusted toy host.
        context = target_summary(world, op.target_group, method) if method in TRAINABLE else ()
        action = (0 if method == "rule_hold" else 1 if method == "rule_transfer"
                  else learner.decide(context, rng, explore=0.18 if train else 0))
        decisions.append((op, context, action))
    proposals = tuple(
        Exchange(op.source_group, op.target_group,
                 Action(f"p2-offer-{i}", world.tick, OWNER, op.actor,
                        op.recipient, "transfer", 2),
                 tokens[op.actor], tokens[op.recipient])
        for i, (op, _, action) in enumerate(decisions) if action == 1
    )
    first = router.advance(world, exchanges=proposals, max_actions=10)
    world = first.state.world
    accepted = set(first.state.accepted)
    # Receiver's next-tick action is a fixed rule and depends on its *current
    # W3 balance*, which may have changed because of donor policy.
    current = dict(world.balances)
    acknowledgements = tuple(
        Exchange(op.target_group, op.source_group,
                 Action(f"p2-ack-{i}", world.tick, OWNER, op.recipient,
                        op.actor, "signal", 0),
                 tokens[op.recipient], tokens[op.actor])
        for i, op in enumerate(OPPORTUNITIES) if current[op.recipient] >= 2
    )
    second = router.advance(world, exchanges=acknowledgements, max_actions=10)
    world = second.state.world
    confirmed = {e.actor for e in second.events_added if e.kind == "signal"}
    rewards = []
    for i, (op, context, action) in enumerate(decisions):
        transferred = f"p2-offer-{i}" in accepted
        acknowledged = op.recipient in confirmed
        # Delayed, observable W3 event reward. No hidden needs/mode or oracle
        # counterfactual is supplied to the learner or scoring callback.
        reward = float(acknowledged) - 0.25 * int(transferred)
        rewards.append(reward)
    if train and learner is not None:
        for (_, context, action), reward in zip(decisions, rewards):
            learner.update(context, action, reward)
    assert sum(v for _,v in world.balances) == sum(v for _,v in genesis.balances)
    assert verify_replay(genesis, world)
    return {
        "reward": statistics.fmean(rewards),
        "transfers": len(accepted),
        "signals": len(confirmed),
        "world_fingerprint": world.fingerprint(),
        "actions": tuple(action for _,_,action in decisions),
        "reward_list": tuple(rewards),
        "ticks": world.tick,
        "events": len(world.events),
    }, world


def run_case(*, seed: int, method: str, train_episodes: int = 60,
             holdout_episodes: int = 30) -> dict:
    if (method not in METHODS or type(seed) is not int or seed < 0
            or not 1 <= train_episodes <= 200 or
            not 1 <= holdout_episodes <= 100):
        raise ValueError("invalid bounded trial")
    router, tokens = make_router()
    learner = TabularBandit() if method in TRAINABLE else None
    train_scores = []
    eval_scores = []
    mode_pairs = []
    for phase, amount in (("train", train_episodes), ("holdout", holdout_episodes)):
        for episode in range(amount):
            episode_seed = seed if phase == "train" else seed + 1000003
            world, needs = build_world(seed=episode_seed, episode=episode)
            result, _ = play_episode(
                router, tokens, world, method, learner,
                exploration_seed=deterministic_seed(episode_seed, episode, method),
                train=phase == "train" and method in TRAINABLE,
            )
            if phase == "train":
                train_scores.append(result["reward"])
            else:
                eval_scores.append(result["reward"])
                mode_pairs.append(needs)
    return {
        "method": method,
        "seed": seed, "holdout_seed": seed+1000003,
        "registered_agents": 30, "decision_agents_per_episode": 10,
        "train_episodes": train_episodes, "holdout_episodes": holdout_episodes,
        "train_updates": learner.updates if learner is not None else 0,
        "train_avg_reward": statistics.fmean(train_scores),
        "holdout_avg_reward": statistics.fmean(eval_scores),
        "holdout_needs_count": sum(sum(pair) for pair in mode_pairs),
        "holdout_mode_hash": sha256(json.dumps(mode_pairs).encode()).hexdigest(),
        "holdout_reward_sequence": eval_scores,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-episodes", type=int, default=60)
    parser.add_argument("--holdout-episodes", type=int, default=30)
    parser.add_argument("--seed-start", type=int, default=4103)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=METHODS)
    args = parser.parse_args()
    if not (1 <= args.seeds <= 5 and args.seed_start >= 0):
        parser.error("1..5 seeds, nonnegative seed start")
    started = time.perf_counter()
    cases = [run_case(seed=args.seed_start+i, method=m,
                      train_episodes=args.train_episodes,
                      holdout_episodes=args.holdout_episodes)
             for i in range(args.seeds) for m in args.methods]
    report = {
        "schema": SCHEMA, "python":sys.version.split()[0],
        "platform":platform.platform(), "wall_seconds":time.perf_counter()-started,
        "limitations": (
            "30 registered actors; only 10 make learned donor decisions each episode. "
            "Two-tick local same-owner donation tasks. Scripted recipients and "
            "reset episodes: delayed contextual bandit in W3, NOT general MARL."),
        "cases": cases,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
