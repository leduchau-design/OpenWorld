"""Minimal, safe-by-default memory routing contracts.

This is intentionally NOT the finished HyperMemory compiler.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Provenance(str, Enum):
    OBSERVED_RECORDED = "observed_recorded"
    VERIFIED = "verified"
    INFERRED = "inferred"
    SIMULATED = "simulated"
    UNAVAILABLE = "unavailable"


class MemoryRoute(str, Enum):
    EXACT = "exact"
    PREDICTIVE = "predictive"
    GENERATIVE = "generative"


EXACT_EVENT_TYPES = frozenset({
    "consent", "payment", "ownership_transfer", "promise", "contract",
    "permission_change", "safety_incident", "external_action",
})


@dataclass(frozen=True, slots=True)
class MemoryEvent:
    event_id: str
    owner_id: str
    event_type: str
    provenance: Provenance
    payload: bytes
    reconstructable: bool = False
    protected: bool = False

    def __post_init__(self) -> None:
        if not self.event_id or not self.owner_id or not self.event_type:
            raise ValueError("event_id, owner_id, and event_type are required")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be an explicit Provenance value")
        if not isinstance(self.payload, bytes):
            raise TypeError("payload must be raw bytes")


def route_memory_event(event: MemoryEvent) -> MemoryRoute:
    """Conservative routing: keep unknown cases exactly."""
    if event.protected or event.event_type in EXACT_EVENT_TYPES:
        return MemoryRoute.EXACT
    if event.provenance in (Provenance.OBSERVED_RECORDED, Provenance.VERIFIED):
        return MemoryRoute.EXACT
    if event.provenance == Provenance.SIMULATED and event.reconstructable:
        return MemoryRoute.GENERATIVE
    if event.provenance == Provenance.INFERRED:
        return MemoryRoute.PREDICTIVE
    return MemoryRoute.EXACT
