"""W3 P0: local, same-owner population exchange over the existing guarded world.

This is a research adapter, not federation, a new owner-consent protocol, a
network listener, or an independent identity provider. Untrusted Python code
must not run in the trusted host; the raw W3 reducer remains importable.
"""
from __future__ import annotations

from dataclasses import dataclass

from .world_fixture import Action, Event, StepResult, Weather, World
from .world_guard import AuthorizedWorldAction, GuardedWorldGateway


@dataclass(frozen=True)
class Population:
    group_id: str
    members: tuple[str, ...]


@dataclass(frozen=True)
class PopulationLink:
    """Directional, host-reviewed local interaction policy (not cross-owner consent)."""
    source: str
    destination: str
    kinds: tuple[str, ...]
    max_transfer: int = 0
    max_actions_per_tick: int = 1


@dataclass(frozen=True)
class Exchange:
    """Intent for one W3 action; both resource grants are required."""
    source_group: str
    destination_group: str
    action: Action
    actor_capability: str
    target_capability: str


@dataclass(frozen=True)
class PopulationStep:
    state: StepResult
    events_added: tuple[Event, ...]


class PopulationRouter:
    """Explicit group membership + contracts; all permission checks precede W3.

    The *two* capabilities may originate from the same authenticated principal.
    They are not evidence of independent receiver consent or bilateral owners.
    W3 records accepted simulator events but NOT the two grants or their outcome.
    """

    def __init__(self, gateway: GuardedWorldGateway,
                 populations: tuple[Population, ...],
                 links: tuple[PopulationLink, ...]):
        if not isinstance(gateway, GuardedWorldGateway):
            raise TypeError("a guarded W3 gateway is required")
        if not isinstance(populations, tuple) or not 2 <= len(populations) <= 32:
            raise ValueError("expected 2..32 local populations")
        membership: dict[str, str] = {}
        groups: set[str] = set()
        for pop in populations:
            if (not isinstance(pop, Population) or not isinstance(pop.group_id, str)
                    or not pop.group_id or len(pop.group_id) > 80
                    or pop.group_id in groups or not isinstance(pop.members, tuple)
                    or not pop.members):
                raise ValueError("invalid or duplicate population")
            groups.add(pop.group_id)
            for member in pop.members:
                if (not isinstance(member, str) or not member
                        or len(member) > 128 or member in membership):
                    raise ValueError("ambiguous or invalid population membership")
                membership[member] = pop.group_id
        if len(membership) > 300:
            raise ValueError("fixture population budget exceeded")
        if not isinstance(links, tuple):
            raise TypeError("population links must be a tuple")
        allowed: dict[tuple[str, str], PopulationLink] = {}
        for link in links:
            if (not isinstance(link, PopulationLink) or
                    link.source not in groups or link.destination not in groups or
                    link.source == link.destination or
                    not isinstance(link.kinds, tuple) or not link.kinds or
                    len(set(link.kinds)) != len(link.kinds) or
                    any(kind not in {"signal", "transfer"} for kind in link.kinds) or
                    type(link.max_transfer) is not int or link.max_transfer < 0 or
                    type(link.max_actions_per_tick) is not int or
                    not 1 <= link.max_actions_per_tick <= 32):
                raise ValueError("invalid population link contract")
            key = (link.source, link.destination)
            if key in allowed:
                raise ValueError("duplicate population link")
            allowed[key] = link
        self.gateway = gateway
        self.populations = populations
        self.membership = membership
        self.links = allowed

    def advance(self, world: World, *, exchanges: tuple[Exchange, ...],
                external: tuple[Weather, ...] = (),
                max_actions: int = 32) -> PopulationStep:
        """Validate every exchange and target grant before invoking W3 once.

        A failed precheck leaves the supplied immutable world unchanged. W3 may
        reject validly authorized intents for resource shortages; that is a
        committed simulated tick and is reported, not silently retried.
        """
        if not isinstance(world, World):
            raise TypeError("expected world")
        if (not isinstance(exchanges, tuple) or not isinstance(external, tuple)
                or type(max_actions) is not int or not 0 <= max_actions <= 256
                or len(exchanges) > max_actions):
            raise ValueError("invalid action budget or batch")
        owners = {agent.agent_id: agent.owner_id for agent in world.agents}
        if set(self.membership) != set(owners):
            raise ValueError("population roster must exactly cover world agents")
        graph = dict(world.graph)
        principal = self.gateway.authenticated_principal()
        if not isinstance(principal, str) or not principal:
            raise PermissionError("trusted principal required")
        requests: set[str] = set()
        usage: dict[tuple[str, str], int] = {}
        authorized = []
        for e in exchanges:
            if not isinstance(e, Exchange) or not isinstance(e.action, Action):
                raise TypeError("invalid exchange")
            a = e.action
            if (not isinstance(a.request_id, str) or not a.request_id
                    or len(a.request_id) > 128 or a.request_id in requests
                    or a.request_id in world.processed_ids):
                raise ValueError("invalid or duplicate request ID")
            requests.add(a.request_id)
            if (a.tick != world.tick or
                    self.membership.get(a.actor) != e.source_group or
                    self.membership.get(a.target) != e.destination_group):
                raise PermissionError("exchange does not match current membership/tick")
            link_key = (e.source_group, e.destination_group)
            contract = self.links.get(link_key)
            if contract is None or a.kind not in contract.kinds:
                raise PermissionError("no directional population contract")
            if a.target not in graph[a.actor]:
                raise PermissionError("population link lacks W3 adjacency")
            if owners[a.actor] != owners[a.target] or a.principal != owners[a.actor]:
                raise PermissionError("cross-owner or forged-owner exchange denied")
            if ((a.kind == "signal" and a.amount != 0) or
                    (a.kind == "transfer" and
                     (type(a.amount) is not int or a.amount < 1 or
                      a.amount > contract.max_transfer))):
                raise ValueError("amount violates population contract")
            usage[link_key] = usage.get(link_key, 0) + 1
            if usage[link_key] > contract.max_actions_per_tick:
                raise PermissionError("link quota exceeded")
            # Target grant proves an authorization for the same trusted owner,
            # not receiver intent, independent signatures or cross-owner consent.
            self.gateway.authority.verify(
                e.target_capability,
                authenticated_principal=principal,
                owner=owners[a.target],
                resource=a.target,
                action="write_agent",
            )
            authorized.append(AuthorizedWorldAction(a, e.actor_capability))
        start = len(world.events)
        result = self.gateway.advance(
            world, actions=tuple(authorized), external=external,
            max_actions=max_actions,
        )
        return PopulationStep(result, result.world.events[start:])
