"""Experimental bounded predictive-memory encoders, NOT the HyperMemory default.

These models track synthetic Bernoulli feedback only. They do not authenticate
events, own identities, issue grants, replace the protected exact ledger, or
provide general sequence replay. All predictions are computed before updates.
"""
from __future__ import annotations

import math

MODELS = ("full_history", "beta_counts", "discounted", "markov", "markov_fourier")


def _step(step: int, last: int) -> None:
    if type(step) is not int or step < 0 or step <= last:
        raise ValueError("step must be a new nonnegative integer")


def _outcome(outcome: int) -> None:
    if type(outcome) is not int or outcome not in (0, 1):
        raise ValueError("observed Bernoulli outcome must be 0 or 1")


def _probability(p: float) -> float:
    return max(0.000001, min(0.999999, p))


class FullHistory:
    """Exact sequence of observed *synthetic labels*, not protected event audit."""

    def __init__(self) -> None:
        self.history: list[tuple[int, int]] = []
        self.last_step = -1

    def predict(self, step: int) -> float:
        _step(step, self.last_step)
        # Deliberately recompute from retained history; no hidden count cache.
        return (1 + sum(y for _, y in self.history)) / (2 + len(self.history))

    def observe(self, step: int, outcome: int) -> None:
        _step(step, self.last_step)
        _outcome(outcome)
        self.history.append((step, outcome))
        self.last_step = step

    def exact_observed_outcome(self, step: int) -> int | str:
        for t, y in self.history:
            if t == step:
                return y
        return "UNAVAILABLE"

    def snapshot(self) -> dict:
        return {"model": "full_history", "history": self.history, "last_step": self.last_step}


class BetaCounts:
    """Fixed Beta(1,1) Bernoulli prior, sufficient counts for IID trials."""

    def __init__(self) -> None:
        self.n = 0
        self.successes = 0
        self.last_step = -1

    def predict(self, step: int) -> float:
        _step(step, self.last_step)
        return (1 + self.successes) / (2 + self.n)

    def observe(self, step: int, outcome: int) -> None:
        _step(step, self.last_step)
        _outcome(outcome)
        self.successes += outcome
        self.n += 1
        self.last_step = step

    def exact_observed_outcome(self, step: int) -> str:
        return "UNAVAILABLE"

    def snapshot(self) -> dict:
        return {"model": "beta_counts", "n": self.n,
                "successes": self.successes, "last_step": self.last_step}


class Discounted:
    """Geometric decay at 0.85; no exact-time reconstruction."""

    DECAY = 0.85

    def __init__(self) -> None:
        self.weight = 0.0
        self.success_weight = 0.0
        self.last_step = -1

    def predict(self, step: int) -> float:
        _step(step, self.last_step)
        return (1 + self.success_weight) / (2 + self.weight)

    def observe(self, step: int, outcome: int) -> None:
        _step(step, self.last_step)
        _outcome(outcome)
        self.weight = self.DECAY * self.weight + 1.0
        self.success_weight = self.DECAY * self.success_weight + outcome
        self.last_step = step

    def exact_observed_outcome(self, step: int) -> str:
        return "UNAVAILABLE"

    def snapshot(self) -> dict:
        return {"model": "discounted", "weight": self.weight,
                "success_weight": self.success_weight, "last_step": self.last_step}


class Markov(BetaCounts):
    """Two-state first-order transition counts plus a marginal fallback.

    A transition is observed only between *consecutive* fully observed ticks.
    Missing feedback cannot be bridged by inventing the unobserved state.
    """

    def __init__(self) -> None:
        super().__init__()
        self.transitions = [[0, 0], [0, 0]]
        self.last_outcome: int | None = None

    def predict(self, step: int) -> float:
        base = super().predict(step)
        if self.last_step != step - 1 or self.last_outcome is None:
            return base
        row = self.transitions[self.last_outcome]
        if sum(row) < 2:
            return base
        return (1 + row[1]) / (2 + sum(row))

    def observe(self, step: int, outcome: int) -> None:
        _step(step, self.last_step)
        _outcome(outcome)
        if self.last_step == step - 1 and self.last_outcome is not None:
            self.transitions[self.last_outcome][outcome] += 1
        super().observe(step, outcome)
        self.last_outcome = outcome

    def snapshot(self) -> dict:
        state = super().snapshot()
        state.update(model="markov", transitions=self.transitions,
                     last_outcome=self.last_outcome)
        return state


class MarkovFourier(Markov):
    """Markov + online 1-harmonic time-phase regression, fixed research knobs.

    The 12-tick period is a *task assumption*, deliberately a positive control
    for periodic test data, not a universally learned frequency or ECF.
    With Bernoulli outcomes, the marginal characteristic function is already
    determined by p; a new Fourier transform of that marginal adds no facts.
    """

    LR = 0.08

    def __init__(self, *, period: int = 12) -> None:
        super().__init__()
        if type(period) is not int or not 3 <= period <= 64:
            raise ValueError("period must be in [3, 64]")
        self.period = period
        self.weights = [0.5, 0.0, 0.0]

    def _features(self, step: int) -> tuple[float, float, float]:
        phase = 2.0 * math.pi * (step % self.period) / self.period
        return (1.0, math.cos(phase), math.sin(phase))

    def predict(self, step: int) -> float:
        p_markov = super().predict(step)
        if self.n < 8:
            return p_markov
        seasonal = sum(w * x for w, x in zip(self.weights, self._features(step)))
        return _probability(0.5 * p_markov + 0.5 * seasonal)

    def observe(self, step: int, outcome: int) -> None:
        _step(step, self.last_step)
        _outcome(outcome)
        features = self._features(step)
        prediction = sum(w * x for w, x in zip(self.weights, features))
        error = outcome - prediction
        self.weights = [
            max(-1.0, min(1.0, w + self.LR * error * x))
            for w, x in zip(self.weights, features)
        ]
        super().observe(step, outcome)

    def snapshot(self) -> dict:
        state = super().snapshot()
        state.update(model="markov_fourier", period=self.period,
                     weights=self.weights)
        return state


def make_model(name: str, *, period: int = 12):
    if name == "full_history":
        return FullHistory()
    if name == "beta_counts":
        return BetaCounts()
    if name == "discounted":
        return Discounted()
    if name == "markov":
        return Markov()
    if name == "markov_fourier":
        return MarkovFourier(period=period)
    raise ValueError("unknown research memory representation")
