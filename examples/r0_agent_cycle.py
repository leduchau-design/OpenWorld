"""Single-command R0 walkthrough: no real agents, keys, network or external action.

Usage: PYTHONPATH=src python examples/r0_agent_cycle.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openworld_superkernel.hyper_memory_p1e import HyperMemoryP1e
from openworld_superkernel.r0_cycle import run_cycle
from openworld_superkernel.trust_boundaries import CapabilityAuthority
from openworld_superkernel.world_fixture import Agent, create_world, verify_replay
from openworld_superkernel.world_guard import GuardedWorldGateway


def main() -> None:
    principal, owner = "trusted-local-r0-host", "research-owner"
    genesis = create_world(
        (Agent("alice", owner, "lab", 3), Agent("bob", owner, "lab", 3)),
        (("alice", "bob"),), seed=2026,
    )
    authority = CapabilityAuthority(
        os.urandom(32), issuer="r0-local-ephemeral", audience="world",
    )
    gateway = GuardedWorldGateway(authority, authenticated_principal=lambda: principal)
    now = int(time.time())

    def token(action: str) -> str:
        return authority.issue(
            principal=principal, owner=owner, resource="alice", action=action,
            valid_from=now - 10, expires_at=now + 120,
        )

    read_token = token("read_world")
    write_token = token("write_agent")
    with tempfile.TemporaryDirectory(prefix="openworld-r0-") as directory:
        with HyperMemoryP1e(Path(directory) / "lab-memory.sqlite3") as memory:
            state = genesis
            cycles = []
            for outcome in (0, 1, 1):
                result = run_cycle(
                    genesis=genesis, world=state, memory=memory, gateway=gateway,
                    owner_id=owner, agent_id="alice", target_id="bob",
                    read_capability=read_token, write_capability=write_token,
                    simulated_outcome=outcome,
                )
                state = result.world
                stored = memory.exact_event(
                    result.memory_event_id, requester_owner_id=owner,
                )
                assert stored is not None
                assert json.loads(stored)["provenance"] == "SIMULATED"
                cycles.append({
                    "tick": result.observation.tick,
                    "strategy": result.strategy,
                    "predictor": result.estimator,
                    "prediction_provenance": "INFERRED",
                    "world_observation_provenance": "SIMULATED",
                    "p_success_before_action": round(result.prediction, 4),
                    "action": result.action_kind,
                    "synthetic_feedback": outcome,
                    "memory_event_id": result.memory_event_id,
                    "replay": "PASS" if result.replay_ok else "FAIL",
                })
            print(json.dumps({
                "schema": "openworld.r0.vertical-slice.demo.v0",
                "owners": 1, "agents": 2,
                "goal": "conditional simulated resource offer to a neighbor",
                "cycles": cycles,
                "final_balances": dict(state.balances),
                "world_sha256": state.fingerprint(),
                "world_replay": "PASS" if verify_replay(genesis, state) else "FAIL",
                "limits": (
                    "Synthetic same-owner local fixture only; ephemeral key; "
                    "W3 in-memory and HM-P1e SQLite are NOT atomic together; "
                    "no independent authentication, bilateral consent, "
                    "production guarantee or measured policy superiority"
                ),
            }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
