"""Pure P0 institution-charter proposals for a trusted single-owner W3 world.

No runtime mutation, capability issuance, membership change, policy execution,
cross-owner consent, federation or automatic approval. Reviewer must operate
outside untrusted agent code and independently authorize any future action.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from .population_links import PopulationLink, PopulationRouter
from .world_fixture import World


@dataclass(frozen=True)
class CharterProposal:
    proposal_id: str
    proposed_owner: str
    members: tuple[str, ...]
    purpose: str
    links: tuple[PopulationLink, ...]
    max_total_actions_per_tick: int
    expected_world_tick: int
    expires_at_tick: int


@dataclass(frozen=True)
class CharterReview:
    proposal_digest: str
    verdict: str
    reasons: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return self.verdict == "ELIGIBLE_FOR_OWNER_REVIEW"


def _validated(proposal: CharterProposal) -> None:
    if not isinstance(proposal, CharterProposal):
        raise TypeError("expected immutable charter proposal")
    if (not isinstance(proposal.proposal_id, str) or not proposal.proposal_id
            or len(proposal.proposal_id) > 128
            or not isinstance(proposal.proposed_owner, str) or not proposal.proposed_owner
            or not isinstance(proposal.purpose, str) or not proposal.purpose
            or len(proposal.purpose) > 256):
        raise ValueError("invalid charter metadata")
    if (not isinstance(proposal.members, tuple) or not 2 <= len(proposal.members) <= 30
            or any(not isinstance(m, str) or not m for m in proposal.members)
            or len(set(proposal.members)) != len(proposal.members)
            or proposal.members != tuple(sorted(proposal.members))):
        raise ValueError("members must be sorted unique registered IDs")
    if (not isinstance(proposal.links, tuple) or not 1 <= len(proposal.links) <= 16
            or any(not isinstance(link, PopulationLink) for link in proposal.links)
            or len({(link.source, link.destination) for link in proposal.links})
                != len(proposal.links)):
        raise ValueError("invalid or duplicate charter link requests")
    if (type(proposal.max_total_actions_per_tick) is not int or
            not 1 <= proposal.max_total_actions_per_tick <= 32
            or type(proposal.expected_world_tick) is not int or
            proposal.expected_world_tick < 0
            or type(proposal.expires_at_tick) is not int or
            proposal.expires_at_tick <= proposal.expected_world_tick
            or proposal.expires_at_tick - proposal.expected_world_tick > 100):
        raise ValueError("invalid charter budget or validity")


def _digest(proposal: CharterProposal) -> str:
    fields = {
        "format": "openworld.charter.proposal.v0",
        "id": proposal.proposal_id,
        "owner": proposal.proposed_owner,
        "members": proposal.members,
        "purpose": proposal.purpose,
        "links": [(l.source, l.destination, l.kinds, l.max_transfer,
                   l.max_actions_per_tick) for l in proposal.links],
        "max_total_actions_per_tick": proposal.max_total_actions_per_tick,
        "expected_world_tick": proposal.expected_world_tick,
        "expires_at_tick": proposal.expires_at_tick,
    }
    raw = json.dumps(fields, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False).encode()
    return "sha256:" + sha256(raw).hexdigest()


def review_charter(world: World, router: PopulationRouter,
                   proposal: CharterProposal, *,
                   trusted_owner: str) -> CharterReview:
    """Return a non-binding recommendation; cannot add rights or edit state.

    The caller-provided owner is only a trusted-host claim; this function does
    not authenticate users. An eligible proposal still needs external independent
    authorization and does NOT alter the router or W3 world.
    """
    if not isinstance(world, World) or not isinstance(router, PopulationRouter):
        raise TypeError("expected existing W3 world and configured router")
    _validated(proposal)
    if not isinstance(trusted_owner, str) or not trusted_owner:
        raise PermissionError("trusted host owner unavailable")
    reasons: list[str] = []
    if proposal.proposed_owner != trusted_owner:
        reasons.append("owner_claim_mismatch")
    if world.tick != proposal.expected_world_tick or world.tick >= proposal.expires_at_tick:
        reasons.append("stale_or_expired_charter")
    owners = {a.agent_id: a.owner_id for a in world.agents}
    if set(owners) != set(router.membership):
        reasons.append("roster_drift")
    if any(m not in owners for m in proposal.members):
        reasons.append("unknown_member")
    if any(owners.get(m) != proposal.proposed_owner for m in proposal.members):
        reasons.append("cross_owner_member")
    represented = {router.membership.get(m) for m in proposal.members}
    total_requested = 0
    for requested in proposal.links:
        existing = router.links.get((requested.source, requested.destination))
        if existing is None:
            reasons.append("unapproved_link")
            continue
        if (not isinstance(requested.kinds, tuple) or not requested.kinds
                or set(requested.kinds) - set(existing.kinds)):
            reasons.append("action_scope_escalation")
        if (type(requested.max_transfer) is not int or
                requested.max_transfer < 0 or
                requested.max_transfer > existing.max_transfer or
                type(requested.max_actions_per_tick) is not int or
                requested.max_actions_per_tick < 1 or
                requested.max_actions_per_tick > existing.max_actions_per_tick):
            reasons.append("quota_escalation")
        else:
            total_requested += requested.max_actions_per_tick
        if requested.source not in represented or requested.destination not in represented:
            reasons.append("unrepresented_group")
    if total_requested > proposal.max_total_actions_per_tick:
        reasons.append("aggregate_quota_exceeded")
    unique = tuple(sorted(set(reasons)))
    return CharterReview(
        _digest(proposal),
        "REJECTED" if unique else "ELIGIBLE_FOR_OWNER_REVIEW",
        unique,
    )
