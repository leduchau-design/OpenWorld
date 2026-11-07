"""Experimental capability-checked façade for the local W3 world fixture.

This is not a network security boundary: the underlying world reducer remains
public in Python. Trusted host identity and grant handling must be external.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .trust_boundaries import CapabilityAuthority
from .world_fixture import (
    Action, Observation, StepResult, TickInput, Weather, World,
    advance as raw_advance, observe as raw_observe,
)


@dataclass(frozen=True, slots=True)
class AuthorizedWorldAction:
    """A simulated action and its exact owner-scoped bearer authorization."""
    action: Action
    signed_capability: str


class GuardedWorldGateway:
    """A strict simulation gateway; deny cross-owner interactions by default.

    The authenticated_principal callback MUST come from a trusted host. It is
    not an identity provider. All actions are pre-checked before any reducer
    call. W3's in-memory journal does not persist these capability proofs.
    """

    def __init__(self, authority: CapabilityAuthority,
                 authenticated_principal: Callable[[], str]):
        self.authority = authority
        self.authenticated_principal = authenticated_principal

    @staticmethod
    def _owners(world: World) -> dict[str, str]:
        if not isinstance(world, World):
            raise TypeError('expected World fixture')
        return {agent.agent_id: agent.owner_id for agent in world.agents}

    def observe(self, world: World, *, agent_id: str,
                signed_capability: str) -> Observation:
        owners = self._owners(world)
        owner = owners.get(agent_id)
        if owner is None:
            raise PermissionError('unknown observation target')
        self.authority.verify(
            signed_capability,
            authenticated_principal=self.authenticated_principal(),
            owner=owner, resource=agent_id, action='read_world',
        )
        return raw_observe(world, owner, agent_id)

    def advance(self, world: World, *, actions: tuple[AuthorizedWorldAction, ...],
                external: tuple[Weather, ...] = (), max_actions: int = 256) -> StepResult:
        """Preauthorize every action before reducer, preserving all-or-none rejection.

        The external weather inputs are provided by the trusted host, not a
        source-authenticated weather service. Reject unknown identities and
        cross-owner interactions (even a one-way signal) for now.
        """
        if not isinstance(actions, tuple) or not isinstance(external, tuple):
            raise TypeError('actions and external must be immutable tuples')
        if type(max_actions) is not int or max_actions < 0 or len(actions) > max_actions:
            raise ValueError('action budget exceeded')
        owners = self._owners(world)
        principal = self.authenticated_principal()
        if not isinstance(principal, str) or not principal:
            raise PermissionError('authenticated principal unavailable')
        prepared = []
        for entry in actions:
            if not isinstance(entry, AuthorizedWorldAction) or not isinstance(entry.action, Action):
                raise TypeError('expected authorized W3 action')
            action = entry.action
            actor_owner = owners.get(action.actor)
            target_owner = owners.get(action.target)
            if actor_owner is None or target_owner is None:
                raise PermissionError('world actor or target does not exist')
            if actor_owner != target_owner:
                raise PermissionError('cross-owner world interactions require future consent protocol')
            if action.principal != actor_owner:
                raise PermissionError('action claims wrong owner')
            self.authority.verify(
                entry.signed_capability, authenticated_principal=principal,
                owner=actor_owner, resource=action.actor, action='write_agent',
            )
            prepared.append(action)
        return raw_advance(world, TickInput(world.tick, tuple(prepared), external),
                           max_actions=max_actions)
