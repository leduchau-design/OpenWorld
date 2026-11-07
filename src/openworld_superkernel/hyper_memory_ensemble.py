"""Opt-in, SQLite-atomic HM-P1e/ExponentialWeights research adapter.

Experimental Bernoulli-only predictive state. This module does not authenticate
claims, authorize tools, reconstruct discarded observations, or provide a
multi-node transaction protocol.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .hyper_memory_p1e import HyperMemoryP1e, Observation, _probabilities
from .online_ensemble import ExponentialWeights


EXPERTS = ("static", "fast", "slow")
POLICY_VERSION = "ow.hm-p1e.hedge.v1"


class IncompatibleMemoryPolicy(ValueError):
    """Existing states cannot be reinterpreted under a changed policy."""


class EnsembleStateCorrupted(ValueError):
    """Persistent ensemble state disagrees with the base state or schema."""


class EnsembleHyperMemory(HyperMemoryP1e):
    """HM-P1e with opt-in prequential exponential weights.

    Base state, ensemble update, and protected ledger all use the *same*
    SQLite BEGIN IMMEDIATE/COMMIT boundary. Not suitable for untrusted users.
    """

    def __init__(self, path: str | Path, *, eta: float = 0.5):
        # Validate before creating/changing any database file.
        ExponentialWeights(EXPERTS, eta=eta)
        super().__init__(path)
        self.eta = float(eta)
        try:
            self._initialize_ensemble_tables()
        except BaseException:
            self.close()
            raise

    def _initialize_ensemble_tables(self) -> None:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("""CREATE TABLE IF NOT EXISTS ensemble_policy (
                id INTEGER PRIMARY KEY CHECK(id=1), version TEXT NOT NULL,
                eta REAL NOT NULL, experts_json TEXT NOT NULL)""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS ensemble_state (
                owner_id TEXT NOT NULL, agent_id TEXT NOT NULL,
                state_json TEXT NOT NULL,
                PRIMARY KEY(owner_id, agent_id))""")
            policy = self.db.execute("SELECT version, eta, experts_json FROM ensemble_policy WHERE id=1").fetchone()
            if policy is None:
                # Upgrading an existing HM-P1e store without a replay/migration
                # would silently lose historical prequential weights.
                if self.db.execute("SELECT 1 FROM agent_state LIMIT 1").fetchone() is not None:
                    raise IncompatibleMemoryPolicy("existing base memory needs explicit replay migration")
                self.db.execute(
                    "INSERT INTO ensemble_policy VALUES(1,?,?,?)",
                    (POLICY_VERSION, self.eta, json.dumps(EXPERTS)))
            elif policy != (POLICY_VERSION, self.eta, json.dumps(EXPERTS)):
                raise IncompatibleMemoryPolicy("pinned ensemble version/eta/expert order mismatch")
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _load_estimator(self, owner_id: str, agent_id: str,
                        previous_sequence: int) -> tuple[ExponentialWeights, dict]:
        row = self.db.execute(
            "SELECT state_json FROM ensemble_state WHERE owner_id=? AND agent_id=?",
            (owner_id, agent_id)).fetchone()
        learner = ExponentialWeights(EXPERTS, eta=self.eta)
        if row is None:
            if previous_sequence != 0:
                raise EnsembleStateCorrupted("base state without matching ensemble state")
            return learner, {"mix_loss": 0.0, "expert_losses": [0.0] * len(EXPERTS)}
        try:
            saved = json.loads(row[0])
            weights = saved["log_weights"]
            losses = saved["expert_losses"]
            step = saved["steps"]
            if (saved["version"] != POLICY_VERSION or
                type(step) is not int or step != previous_sequence or
                len(weights) != len(EXPERTS) or len(losses) != len(EXPERTS) or
                not all(isinstance(x, (int, float)) and math.isfinite(x) for x in (*weights, *losses)) or
                not isinstance(saved["mix_loss"], (float, int)) or
                not math.isfinite(saved["mix_loss"]) or saved["mix_loss"] < 0 or
                any(x < 0 for x in losses)):
                raise ValueError("invalid estimator state")
            learner._log_weights = list(map(float, weights))
            learner.steps = step
            return learner, saved
        except (TypeError, ValueError, KeyError) as exc:
            raise EnsembleStateCorrupted("invalid persisted ensemble state") from exc

    def _before_observation(self, item: Observation, prior: dict[str, float],
                            previous_state: dict) -> None:
        learner, saved = self._load_estimator(
            item.event.owner_id, item.agent_id, previous_state["seq"])
        ps = tuple(prior[name] for name in EXPERTS)
        # Prequential: calculate first, then update with current outcome.
        prediction = learner.predict(ps)
        mixture_loss = (prediction - item.outcome) ** 2
        expert_losses = [(p - item.outcome) ** 2 for p in ps]
        learner.observe(ps, item.outcome)
        next_state = {
            "version": POLICY_VERSION,
            "steps": learner.steps,
            "log_weights": learner._log_weights,
            "last_prequential_prediction": prediction,
            "last_prequential_experts": list(ps),
            "mix_loss": saved["mix_loss"] + mixture_loss,
            "expert_losses": [a + b for a, b in zip(saved["expert_losses"], expert_losses)],
        }
        self.db.execute(
            "INSERT INTO ensemble_state(owner_id,agent_id,state_json) VALUES(?,?,?) "
            "ON CONFLICT(owner_id,agent_id) DO UPDATE SET state_json=excluded.state_json",
            (item.event.owner_id, item.agent_id,
             json.dumps(next_state, separators=(",", ":"))),
        )

    def get_ensemble_state(self, *, owner_id: str, agent_id: str,
                           requester_owner_id: str) -> dict:
        base = self.get_state(owner_id=owner_id, agent_id=agent_id,
                              requester_owner_id=requester_owner_id)
        learner, saved = self._load_estimator(owner_id, agent_id, base["seq"])
        return {"version": POLICY_VERSION, "steps": learner.steps,
                "weights": learner.weights, "cumulative_mix_brier": saved["mix_loss"],
                "cumulative_expert_brier": tuple(saved["expert_losses"]),
                "last_prequential_prediction": saved.get("last_prequential_prediction")}

    def predict(self, *, owner_id: str, agent_id: str,
                requester_owner_id: str) -> tuple[float, str]:
        base = self.get_state(owner_id=owner_id, agent_id=agent_id,
                              requester_owner_id=requester_owner_id)
        learner, _saved = self._load_estimator(owner_id, agent_id, base["seq"])
        probs = _probabilities(base)
        return learner.predict(tuple(probs[name] for name in EXPERTS)), "ensemble"
