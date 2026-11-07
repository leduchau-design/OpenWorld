"""Experimental, dependency-free compositional world fixture.

Not a production kernel, sandbox, cryptographic identity, or a normative OWP API.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import random
from typing import Callable


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class Arrow:
    """A typed pure arrow. Composition is sequential, not an effects system."""

    source: type
    target: type
    function: Callable

    def __call__(self, value: object) -> object:
        if type(value) is not self.source:
            raise TypeError("arrow input type mismatch")
        result = self.function(value)
        if type(result) is not self.target:
            raise TypeError("arrow output type mismatch")
        return result

    def then(self, other: Arrow) -> Arrow:
        if self.target is not other.source:
            raise TypeError("incompatible composition ports")
        return Arrow(self.source, other.target, lambda x: other(self(x)))


def identity(kind: type) -> Arrow:
    return Arrow(kind, kind, lambda x: x)


@dataclass(frozen=True)
class Blueprint:
    agent_id: str
    owner_id: str
    role: str
    generation: int
    parent_id: str | None
    traits: tuple[tuple[str, int], ...]


def spawn(owner_id: str, role: str, seed: int, parent: Blueprint | None = None) -> Blueprint:
    """Create a deterministic *blueprint*, not learned intelligence or authority."""
    if not owner_id or role not in {"explorer", "builder", "diplomat"}:
        raise ValueError("unknown role or missing owner")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if parent and (parent.owner_id != owner_id or parent.role != role):
        raise ValueError("parent owner or role mismatch")
    parent_id = parent.agent_id if parent else None
    key = canonical([owner_id, role, seed, parent_id])
    rng = random.Random(seed)
    base = dict(parent.traits) if parent else {"curiosity": 50, "cooperation": 50}
    traits = tuple(sorted((name, max(0, min(100, value + rng.randint(-5, 5))))
                          for name, value in base.items()))
    return Blueprint("agt-" + sha256(key.encode()).hexdigest()[:20], owner_id, role,
                     parent.generation + 1 if parent else 0, parent_id, traits)


@dataclass(frozen=True)
class Intent:
    request_id: str
    principal: str
    from_agent: str
    to_agent: str
    amount: int
    tick: int


@dataclass(frozen=True)
class Event:
    tick: int
    sequence: int
    request_id: str
    from_agent: str
    to_agent: str
    amount: int
    prev_hash: str
    digest: str
    provenance: str = "SIMULATED"


@dataclass(frozen=True)
class World:
    tick: int
    accounts: tuple[tuple[str, int], ...]
    committed_ids: tuple[str, ...] = ()
    events: tuple[Event, ...] = ()

    @classmethod
    def create(cls, accounts: dict[str, int]) -> World:
        if not accounts or any(not key or type(value) is not int or value < 0
                               for key, value in accounts.items()):
            raise ValueError("invalid initial accounts")
        return cls(0, tuple(sorted(accounts.items())))

    def balance(self, agent: str) -> int:
        return dict(self.accounts)[agent]

    def fingerprint(self) -> str:
        payload = [self.tick, self.accounts, self.committed_ids,
                   [event.digest for event in self.events]]
        return sha256(canonical(payload).encode()).hexdigest()


@dataclass(frozen=True)
class StepResult:
    world: World
    accepted: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]


def advance(world: World, intents: list[Intent], grants: dict[str, frozenset[str]]) -> StepResult:
    """Resolve simultaneous proposals by request_id; one transfer is atomic.

    `grants` is trusted host input, not a field controlled by the intent sender.
    Rejections are receipts only; a production implementation needs a durable audit log.
    """
    balances = dict(world.accounts)
    seen = set(world.committed_ids)
    accepted: list[str] = []
    rejected: list[tuple[str, str]] = []
    events = list(world.events)
    for cmd in sorted(intents, key=lambda a: (a.request_id, a.principal, a.from_agent, a.to_agent)):
        reason = None
        if not cmd.request_id or cmd.request_id in seen:
            reason = "duplicate_or_missing_id"
        elif cmd.tick != world.tick:
            reason = "stale_tick"
        elif not cmd.principal or cmd.from_agent not in grants.get(cmd.principal, frozenset()):
            reason = "unauthorized"
        elif type(cmd.amount) is not int or cmd.amount <= 0:
            reason = "invalid_amount"
        elif cmd.from_agent not in balances or cmd.to_agent not in balances:
            reason = "unknown_account"
        elif cmd.from_agent == cmd.to_agent:
            reason = "self_transfer"
        elif balances[cmd.from_agent] < cmd.amount:
            reason = "insufficient_funds"
        if reason:
            rejected.append((cmd.request_id, reason))
            continue
        balances[cmd.from_agent] -= cmd.amount
        balances[cmd.to_agent] += cmd.amount
        seen.add(cmd.request_id)
        previous = events[-1].digest if events else "GENESIS"
        fields = [world.tick, len(events) + 1, cmd.request_id, cmd.from_agent,
                  cmd.to_agent, cmd.amount, previous, "SIMULATED"]
        digest = sha256(canonical(fields).encode()).hexdigest()
        events.append(Event(world.tick, len(events) + 1, cmd.request_id,
                            cmd.from_agent, cmd.to_agent, cmd.amount, previous, digest))
        accepted.append(cmd.request_id)
    new_world = World(world.tick + 1, tuple(sorted(balances.items())),
                      tuple(sorted(seen)), tuple(events))
    assert sum(balances.values()) == sum(dict(world.accounts).values())
    return StepResult(new_world, tuple(accepted), tuple(rejected))


def replay(initial: World, batches: list[list[Intent]], grants: dict[str, frozenset[str]]) -> World:
    """Replay submitted inputs, including rejected commands, under fixed code and order."""
    current = initial
    for batch in batches:
        current = advance(current, batch, grants).world
    return current
