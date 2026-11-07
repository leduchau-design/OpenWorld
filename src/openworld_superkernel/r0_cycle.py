"""R0 research-only integrated agent cycle; no public SuperKernel API.

This deliberately combines existing W1/W3/W4 fixtures on a trusted local host.
W3 is an immutable *in-memory* simulation; HyperMemory has a separate SQLite
transaction. Their effects are NOT atomic, crash-safe, externally authenticated,
or permission to interact across owners. No model/LLM calls or real-world actions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .hyper_memory_p1e import HyperMemoryP1e, Observation as MemoryObservation
from .memory_contracts import MemoryEvent, Provenance
from .world_fixture import (
    Action, Observation as WorldObservation, World, verify_replay,
)
from .world_guard import AuthorizedWorldAction, GuardedWorldGateway


@dataclass(frozen=True)
class CycleResult:
    """One accepted synthetic tick and its explicitly limited evidence."""

    world: World
    observation: WorldObservation
    prediction: float
    estimator: str
    strategy: str
    action_kind: str
    memory_event_id: str | None
    replay_ok: bool


def run_cycle(
    *,
    genesis: World,
    world: World,
    memory: HyperMemoryP1e,
    gateway: GuardedWorldGateway,
    owner_id: str,
    agent_id: str,
    target_id: str,
    read_capability: str,
    write_capability: str | None,
    simulated_outcome: int | None,
    strategy: str = "memory_threshold",
) -> CycleResult:
    """Run observe -> predict -> decide -> guard -> simulate -> record -> replay.

    The lab supplies the binary outcome *after* an accepted simulated action.
    It is synthetic feedback, never a verified real-world observation. `hold`
    has no observed reward and MUST NOT train the predictor.

    World state is only returned after the SQLite memory write succeeds; this
    does NOT create a cross-store transaction. A process crash after the SQLite
    commit, lost caller state or host compromise cannot be recovered atomically.
    The trusted host must separately authenticate its caller and protect keys.
    """
    if strategy not in {"memory_threshold", "fixed_transfer", "hold"}:
        raise ValueError("unknown R0 policy")
    if not owner_id or not agent_id or not target_id:
        raise ValueError("owner, actor and target are required")
    if strategy == "hold":
        if simulated_outcome is not None:
            raise ValueError("hold has no observed outcome")
    elif type(simulated_outcome) is not int or simulated_outcome not in (0, 1):
        raise ValueError("accepted simulated action requires binary feedback")
    if not verify_replay(genesis, world):
        raise ValueError("world replay failed")

    owner_of_actor = next(
        (a.owner_id for a in world.agents if a.agent_id == agent_id), None
    )
    if owner_of_actor != owner_id:
        raise PermissionError("agent ownership mismatch")
    observation = gateway.observe(
        world, agent_id=agent_id, signed_capability=read_capability,
    )
    prediction, estimator = memory.predict(
        owner_id=owner_id, agent_id=agent_id, requester_owner_id=owner_id,
    )
    if target_id not in observation.neighbors:
        raise ValueError("target is not a neighbor in the observed world")

    if strategy == "hold":
        kind = "hold"
    elif strategy == "fixed_transfer":
        kind = "transfer"
    else:
        kind = "transfer" if prediction >= 0.5 and observation.balance >= 1 else "signal"

    if kind == "hold":
        result = gateway.advance(world, actions=(), external=(), max_actions=1)
        if not verify_replay(genesis, result.world):
            raise ValueError("simulated replay diverged")
        return CycleResult(
            result.world, observation, prediction, estimator, strategy,
            kind, None, True,
        )

    if not write_capability:
        raise PermissionError("missing write capability")
    request_id = f"r0-{world.tick}-{agent_id}"
    action = Action(
        request_id=request_id, tick=world.tick, principal=owner_id,
        actor=agent_id, target=target_id, kind=kind,
        amount=1 if kind == "transfer" else 0,
    )
    step = gateway.advance(
        world, actions=(AuthorizedWorldAction(action, write_capability),),
        external=(), max_actions=1,
    )
    if step.accepted != (request_id,) or step.rejected:
        raise ValueError(f"simulated world action rejected: {step.rejected}")
    if not verify_replay(genesis, step.world):
        raise ValueError("simulated replay diverged")

    memory_state = memory.get_state(
        owner_id=owner_id, agent_id=agent_id, requester_owner_id=owner_id,
    )
    event_id = f"r0-simulated-feedback-{world.tick}-{agent_id}"
    payload = json.dumps(
        {
            "schema": "openworld.r0.simulated-feedback.v0",
            "world_before": world.fingerprint(),
            "world_after": step.world.fingerprint(),
            "request_id": request_id,
            "action": kind,
            "outcome": simulated_outcome,
            "provenance": "SIMULATED",
        },
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    memory.apply_batch(
        (
            MemoryObservation(
                event=MemoryEvent(
                    event_id=event_id, owner_id=owner_id,
                    event_type="synthetic_action_feedback",
                    provenance=Provenance.SIMULATED,
                    payload=payload, protected=True,
                ),
                agent_id=agent_id,
                sequence_number=memory_state["seq"] + 1,
                outcome=simulated_outcome,
            ),
        ),
        requester_owner_id=owner_id,
    )
    return CycleResult(
        step.world, observation, prediction, estimator, strategy,
        kind, event_id, True,
    )
