"""Finite, CPU-only reference mathematics for OpenWorld RFC-007.

This module defines stochastic *models*, not event provenance or permissions.
All distributions are explicit finite probability vectors; no model API is used.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


DEFAULT_TOLERANCE = 1e-10


class ImpossibleObservation(ValueError):
    """An observed symbol has zero probability under the predicted belief."""


def _distribution(values: Sequence[float], *, tolerance: float = DEFAULT_TOLERANCE) -> tuple[float, ...]:
    """Validate a normalized probability vector without altering its entries."""
    if not values or not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("nonempty distribution and positive finite tolerance required")
    if any(not isinstance(p, (int, float)) or not math.isfinite(p) or p < 0 for p in values):
        raise ValueError("probabilities must be nonnegative finite numbers")
    if abs(math.fsum(values) - 1.0) > tolerance:
        raise ValueError("probability vector must sum to one")
    return tuple(float(p) for p in values)


@dataclass(frozen=True)
class FiniteKernel:
    """K: source -> target, with one row-stochastic vector per source state.

    ``first.compose(second)`` means apply first, then second (matrix K @ L).
    """
    source: tuple[str, ...]
    target: tuple[str, ...]
    rows: tuple[tuple[float, ...], ...]

    def __post_init__(self) -> None:
        if (not self.source or not self.target or
                any(not isinstance(s, str) or not s for s in (*self.source, *self.target)) or
                len(set(self.source)) != len(self.source) or
                len(set(self.target)) != len(self.target)):
            raise ValueError("supports must be nonempty, uniquely named state tuples")
        if len(self.rows) != len(self.source):
            raise ValueError("row count must match source support")
        for row in self.rows:
            if len(row) != len(self.target):
                raise ValueError("row length must match target support")
            _distribution(row)

    @classmethod
    def identity(cls, states: tuple[str, ...]) -> "FiniteKernel":
        return cls(states, states, tuple(
            tuple(float(i == j) for j in range(len(states)))
            for i in range(len(states))
        ))

    def compose(self, after: "FiniteKernel") -> "FiniteKernel":
        """Return composition: apply this kernel, then ``after``."""
        if self.target != after.source:
            raise ValueError("incompatible ordered intermediate supports")
        rows = tuple(tuple(
            math.fsum(self.rows[i][k] * after.rows[k][j]
                      for k in range(len(self.target)))
            for j in range(len(after.target)))
            for i in range(len(self.source)))
        return FiniteKernel(self.source, after.target, rows)



@dataclass(frozen=True)
class ControlledKernel:
    """Action-indexed finite transition kernels with a shared ordered support."""
    actions: tuple[str, ...]
    kernels: tuple[FiniteKernel, ...]

    def __post_init__(self) -> None:
        if (not self.actions or len(self.actions) != len(self.kernels)
                or any(not isinstance(a, str) or not a for a in self.actions)
                or len(set(self.actions)) != len(self.actions)):
            raise ValueError("unique action names and matching kernels required")
        first = self.kernels[0]
        if any(k.source != first.source or k.target != first.target
               for k in self.kernels):
            raise ValueError("all actions must share ordered source/target support")

    def for_action(self, action: str) -> FiniteKernel:
        """Fail closed on an unknown action rather than selecting a default."""
        try:
            return self.kernels[self.actions.index(action)]
        except ValueError as exc:
            raise ValueError(f"unknown action: {action}") from exc



def predict_belief(prior: Sequence[float], transition: FiniteKernel) -> tuple[float, ...]:
    """Push forward a belief through the transition matrix."""
    if len(prior) != len(transition.source):
        raise ValueError("prior and transition support lengths differ")
    p = _distribution(prior)
    predicted = tuple(math.fsum(p[i] * transition.rows[i][j]
                                for i in range(len(p)))
                      for j in range(len(transition.target)))
    return _distribution(predicted)


def condition_on_observation(predicted: Sequence[float],
                             likelihood: Sequence[float]) -> tuple[float, ...]:
    """Bayes conditioning for P(observation | next_state).

    Likelihoods need not sum to one across states; each must be in [0, 1].
    """
    p = _distribution(predicted)
    if len(likelihood) != len(p) or any(
        not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or v > 1
        for v in likelihood
    ):
        raise ValueError("likelihood must be finite, in [0, 1], and match support")
    weighted = tuple(a * b for a, b in zip(p, likelihood))
    evidence = math.fsum(weighted)
    if evidence <= 0:
        raise ImpossibleObservation("zero-likelihood observation")
    return _distribution(tuple(v / evidence for v in weighted))


def bayes_filter(prior: Sequence[float], transition: FiniteKernel,
                 likelihood: Sequence[float]) -> tuple[float, ...]:
    """Predict then condition; no silent fallback on impossible observations."""
    return condition_on_observation(predict_belief(prior, transition), likelihood)


def total_variation(p: Sequence[float], q: Sequence[float]) -> float:
    """Finite TV distance for *matched and ordered* outcome supports."""
    if len(p) != len(q):
        raise ValueError("probability vectors require the same outcome support")
    left, right = _distribution(p), _distribution(q)
    return 0.5 * math.fsum(abs(a - b) for a, b in zip(left, right))


def task_relative_equivalence(p: Sequence[float], q: Sequence[float],
                              *, epsilon: float) -> bool:
    """Compare declared query outcome laws; this is NOT a universal sufficiency oracle."""
    if not math.isfinite(epsilon) or epsilon < 0 or epsilon > 1:
        raise ValueError("epsilon must lie in [0, 1]")
    return total_variation(p, q) <= epsilon + DEFAULT_TOLERANCE


def two_sign_process(q_keep: float, u: float) -> dict[str, float]:
    """A stationary two-sign Markov process: P(X_t = +/-1) = 1/2.

    Marginal characteristic function is cos(u), while lag-one correlation
    depends on q_keep. This is an analytical counterexample, not replay.
    """
    if not isinstance(q_keep, (int, float)) or not math.isfinite(q_keep) or not (0 <= q_keep <= 1):
        raise ValueError("q_keep must be in [0, 1]")
    if not isinstance(u, (int, float)) or not math.isfinite(u):
        raise ValueError("u must be a finite real number")
    return {"p_positive": 0.5,
            "marginal_cf_real": math.cos(u),
            "lag_one_correlation": 2.0 * q_keep - 1.0,
            "p_same_sign": float(q_keep)}


def exact_outcome_from_counts(n: int, successes: int, index: int) -> int | str:
    """Toy Bernoulli-count query; return UNAVAILABLE if exact history was lost.

    A degenerate all-success/all-failure count determines every recorded bit.
    Otherwise multiple histories share the same summary, so the indexed
    outcome cannot be inferred. This is NOT a ledger implementation.
    """
    if (type(n) is not int or type(successes) is not int or type(index) is not int
            or n < 0 or successes < 0 or successes > n or index < 0 or index >= n):
        raise ValueError("invalid count summary or query index")
    if successes == 0:
        return 0
    if successes == n:
        return 1
    return "UNAVAILABLE"
