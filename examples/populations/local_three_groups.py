"""Local 30-agent/3-population *simulated* exchange, no trained policy or network.

Prints a replay-verifiable W3 trace. Grant examples are issued by a single
trusted toy host and are NOT independently authenticated bilateral consent.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from openworld_superkernel.population_links import (
    Exchange, Population, PopulationLink, PopulationRouter,
)
from openworld_superkernel.trust_boundaries import CapabilityAuthority
from openworld_superkernel.world_guard import GuardedWorldGateway
from openworld_superkernel.world_fixture import (
    Action, Agent, create_world, verify_replay,
)


def run_demo() -> dict:
    owner = "single-research-owner"
    principal = "trusted-local-demo"
    ids = [f"a{i:02d}" for i in range(30)]
    populations = tuple(Population(f"guild-{g}", tuple(ids[g*10:g*10+10]))
                        for g in range(3))
    agents = tuple(Agent(a, owner, f"region-{i//10}", 5)
                   for i, a in enumerate(ids))
    edges = tuple(zip(ids[:-1], ids[1:]))
    genesis = create_world(agents, edges, seed=2026)
    authority = CapabilityAuthority(
        os.urandom(32), issuer="local-demonstration", audience="world")
    gateway = GuardedWorldGateway(
        authority, authenticated_principal=lambda: principal)
    router = PopulationRouter(gateway, populations, (
        PopulationLink("guild-0", "guild-1", ("transfer", "signal"),
                       max_transfer=3, max_actions_per_tick=2),
        PopulationLink("guild-1", "guild-0", ("signal",)),
        PopulationLink("guild-1", "guild-2", ("transfer", "signal"),
                       max_transfer=3, max_actions_per_tick=2),
        PopulationLink("guild-2", "guild-1", ("signal",)),
    ))
    now = int(time.time())

    def exchange(world, req, source, dest, actor, target, kind, amount=0):
        def token(agent):
            return authority.issue(
                principal=principal, owner=owner, resource=agent,
                action="write_agent", valid_from=now - 10, expires_at=now + 120)
        return Exchange(source, dest, Action(
            req, world.tick, owner, actor, target, kind, amount),
            token(actor), token(target))

    first = router.advance(genesis, exchanges=(
        exchange(genesis, "ex0-transfer", "guild-0", "guild-1",
                 "a09", "a10", "transfer", 2),
        exchange(genesis, "ex0-signal", "guild-1", "guild-2",
                 "a19", "a20", "signal"),
        exchange(genesis, "ex0-reply", "guild-1", "guild-0",
                 "a10", "a09", "signal"),
    ))
    world = first.state.world
    second = router.advance(world, exchanges=(
        exchange(world, "ex1-reply", "guild-2", "guild-1",
                 "a20", "a19", "signal"),
        exchange(world, "ex1-transfer", "guild-1", "guild-2",
                 "a19", "a20", "transfer", 1),
    ))
    world = second.state.world
    assert verify_replay(genesis, world)
    balances = dict(world.balances)
    assert sum(balances.values()) == 150
    assert all(e.provenance == "SIMULATED" for e in world.events)
    return {
        "schema": "openworld.w3.local-population-links.demo.v0",
        "population_count": len(populations),
        "registered_agents": len(ids),
        "owners": 1,
        "ticks": world.tick,
        "accepted": list(first.state.accepted + second.state.accepted),
        "rejected": list(first.state.rejected + second.state.rejected),
        "event_kinds": [e.kind for e in world.events],
        "total_resources": sum(balances.values()),
        "selected_balances": {key: balances[key] for key in
                              ("a09", "a10", "a19", "a20")},
        "replay": "PASS",
        "simulated_state_sha256": world.fingerprint(),
        "limits": "Single trusted owner, static rules, no federation/learning/independent consent",
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, indent=2))
