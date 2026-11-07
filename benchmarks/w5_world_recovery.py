"""W5 bounded CPU-only world-replay evaluation. Outputs synthetic JSON, no API calls."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import platform
import resource
import sqlite3
import sys
import tempfile
import time
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openworld_superkernel.world_fixture import (
    Agent, TickInput, Weather, advance, candidate_contacts, create_world,
    seeded_signals, verify_replay,
)
from openworld_superkernel.world_persistence import load_checkpoint, save_checkpoint


def build_world(count: int, shape: str, seed: int):
    ids = [f"a{i:04d}" for i in range(count)]
    agents = tuple(Agent(agent, f"owner-{agent}", "north" if i % 2 == 0 else "south", 10)
                   for i, agent in enumerate(ids))
    if shape == "chain":
        edges = tuple(zip(ids[:-1], ids[1:]))
    elif shape == "hub":
        edges = tuple((ids[0], agent) for agent in ids[1:])
    elif shape == "disconnected":
        edges = ()
    else:
        raise ValueError("invalid graph shape")
    return create_world(agents, edges, seed=seed)


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * .95) - 1]


def measure(count: int, ticks: int, seed: int, shape: str) -> dict:
    genesis = build_world(count, shape, seed)
    world = genesis
    times = []
    tracemalloc.start()
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    visited_contacts = 0
    for step in range(ticks):
        active = tuple(a.agent_id for i, a in enumerate(genesis.agents)
                       if (i + step) % 3 == 0)
        visited_contacts += len(candidate_contacts(world, active))
        actions = seeded_signals(world, active)
        weather = (Weather("north", "rain" if step % 2 else "clear"),)
        started = time.perf_counter()
        world = advance(world, TickInput(world.tick, actions, weather)).world
        times.append(time.perf_counter() - started)
    with tempfile.TemporaryDirectory() as temp:
        dest = Path(temp) / "world.sqlite3"
        write_start = time.perf_counter()
        save_checkpoint(dest, genesis, world)
        checkpoint_seconds = time.perf_counter() - write_start
        read_start = time.perf_counter()
        genesis_loaded, restored = load_checkpoint(dest)
        recovery_seconds = time.perf_counter() - read_start
        if (not verify_replay(genesis_loaded, restored)
                or restored.fingerprint() != world.fingerprint()):
            raise AssertionError("simulated replay differs after checkpoint")
        size = sum(p.stat().st_size for p in (
            dest, Path(str(dest) + "-wal"), Path(str(dest) + "-shm")
        ) if p.exists())
    cpu_seconds = time.process_time() - cpu_start
    wall_seconds = time.perf_counter() - wall_start
    _, tracemalloc_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "shape": shape, "seed": seed, "agent_count": count, "ticks": ticks,
        "simulated_events": len(world.events), "contacts_visited": visited_contacts,
        "journal_ticks": len(world.journal), "replay_match": True,
        "tick_p95_seconds": p95(times),
        "simulation_wall_seconds": sum(times),
        "checkpoint_seconds": checkpoint_seconds,
        "recovery_seconds": recovery_seconds,
        "total_wall_seconds": wall_seconds,
        "process_cpu_seconds": cpu_seconds,
        "tracemalloc_peak_bytes": tracemalloc_peak,
        "checkpoint_disk_bytes_including_wal_shm": size,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", type=int, default=30)
    parser.add_argument("--ticks", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=2026)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not (2 <= args.agents <= 200 and 1 <= args.ticks <= 100
            and 1 <= args.seeds <= 5 and 0 <= args.seed_start <= 2**31 - 1):
        parser.error("bounded experiment: agents 2-200, ticks 1-100, seeds 1-5")
    rows = [measure(args.agents, args.ticks, args.seed_start + index, shape)
            for shape in ("chain", "hub", "disconnected")
            for index in range(args.seeds)]
    report = {
        "schema": "openworld.w5.world-recovery-eval.v0",
        "limits": "SIMULATED, local CPU only, no independent security/capacity proof",
        "environment": {
            "python": sys.version.split()[0],
            "sqlite": sqlite3.sqlite_version,
            "platform": platform.platform(),
            "pid": os.getpid(),
            "rss_peak_kib_linux": (
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                if sys.platform == "linux" else None
            ),
        },
        "arguments": {
            "agents": args.agents, "ticks": args.ticks,
            "seed_start": args.seed_start, "seeds": args.seeds,
        },
        "results": rows,
    }
    raw = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(raw, encoding="utf-8")
    else:
        print(raw, end="")


if __name__ == "__main__":
    main()
