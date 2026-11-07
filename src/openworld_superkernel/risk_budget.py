"""Research-only donor risk budgeting; not an authorization or consent provider.

A donor reserves one worst-case loss unit when W3 accepts a donation.
Known losses and unresolved donations share a hard limit. Only a confirmed,
visible W3 return releases a reserve; missing feedback cannot create credit.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from hashlib import sha256

POLICIES = ("hold", "always_offer", "uncapped_offer", "all_history",
            "fixed_probe", "random_probe", "change_point")
CAP = 4
BREAK_EVEN = 0.25 / 0.85


def draw(seed: int, round_index: int, agent: str, tag: str) -> int:
    if type(seed) is not int or seed < 0 or not isinstance(agent, str):
        raise ValueError("invalid deterministic test inputs")
    return int(sha256(f"{seed}:{round_index}:{agent}:{tag}".encode()).hexdigest()[:12], 16)


@dataclass
class DonorBudget:
    """All values in single-unit synthetic W3 transfers, for one donor only."""
    method: str
    known_bad: int = 0
    pending: set[int] = field(default_factory=set)
    observed: list[int] = field(default_factory=list)
    recent: deque[int] = field(default_factory=lambda: deque(maxlen=4))
    probes: int = 0
    blocked: int = 0
    peak_exposure: int = 0
    hold_until: int = 0

    def __post_init__(self):
        if self.method not in POLICIES:
            raise ValueError("unknown risk policy")

    @property
    def exposure(self) -> int:
        return self.known_bad + len(self.pending)

    def may_issue(self, balance: int) -> bool:
        if type(balance) is not int or balance < 0:
            raise ValueError("invalid W3 balance")
        return balance >= 1 and (
            self.method == "uncapped_offer" or self.exposure < CAP)

    def choose(self, seed: int, tick: int, recipient: str, balance: int) -> bool:
        if type(tick) is not int or not 0 <= tick < 20:
            raise ValueError("invalid experiment round")
        if self.method == "hold" or balance == 0:
            return False
        if not self.may_issue(balance):
            self.blocked += 1
            return False
        if self.method in ("always_offer", "uncapped_offer"):
            return True
        if self.method == "all_history":
            return (1 + sum(self.observed)) / (2 + len(self.observed)) > BREAK_EVEN
        recent = tuple(self.recent)
        reliable = len(recent) >= 2 and sum(recent) / len(recent) > 0.6
        if self.method == "change_point" and tick < self.hold_until:
            reliable = False
        probe = len(self.observed) < 2
        if not reliable and not probe:
            if self.method == "fixed_probe":
                probe = tick % 5 == 0
            else:
                probe = draw(seed, tick, recipient, "probe") % 5 == 0
        if probe and not reliable:
            self.probes += 1
        return bool(reliable or probe)

    def accepted(self, origin: int) -> None:
        if origin in self.pending or (self.method != "uncapped_offer"
                                      and self.exposure >= CAP):
            raise AssertionError("duplicate donation or exhausted budget")
        self.pending.add(origin)
        self.peak_exposure = max(self.peak_exposure, self.exposure)

    def observed_outcome(self, origin: int, returned: bool, at_round: int) -> None:
        if origin not in self.pending:
            raise AssertionError("unissued, missing or double-settled donation")
        self.pending.remove(origin)
        self.known_bad += int(not returned)
        self.observed.append(int(returned))
        self.recent.append(int(returned))
        if self.method == "change_point" and len(self.recent) >= 3:
            last = tuple(self.recent)
            if 1 in last[:-2] and last[-2:] == (0, 0):
                self.hold_until = max(self.hold_until, at_round + 2)
        if self.method != "uncapped_offer" and self.exposure > CAP:
            raise AssertionError("budget invariant violated")
