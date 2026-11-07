"""Bounded-state exponential weights for prequential Bernoulli forecasting.

No agent policy, LLM, privacy boundary or temporal drift theorem is implied.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class ExponentialWeights:
    """Hedge with square-loss experts; prediction occurs before update.

    For fixed K experts, losses in [0,1] and learning rate eta > 0, the
    cumulative mixture loss is at most the best fixed expert loss plus
    log(K)/eta + eta*T/8, via convexity and the standard Hedge bound.
    This does NOT imply tracking the best switching expert.
    """
    expert_names: tuple[str, ...]
    eta: float = 0.5
    _log_weights: list[float] = field(init=False, repr=False)
    steps: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if (not self.expert_names or len(set(self.expert_names)) != len(self.expert_names)
                or any(not isinstance(n, str) or not n for n in self.expert_names)):
            raise ValueError("unique, nonempty expert names required")
        if not isinstance(self.eta, (int, float)) or not math.isfinite(self.eta) or self.eta <= 0:
            raise ValueError("eta must be finite and strictly positive")
        self._log_weights = [0.0] * len(self.expert_names)

    @property
    def weights(self) -> tuple[float, ...]:
        top = max(self._log_weights)
        scaled = [math.exp(v - top) for v in self._log_weights]
        z = math.fsum(scaled)
        return tuple(v / z for v in scaled)

    def predict(self, expert_probabilities: Sequence[float]) -> float:
        ps = self._validate_predictions(expert_probabilities)
        return math.fsum(w * p for w, p in zip(self.weights, ps))

    def observe(self, expert_probabilities: Sequence[float], outcome: int) -> None:
        """Update weights only after the caller records its pre-outcome prediction."""
        ps = self._validate_predictions(expert_probabilities)
        if type(outcome) is not int or outcome not in (0, 1):
            raise ValueError("outcome must be integer 0 or 1")
        self._log_weights = [w - self.eta * (p - outcome) ** 2
                             for w, p in zip(self._log_weights, ps)]
        # The common shift does not change normalized weights and prevents
        # unbounded negative magnitudes in extremely long trajectories.
        largest = max(self._log_weights)
        self._log_weights = [w - largest for w in self._log_weights]
        self.steps += 1

    def _validate_predictions(self, values: Sequence[float]) -> tuple[float, ...]:
        if len(values) != len(self.expert_names) or any(
            not isinstance(v, (float, int)) or not math.isfinite(v) or v < 0 or v > 1
            for v in values
        ):
            raise ValueError("one finite [0,1] probability per expert required")
        return tuple(float(v) for v in values)

    def fixed_expert_regret_bound(self) -> float:
        return math.log(len(self.expert_names)) / self.eta + self.eta * self.steps / 8.0
