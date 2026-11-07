"""SEC-003 P1 read-only witness state assessment, never authority reactivation.

No in-process diagnosis can prove a source event or authorize lifting a
pending fence. Recovery requires an independent trusted operator, verified
external historical evidence, and a separately designed commit protocol.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .anti_rollback import (
    MonotonicWitness, WitnessUnavailable, authority_fingerprint,
)


class RecoveryState(str, Enum):
    CONSISTENT = "consistent"
    WITNESS_UNAVAILABLE = "witness_unavailable"
    DIVERGENT = "divergent"
    PENDING_UNCHANGED = "pending_unchanged"
    PENDING_CHANGED = "pending_changed"


@dataclass(frozen=True, slots=True)
class RecoveryAssessment:
    state: RecoveryState
    digest_consistent_without_pending_fence: bool
    observed_digest: str | None
    witnessed_digest: str | None
    witnessed_epoch: int | None
    pending_operation: str | None
    operator_review_required: bool


def assess_authority(authority, witness: MonotonicWitness) -> RecoveryAssessment:
    """Read-only classification of an authority vs its separately held witness.

    This does not issue tokens, unfreeze pending state, or call an external
    service. A clean digest match is only a necessary consistency condition,
    **never** sufficient to authenticate identities or establish deployment.

    In particular, if the witness is pending and the SQLite digest still
    equals the previous digest, the operation may not have happened *or* a
    committed operation may have been rolled back. These are indistinguishable
    from a single current snapshot. Deny in both cases.
    """
    try:
        head = witness.head()
    except WitnessUnavailable:
        return RecoveryAssessment(
            state=RecoveryState.WITNESS_UNAVAILABLE,
            digest_consistent_without_pending_fence=False,
            observed_digest=None,
            witnessed_digest=None,
            witnessed_epoch=None,
            pending_operation=None,
            operator_review_required=True,
        )

    # Read from the *trusted* local authority connection. Any unwrapped
    # concurrent mutation can invalidate a result; the host must serialize.
    try:
        observed = authority_fingerprint(authority.db)
    except Exception:
        # Any unreadable or corrupt DB is not evidence of a safe state.
        return RecoveryAssessment(
            RecoveryState.DIVERGENT, False, None, head.digest, head.epoch,
            head.pending, True,
        )
    if head.pending is not None:
        return RecoveryAssessment(
            RecoveryState.PENDING_UNCHANGED if observed == head.digest
            else RecoveryState.PENDING_CHANGED,
            False, observed, head.digest, head.epoch, head.pending, True,
        )
    if observed != head.digest:
        return RecoveryAssessment(
            RecoveryState.DIVERGENT, False, observed, head.digest,
            head.epoch, None, True,
        )
    return RecoveryAssessment(
        RecoveryState.CONSISTENT, True, observed, head.digest,
        head.epoch, None, False,
    )