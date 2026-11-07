"""Independent W5 experiment runner for HyperMemory HM-P1e.

CPU-only synthetic data; compares predictive quality and physical SQLite footprint.
Full-history and compact state do not offer equivalent historical recall.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from openworld_superkernel.memory_contracts import MemoryEvent, Provenance
from openworld_superkernel.hyper_memory_p1e import HyperMemoryP1e, Observation

SCENARIOS = ("stable", "abrupt", "gradual", "alternating", "noise")


def probability(agent: int, day: int, days: int, scenario: str) -> float:
    if scenario not in SCENARIOS:
        raise ValueError("invalid scenario")
    base = 0.8 if agent % 2 == 0 else 0.2
    if scenario == "stable":
        return base
    if scenario == "abrupt":
        return base if day < days // 2 else 1 - base
    if scenario == "gradual":
        return base + (1 - 2 * base) * day / max(1, days - 1)
    if scenario == "alternating":
        return base if (day // max(1, days // 4)) % 2 == 0 else 1 - base
    return 0.5


def generate(agents: int, days: int, seed: int, scenario: str):
    if agents < 1 or days < 1:
        raise ValueError("agents and days must be positive")
    rng = [random.Random(seed + a * 100_003) for a in range(agents)]
    for day in range(days):
        yield [(a, day, int(rng[a].random() < probability(a, day, days, scenario)))
               for a in range(agents)]


def disk_bytes(path: Path) -> int:
    return sum(p.stat().st_size for suffix in ("", "-wal", "-shm")
               if (p := Path(str(path) + suffix)).exists())


def brier(predictions: list[float], outcomes: list[int]) -> float:
    if not predictions or len(predictions) != len(outcomes):
        raise ValueError("nonempty matched arrays required")
    return sum((p - y) ** 2 for p, y in zip(predictions, outcomes)) / len(outcomes)


def p95(xs: list[float]) -> float:
    if not xs:
        return 0.0
    return sorted(xs)[min(len(xs) - 1, round(0.95 * (len(xs) - 1)))]


def run(agents: int, days: int, seed: int, scenario: str) -> dict:
    if agents < 1 or days < 1 or scenario not in SCENARIOS:
        raise ValueError("invalid benchmark input")

    with tempfile.TemporaryDirectory(prefix="openworld-w5-") as directory:
        path_full = Path(directory) / "full.sqlite"
        path_memory = Path(directory) / "memory.sqlite"
        full = sqlite3.connect(path_full, isolation_level=None)
        full.execute("PRAGMA journal_mode=WAL")
        full.execute("PRAGMA synchronous=FULL")
        full.execute("CREATE TABLE history(agent_id INTEGER, day INTEGER, outcome INTEGER,"
                     "PRIMARY KEY(agent_id, day)) WITHOUT ROWID")
        memory = HyperMemoryP1e(path_memory)

        totals = [0] * agents
        successes = [0] * agents
        fast_success = [0.0] * agents
        fast_weight = [0.0] * agents
        long_pred, fast_pred, adaptive_pred, labels = [], [], [], []
        selected = {"static": 0, "fast": 0, "slow": 0}
        durations_full, durations_memory = [], []
        peak_full, peak_memory = 0, 0
        cpu_start = time.process_time()
        try:
            for batch in generate(agents, days, seed, scenario):
                incoming = []
                history = []
                for agent, day, outcome in batch:
                    long_pred.append((successes[agent] + 1) / (totals[agent] + 2))
                    fast_pred.append((fast_success[agent] + 1) / (fast_weight[agent] + 2))
                    prediction, mode = memory.predict(
                        owner_id="synthetic", agent_id=f"agent-{agent}",
                        requester_owner_id="synthetic",
                    )
                    adaptive_pred.append(prediction)
                    selected[mode] += 1
                    labels.append(outcome)
                    incoming.append(Observation(
                        event=MemoryEvent(event_id=f"agent-{agent}:step-{day}",
                            owner_id="synthetic", event_type="telemetry",
                            provenance=Provenance.SIMULATED,
                            payload=b"", reconstructable=True),
                        agent_id=f"agent-{agent}", sequence_number=day + 1,
                        outcome=outcome))
                    history.append((agent, day, outcome))

                begin = time.perf_counter()
                full.execute("BEGIN IMMEDIATE")
                try:
                    full.executemany("INSERT INTO history VALUES(?,?,?)", history)
                    full.execute("COMMIT")
                except BaseException:
                    full.execute("ROLLBACK")
                    raise
                durations_full.append(time.perf_counter() - begin)

                begin = time.perf_counter()
                written = memory.apply_batch(incoming, requester_owner_id="synthetic")
                durations_memory.append(time.perf_counter() - begin)
                if written != agents:
                    raise AssertionError("unexpected write count")

                for agent, _day, outcome in batch:
                    successes[agent] += outcome
                    totals[agent] += 1
                    fast_success[agent] = 0.65 * fast_success[agent] + outcome
                    fast_weight[agent] = 0.65 * fast_weight[agent] + 1

                peak_full = max(peak_full, disk_bytes(path_full))
                peak_memory = max(peak_memory, disk_bytes(path_memory))

            online = {"full_history": disk_bytes(path_full),
                      "hyper_memory": disk_bytes(path_memory)}
            full.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            memory.checkpoint()
            compact = {"full_history": disk_bytes(path_full),
                       "hyper_memory": disk_bytes(path_memory)}
            return {
                "scenario": scenario, "seed": seed, "agents": agents,
                "days": days, "updates": agents * days,
                "brier": {"full_history_static": brier(long_pred, labels),
                          "discounted_fast": brier(fast_pred, labels),
                          "adaptive_gate": brier(adaptive_pred, labels)},
                "gate_choices": selected,
                "storage_bytes": {
                    "peak_online": {"full_history": peak_full, "hyper_memory": peak_memory},
                    "end_online": online, "after_checkpoint": compact,
                },
                "write_seconds": {"full_history": sum(durations_full),
                                  "hyper_memory": sum(durations_memory)},
                "p95_batch_write_ms": {
                    "full_history": p95(durations_full) * 1000,
                    "hyper_memory": p95(durations_memory) * 1000,
                },
                "combined_cpu_seconds": time.process_time() - cpu_start,
                "caveats": [
                    "Synthetic Bernoulli only; no real users or language memories",
                    "Full-history permits historical queries; compressed telemetry does not",
                    "SQLite bytes include WAL and SHM but omit filesystem block allocation",
                    "Combined CPU is not attributable to an individual method",
                    "Single process, no distributed throughput claim",
                ],
            }
        finally:
            full.close()
            memory.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", type=int, default=100)
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--scenario", choices=SCENARIOS, default="abrupt")
    args = parser.parse_args()
    print(json.dumps(run(args.agents, args.days, args.seed, args.scenario), indent=2))


if __name__ == "__main__":
    main()
