"""CPU-only synthetic world walkthrough and bounded microbenchmark, no cloud/LLM."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from time import perf_counter
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from openworld_superkernel.world_fixture import (
    Agent, TickInput, Weather, advance, create_world, seeded_signals, verify_replay,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--agents', type=int, default=30)
    parser.add_argument('--ticks', type=int, default=20)
    parser.add_argument('--seed', type=int, default=2026)
    args = parser.parse_args()
    if not 2 <= args.agents <= 1000 or not 1 <= args.ticks <= 100:
        parser.error('research limits: agents 2..1000, ticks 1..100')

    regions = ('north', 'mid', 'south')
    agents = tuple(Agent(f'a{i:04}', f'owner{i:04}', regions[i % 3], 10)
                   for i in range(args.agents))
    edges = tuple((f'a{i:04}', f'a{i+1:04}') for i in range(args.agents - 1))
    start = create_world(agents, edges, seed=args.seed)
    state = start
    tracemalloc.start()
    start_time = perf_counter()
    for _ in range(args.ticks):
        active = tuple(a.agent_id for a in agents if int(a.agent_id[1:]) % 3 == state.tick % 3)
        actions = seeded_signals(state, active)
        external = (Weather('north', 'rain' if state.tick % 2 else 'clear'),)
        state = advance(state, TickInput(state.tick, actions, external)).world
    elapsed = perf_counter() - start_time
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert verify_replay(start, state)
    print(f'seed={args.seed} agents={args.agents} ticks={args.ticks}')
    print(f'events={len(state.events)} provenance=SIMULATED')
    print(f'digest={state.fingerprint()} replay=PASS')
    print(f'cpu_seconds={elapsed:.6f} events_per_second={len(state.events)/elapsed:.1f}')
    print(f'peak_tracemalloc_bytes={peak}')
    print('NOTE: tiny synthetic fixture, NOT throughput or scaling certification')


if __name__ == '__main__':
    main()
