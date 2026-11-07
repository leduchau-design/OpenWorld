"""W3 experimental, CPU-only authoritative world fixture (NOT a public API).

Trusted caller authenticates principal BEFORE constructing commands. All world
records here are SIMULATED, in memory, and not a substitute for RFC-006 evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json


def _hash(data: object) -> str:
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Agent:
    agent_id: str
    owner_id: str
    region: str
    resources: int


@dataclass(frozen=True)
class Action:
    request_id: str
    tick: int
    principal: str
    actor: str
    target: str
    kind: str  # transfer | signal
    amount: int = 0


@dataclass(frozen=True)
class Weather:
    region: str
    condition: str  # clear | rain


@dataclass(frozen=True)
class TickInput:
    tick: int
    actions: tuple[Action, ...]
    external: tuple[Weather, ...] | None
    action_budget: int | None = None  # trusted execution setting recorded for replay


@dataclass(frozen=True)
class Event:
    tick: int
    sequence: int
    kind: str
    actor: str
    target: str
    amount: int
    provenance: str
    prev_hash: str
    digest: str


@dataclass(frozen=True)
class World:
    tick: int
    seed: int
    agents: tuple[Agent, ...]
    graph: tuple[tuple[str, tuple[str, ...]], ...]
    balances: tuple[tuple[str, int], ...]
    weather: tuple[tuple[str, str], ...]
    processed_ids: tuple[str, ...] = ()
    events: tuple[Event, ...] = ()
    journal: tuple[TickInput, ...] = ()

    def fingerprint(self) -> str:
        return _hash([self.tick, self.seed, [(a.agent_id, a.owner_id, a.region, a.resources)
                                             for a in self.agents], self.graph, self.balances,
                      self.weather, self.processed_ids,
                      [(e.tick, e.sequence, e.kind, e.actor, e.target, e.amount,
                        e.provenance, e.prev_hash, e.digest) for e in self.events],
                      [_input_record(b) for b in self.journal]])


@dataclass(frozen=True)
class StepResult:
    world: World
    accepted: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Observation:
    tick: int
    agent_id: str
    balance: int
    region: str
    weather: str
    neighbors: tuple[str, ...]
    inbox: tuple[tuple[str, int], ...]  # (sender_id, tick) of signal events


def _input_record(batch: TickInput) -> object:
    return [batch.tick,
            [(c.request_id, c.tick, c.principal, c.actor, c.target, c.kind, c.amount)
             for c in batch.actions],
            None if batch.external is None else
            [(w.region, w.condition) for w in batch.external], batch.action_budget]


def create_world(agents: tuple[Agent, ...], edges: tuple[tuple[str, str], ...],
                 seed: int = 0) -> World:
    """Generate a finite undirected sparse world; no account/edge may be ambiguous."""
    if type(seed) is not int or seed < 0 or not agents:
        raise ValueError("invalid seed or empty population")
    ids = [a.agent_id for a in agents]
    if len(ids) != len(set(ids)) or any(not a.agent_id or not a.owner_id or not a.region
       or type(a.resources) is not int or a.resources < 0 for a in agents):
        raise ValueError("invalid agent identity, ownership, region or resources")
    links: dict[str, set[str]] = {a: set() for a in ids}
    for a, b in edges:
        if a not in links or b not in links or a == b or b in links[a]:
            raise ValueError("invalid, self or duplicate edge")
        links[a].add(b)
        links[b].add(a)
    return World(0, seed, tuple(sorted(agents, key=lambda a: a.agent_id)),
                 tuple(sorted((a, tuple(sorted(neighbors))) for a, neighbors in links.items())),
                 tuple(sorted((a.agent_id, a.resources) for a in agents)),
                 tuple((region, "clear") for region in sorted({a.region for a in agents})))


def candidate_contacts(world: World, active: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    """Visit only adjacency lists of active agents, never all N x N pairs."""
    graph = dict(world.graph)
    if any(a not in graph for a in active):
        raise ValueError("unknown active agent")
    return tuple((a, neighbor) for a in sorted(set(active)) for neighbor in graph[a])


def seeded_signals(world: World, active: tuple[str, ...]) -> tuple[Action, ...]:
    """Deterministic demo policy. SHA-256 explicitly defines the choice algorithm."""
    graph = dict(world.graph)
    owners = {a.agent_id: a.owner_id for a in world.agents}
    if any(a not in graph for a in active):
        raise ValueError("unknown active agent")
    signals = []
    for actor in sorted(set(active)):
        peers = graph[actor]
        if peers:
            choice = int(_hash([world.seed, world.tick, actor]), 16) % len(peers)
            signals.append(Action(f"sig-{world.tick}-{actor}", world.tick,
                                  owners[actor], actor, peers[choice], "signal"))
    return tuple(signals)


def advance(world: World, batch: TickInput, *, max_actions: int = 256) -> StepResult:
    """Authoritative in-memory reducer. All exogenous changes must be explicit."""
    if not isinstance(batch, TickInput) or batch.tick != world.tick:
        raise ValueError("missing or wrong tick input")
    if batch.external is None:
        raise ValueError("external inputs missing; provide an explicit empty tuple")
    if not isinstance(batch.actions, tuple) or not isinstance(batch.external, tuple):
        raise TypeError("tick inputs must be tuples")
    if type(max_actions) is not int or max_actions < 0 or len(batch.actions) > max_actions:
        raise ValueError("action budget exceeded")
    if batch.action_budget is not None and batch.action_budget != max_actions:
        raise ValueError("replay action budget does not match trusted execution")
    if any(not isinstance(c, Action) for c in batch.actions):
        raise TypeError("invalid action type")
    if any(not isinstance(c.request_id, str) or type(c.tick) is not int
           or not isinstance(c.principal, str) or not isinstance(c.actor, str)
           or not isinstance(c.target, str) or not isinstance(c.kind, str)
           or type(c.amount) is not int for c in batch.actions):
        raise TypeError("malformed action fields")
    regions = dict(world.weather)
    if any(not isinstance(w, Weather) for w in batch.external):
        raise ValueError("invalid exogenous input")
    if len({w.region for w in batch.external}) != len(batch.external):
        raise ValueError("conflicting exogenous updates")
    for w in batch.external:
        if w.region not in regions or w.condition not in {"clear", "rain"}:
            raise ValueError("invalid exogenous input")
    balances = dict(world.balances)
    owners = {a.agent_id: a.owner_id for a in world.agents}
    graph = dict(world.graph)
    processed = set(world.processed_ids)
    accepted: list[str] = []
    rejected: list[tuple[str, str]] = []
    events = list(world.events)

    def emit(kind: str, actor: str, target: str, amount: int) -> None:
        previous = events[-1].digest if events else "GENESIS"
        seq = len(events) + 1
        content = [world.tick, seq, kind, actor, target, amount, "SIMULATED", previous]
        events.append(Event(world.tick, seq, kind, actor, target, amount,
                            "SIMULATED", previous, _hash(content)))

    for w in sorted(batch.external, key=lambda x: x.region):
        regions[w.region] = w.condition
        emit("weather." + w.condition, "world", w.region, 0)

    # A canonical order avoids nondeterminism from arrival order (not a fair scheduler).
    order = sorted(batch.actions, key=lambda c: (c.request_id, _hash(vars(c))))
    # Reusing an ID with a different payload is ambiguous: reject *every* variant.
    # An identical retry in the same tick retains the first accepted result.
    seen_payloads: dict[str, Action] = {}
    conflicting_ids: set[str] = set()
    for c in order:
        previous = seen_payloads.setdefault(c.request_id, c)
        if previous != c:
            conflicting_ids.add(c.request_id)
    for c in order:
        reason = None
        if c.request_id in conflicting_ids:
            processed.add(c.request_id)
            reason = "conflicting_request_id"
        elif not c.request_id or len(c.request_id) > 128 or c.request_id in processed:
            reason = "duplicate_or_invalid_id"
        else:
            processed.add(c.request_id)
            if c.tick != world.tick:
                reason = "stale_tick"
            elif c.actor not in owners or c.target not in owners:
                reason = "unknown_agent"
            elif not c.principal or owners[c.actor] != c.principal:
                reason = "unauthorized"
            elif c.target not in graph[c.actor]:
                reason = "not_neighbors"
            elif c.kind == "transfer":
                if type(c.amount) is not int or c.amount <= 0:
                    reason = "bad_amount"
                elif balances[c.actor] < c.amount:
                    reason = "insufficient_resources"
                else:
                    balances[c.actor] -= c.amount
                    balances[c.target] += c.amount
                    emit("transfer", c.actor, c.target, c.amount)
            elif c.kind == "signal":
                if type(c.amount) is not int or c.amount != 0:
                    reason = "bad_amount"
                else:
                    emit("signal", c.actor, c.target, 0)
            else:
                reason = "unknown_action"
        if reason:
            rejected.append((c.request_id, reason))
        else:
            accepted.append(c.request_id)
    if sum(balances.values()) != sum(dict(world.balances).values()):
        raise AssertionError("conservation invariant broken")
    canonical_batch = TickInput(batch.tick, tuple(order), tuple(sorted(batch.external,
                                                        key=lambda w: w.region)), max_actions)
    updated = World(world.tick + 1, world.seed, world.agents, world.graph,
                    tuple(sorted(balances.items())), tuple(sorted(regions.items())),
                    tuple(sorted(processed)), tuple(events), world.journal + (canonical_batch,))
    return StepResult(updated, tuple(accepted), tuple(rejected))


def observe(world: World, principal: str, agent_id: str) -> Observation:
    """Only actor/recipient signals and the actor's own balance are visible."""
    agent = next((a for a in world.agents if a.agent_id == agent_id), None)
    if agent is None or not principal or principal != agent.owner_id:
        raise PermissionError("no authenticated permission to observe agent")
    inbox = tuple((e.actor, e.tick) for e in world.events
                  if e.kind == "signal" and e.target == agent_id)
    return Observation(world.tick, agent_id, dict(world.balances)[agent_id],
                       agent.region, dict(world.weather)[agent.region],
                       dict(world.graph)[agent_id], inbox)


def verify_replay(genesis: World, state: World) -> bool:
    """Exact in-memory input journal; no signature, durable audit or real observations."""
    if genesis.tick != 0 or genesis.journal:
        raise ValueError("genesis must be a fresh world")
    rebuilt = genesis
    for batch in state.journal:
        if batch.action_budget is None:
            raise ValueError("replay missing trusted action budget")
        rebuilt = advance(rebuilt, batch, max_actions=batch.action_budget).world
    if rebuilt.fingerprint() != state.fingerprint():
        raise ValueError("replay diverged")
    return True
