# HM-P1e × Exponential Weights — opt-in research adapter

**Status:** Experimental. Intended for review under Issue #20. No production or real-user approval.

## Decision

Do not replace the original HM-P1e cost-gated predictor. Add an opt-in `EnsembleHyperMemory` subclass that shares its **local SQLite transaction** with an exact-event ledger and an independent, version-pinned exponentially weighted learning state. The base class receives one no-op `_before_observation` hook, invoked only for a new, sequence-valid event **before** it updates the underlying counts.

This is not an authentication, privacy, or distributed transaction system. `requester_owner_id` is provided by the caller rather than cryptographically authenticated.

## Prequential semantics

For every new synthetic observation with outcome `y`, compute `p_static`, `p_fast`, `p_slow` from the **previous** base state. Calculate mixture probability from the **previous** weight state, and only then call `ExponentialWeights.observe(..., y)`. In the same SQLite transaction write the new weights, last prior forecast, cumulative Brier losses, HM-P1e counts, and any exact evidence. Exceptions roll back all lanes together.

The ensemble updates weights on protected and observed events too, but those payloads **remain exact** in the W1 ledger. Only synthetic `SIMULATED/reconstructable=True` telemetry is a valid compact-input benchmark. A provenance tag is not proof of authenticity.

## Persistence and compatibility

- Policy ID: `ow.hm-p1e.hedge.v1`.
- Pinned configuration: exact expert order (`static`, `fast`, `slow`), and learning rate `eta` for the database.
- `ensemble_state` persists step count, normalized log weights, last pre-outcome prediction, and cumulative loss aggregates for each owner/agent.
- Opening an existing HM-P1e database containing nonempty `agent_state` without an ensemble policy fails closed; backfill by explicit, separately tested replay/migration only.
- Reopening with a different `eta` or a conflicting version fails closed.
- A legacy writer modifying `agent_state` without the ensemble lane is detected via mismatched step counts.
- Old retries older than the last receipt remain rejected, not silently considered successful. This is **not** general exactly-once delivery.
- A WAL checkpoint can be blocked by long readers; `synchronous=FULL` does not prove multi-node durability.

## Quality and proof limits

The exponential-weights bound concerns cumulative Brier loss versus the best **fixed** expert from a specified set, not switching-regret, agent intelligence or production accuracy. It does not establish a per-query memory fidelity guarantee. SQLite bytes (including WAL and SHM) and actual cost must be measured independently through W5 before any superiority claim. The ensemble stores O(K) predictive state per agent but keeps protected evidence as required by policy; total storage is not globally O(K).

## Local checks

```bash
python -m unittest discover -s tests -v
python scripts/check_repository.py
```

The adapter-specific tests include atomic rollback, exact byte preservation, conflicting/stale retry, separation of owners and agents, restart, policy/schema mismatch, corruption, and observed vs simulated events. Full integrated-main Gate #11 and W5 multi-seed comparisons remain required before acceptance.
