"""P1: offline multi-agent contextual-bandit learning on frozen synthetic worlds.

This is real *online learning from chosen-action reward only*, but is NOT
multi-agent reinforcement learning in an authoritative W3 world. No agent code,
network, secret, memory, capability or real-world event is ingested.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import sys
import time
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openworld_superkernel.population_repr import empirical_cf, make_genome

ROLES = ("builder", "explorer", "trader")
METHODS = ("no_summary", "group_mean", "histogram8", "ecf")
TASKS = ("mean", "spectral")
REGIMES = ("balanced", "rare")
SCHEMA = "openworld.p1.population-bandit.v1"
POLICY_REF = "sha256:" + sha256(b"synthetic-fixed-rules-no-execution").hexdigest()
GOOD_REWARD = 0.85
BAD_REWARD = 0.15


def _seed(*parts: object) -> int:
    payload = json.dumps(parts, separators=(",", ":"), ensure_ascii=True)
    return int.from_bytes(sha256(payload.encode()).digest()[:8], "big")


def _clip(value: float) -> float:
    return max(-1.0, min(1.0, value))


@dataclass(frozen=True)
class SyntheticAgent:
    """Persistent local synthetic actor; no account identity or owner rights."""
    agent_id: str
    role: str
    trait: float
    genome_id: str


@dataclass(frozen=True)
class Scene:
    """World observation snapshot, not a W3 transaction or recorded real event."""
    seed: int
    tick: int
    agents: tuple[SyntheticAgent, ...]
    states: tuple[float, ...]    # group field, used by experiment's host
    private_obs: tuple[float, ...]  # observation the policy can access


def population(n: int, *, regime: str = "balanced") -> tuple[SyntheticAgent, ...]:
    if type(n) is not int or not 9 <= n <= 300 or regime not in REGIMES:
        raise ValueError("agent population must be 9..300 and regime valid")
    agents = []
    for i in range(n):
        role = ("trader" if i < 2 else ROLES[(i - 2) % 2]) if regime == "rare" \
            else ROLES[i % len(ROLES)]
        trait = ((i % 5) - 2) / 10.0
        genome = make_genome(role, "rules", POLICY_REF,
                             {"curiosity": 30 + (i % 7) * 5,
                              "risk": 50 + (i % 5) * 5})
        agents.append(SyntheticAgent(f"research-{i:04d}", role, trait, genome.genome_id))
    return tuple(agents)


def make_scene(agents: tuple[SyntheticAgent, ...], *, seed: int,
               tick: int, task: str) -> Scene:
    if task not in TASKS or type(seed) is not int or seed < 0 \
            or type(tick) is not int or tick < 0:
        raise ValueError("invalid scene parameters")
    rng = random.Random(_seed(seed, tick, task, "world"))
    # Each role has an independent hidden mode; mode is never passed to policy.
    modes = {role: -1 if rng.randrange(2) == 0 else 1 for role in ROLES}
    states = []
    views = []
    for agent in agents:
        mode = modes[agent.role]
        if task == "mean":
            x = _clip(mode * 0.62 + rng.gauss(0, 0.20))
        else:
            # Two distributions both have approximately zero mean but very
            # different E[cos(pi X)]: central mass versus symmetrical wings.
            x = (_clip(rng.gauss(0, 0.12)) if mode == 1 else
                 _clip((1 if rng.randrange(2) else -1) * 0.85
                       + rng.gauss(0, 0.08)))
        states.append(x)
        # Private signal is deliberately uninformative about the population mode.
        views.append(rng.uniform(-1.0, 1.0))
    return Scene(seed, tick, agents, tuple(states), tuple(views))


def role_state(scene: Scene, role: str) -> tuple[float, ...]:
    return tuple(x for agent, x in zip(scene.agents, scene.states) if agent.role == role)


def true_signal(scene: Scene, role: str, task: str) -> float:
    x = role_state(scene, role)
    if task == "mean":
        return statistics.fmean(x)
    if task == "spectral":
        return statistics.fmean(math.cos(math.pi * item) for item in x)
    raise ValueError("unsupported task")


def optimal_action(scene: Scene, index: int, task: str) -> int:
    agent = scene.agents[index]
    return int(true_signal(scene, agent.role, task) + agent.trait * 0.1 > 0)


def expected_reward(action: int, oracle_action: int) -> float:
    if type(action) is not int or action not in (0, 1):
        raise ValueError("action must be binary")
    return GOOD_REWARD if action == oracle_action else BAD_REWARD


def realized_reward(scene: Scene, index: int, action: int, task: str) -> int:
    """Counterfactual potential outcome is deterministic; reveal CHOSEN action only."""
    p = expected_reward(action, optimal_action(scene, index, task))
    uniform = _seed("reward", scene.seed, scene.tick, scene.agents[index].agent_id,
                    task, action) / 2**64
    return int(uniform < p)


def population_features(scene: Scene, method: str) -> dict[str, tuple[float, ...]]:
    if method not in METHODS:
        raise ValueError("unknown representation")
    output = {}
    for role in ROLES:
        group = role_state(scene, role)
        if not group:
            continue
        if method == "no_summary":
            feature = ()
        elif method == "group_mean":
            feature = (statistics.fmean(group),)
        elif method == "histogram8":
            bins = [0] * 8
            for value in group:
                bins[min(7, max(0, int((value + 1.0) * 4.0)))] += 1
            feature = tuple(count / len(group) for count in bins)
        else:
            feature = empirical_cf(tuple((x,) for x in group), (math.pi,))
        output[role] = feature
    return output


def observe(scene: Scene, index: int, shared: dict[str, tuple[float, ...]]
            ) -> tuple[float, ...]:
    agent = scene.agents[index]
    return (1.0, scene.private_obs[index], agent.trait) + shared[agent.role]


class OnlineBandit:
    """Role-shared logistic reward estimators with epsilon-greedy action choice."""

    def __init__(self, roles: tuple[str, ...], width: int, *, rate: float = 0.14):
        if not roles or type(width) is not int or width < 3 or not 0 < rate <= 0.5:
            raise ValueError("invalid bandit model")
        self.weights = {role: [[0.0] * width for _ in range(2)] for role in roles}
        self.rate = rate
        self.updates = 0

    @staticmethod
    def _prob(weights: list[float], x: tuple[float, ...]) -> float:
        z = sum(a * b for a, b in zip(weights, x))
        z = max(-25.0, min(25.0, z))
        return 1.0 / (1.0 + math.exp(-z))

    def select(self, role: str, x: tuple[float, ...], *, explore: bool,
               rng: random.Random | None = None, epsilon: float = 0.0) -> int:
        if role not in self.weights or len(x) != len(self.weights[role][0]):
            raise ValueError("invalid observation or role")
        if explore and rng is not None and rng.random() < epsilon:
            return rng.randrange(2)
        p0 = self._prob(self.weights[role][0], x)
        p1 = self._prob(self.weights[role][1], x)
        return int(p1 > p0)

    def update(self, role: str, x: tuple[float, ...], action: int, reward: int) -> None:
        if action not in (0, 1) or reward not in (0, 1):
            raise ValueError("invalid bandit feedback")
        w = self.weights[role][action]
        estimate = self._prob(w, x)
        # Only observed chosen-action reward is used; no oracle or reward vector.
        error = reward - estimate
        for j, value in enumerate(x):
            w[j] += self.rate * error * value
        self.updates += 1


def _run_method(agents: tuple[SyntheticAgent, ...],
                train_scenes: tuple[Scene, ...],
                holdout_scenes: tuple[Scene, ...], *,
                method: str, task: str, exploration_seed: int) -> dict:
    sample_shared = population_features(train_scenes[0], method)
    width = len(observe(train_scenes[0], 0, sample_shared))
    learner = OnlineBandit(ROLES, width)
    rng = random.Random(exploration_seed)
    timing = []
    reward_train = 0
    exploratory = 0
    for tick, scene in enumerate(train_scenes):
        started = time.perf_counter()
        shared = population_features(scene, method)
        timing.append(time.perf_counter() - started)
        epsilon = 0.25 - (0.20 * tick / max(1, len(train_scenes) - 1))
        # Freeze each tick's decisions before any reward update: no within-tick
        # communication or future-feedback leakage between agents.
        batch = []
        for index, agent in enumerate(agents):
            vector = observe(scene, index, shared)
            action = learner.select(agent.role, vector, explore=True,
                                    rng=rng, epsilon=epsilon)
            reward = realized_reward(scene, index, action, task)
            batch.append((agent.role, vector, action, reward))
        for role, vector, action, reward in batch:
            learner.update(role, vector, action, reward)
            reward_train += reward
        exploratory += len(batch)
    success = regret = observed = 0.0
    by_role = {role: {"correct": 0, "n": 0} for role in ROLES}
    frozen = learner.updates
    for scene in holdout_scenes:
        started = time.perf_counter()
        shared = population_features(scene, method)
        timing.append(time.perf_counter() - started)
        for index, agent in enumerate(agents):
            x = observe(scene, index, shared)
            action = learner.select(agent.role, x, explore=False)
            oracle = optimal_action(scene, index, task)
            success += int(action == oracle)
            observed += realized_reward(scene, index, action, task)
            regret += GOOD_REWARD - expected_reward(action, oracle)
            by_role[agent.role]["correct"] += int(action == oracle)
            by_role[agent.role]["n"] += 1
    if learner.updates != frozen:
        raise AssertionError("holdout mutated learner weights")
    total = len(holdout_scenes) * len(agents)
    ordered = sorted(timing)
    return {
        "train_updates": learner.updates,
        "train_observed_reward_rate": reward_train / exploratory,
        "holdout_actions": total,
        "holdout_action_accuracy": success / total,
        "holdout_reward_rate": observed / total,
        "holdout_expected_regret_per_action": regret / total,
        "role_accuracy": {r: (v["correct"] / v["n"] if v["n"] else None)
                          for r, v in by_role.items()},
        "sketch_width": width - 3,
        "sketch_p50_seconds": statistics.median(ordered),
        "sketch_p95_seconds": ordered[math.ceil(0.95 * len(ordered)) - 1],
    }


def run_case(*, n: int = 30, train_ticks: int = 160, holdout_ticks: int = 60,
             seed: int = 3101, task: str = "mean",
             regime: str = "balanced") -> dict:
    if (type(seed) is not int or seed < 0 or not 9 <= n <= 300
            or not 10 <= train_ticks <= 500 or not 5 <= holdout_ticks <= 200
            or task not in TASKS or regime not in REGIMES):
        raise ValueError("bounded P1 trial configuration required")
    agents = population(n, regime=regime)
    train = tuple(make_scene(agents, seed=seed, tick=i, task=task)
                  for i in range(train_ticks))
    # Disjoint world-generation seed, ticks and reward tables for holdout.
    held_seed = seed + 1_000_003
    test = tuple(make_scene(agents, seed=held_seed, tick=i, task=task)
                 for i in range(holdout_ticks))
    digest = sha256()
    for scene in train + test:
        digest.update(f"{scene.seed}/{scene.tick}/{task};".encode())
        for agent, state, private in zip(scene.agents, scene.states, scene.private_obs):
            digest.update(f"{agent.agent_id}/{agent.genome_id}/{state.hex()}/"
                          f"{private.hex()};".encode())
    data_hash = digest.hexdigest()
    results = {
        method: _run_method(
            agents, train, test, method=method, task=task,
            exploration_seed=_seed("explore", seed, task, regime),
        )
        for method in METHODS
    }
    return {
        "world_seed": seed,
        "holdout_world_seed": held_seed,
        "agents": len(agents),
        "roles": sorted(set(a.role for a in agents)),
        "task": task, "regime": regime,
        "train_ticks": train_ticks, "holdout_ticks": holdout_ticks,
        "synthetic_data_sha256": data_hash,
        "genomes_are_only_blueprints": True,
        "methods": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", type=int, default=30)
    parser.add_argument("--train-ticks", type=int, default=160)
    parser.add_argument("--holdout-ticks", type=int, default=60)
    parser.add_argument("--seed-start", type=int, default=3101)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--tasks", nargs="+", choices=TASKS, default=TASKS)
    parser.add_argument("--regimes", nargs="+", choices=REGIMES, default=REGIMES)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if type(args.seeds) is not int or not 1 <= args.seeds <= 5:
        parser.error("seed count must be 1..5")
    tracemalloc.start()
    wall = time.perf_counter()
    cpu = time.process_time()
    cases = [run_case(n=args.agents, train_ticks=args.train_ticks,
                      holdout_ticks=args.holdout_ticks, seed=args.seed_start + offset,
                      task=task, regime=regime)
             for task in args.tasks for regime in args.regimes
             for offset in range(args.seeds)]
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    report = {
        "schema": SCHEMA,
        "claim": "Offline synthetic contextual bandits; no W3 policy learning / MARL certification",
        "environment": {
            "python": sys.version.split()[0], "platform": platform.platform(),
            "cpu_count": os.cpu_count(), "tracemalloc_peak_bytes": peak,
        },
        "total_wall_seconds": time.perf_counter() - wall,
        "total_process_cpu_seconds": time.process_time() - cpu,
        "cases": cases,
    }
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
