# HM-P1e — Cost-aware predictive memory (experimental)

**Issue:** #2 · **Status:** implementation candidate, not production ready.

The runtime keeps three bounded-state Bernoulli predictors: a long-horizon beta-smoothed count, a fast exponentially decayed estimator (0.65), and a slower estimator (0.96). It chooses between them based on exponentially smoothed historical Brier losses (decay 0.92), with a penalty (default 0.007) to avoid paying for adaptation when the long-horizon predictor is competitive.

## Explicit limitations

- Not a Bayesian posterior for a nonstationary process. The gate is a heuristic, not a proved online-regret minimizer.
- Predictions are for binary synthetic outcomes; no language-based memory, multi-agent cognition, general-purpose adaptation, or production access control is implemented.
- `MemoryEvent` in the bootstrap lacks `agent_id`. The `Observation` wrapper carries an explicit `agent_id`; RFC-006 will require it in a versioned event envelope. Migration is required before a stable public API.
- SQLite transactionality is **local**. No cross-shard distributed correctness or authenticated provenance is claimed.
- Retains latest idempotency receipt only for ordinary updates. An old retry fails closed with `StaleRetryError`; no arbitrary-history exactly-once guarantee.
- All `OBSERVED_RECORDED`, `VERIFIED`, protected and contract-relevant events are exact. Our compact synthetic benchmark uses `SIMULATED` reconstructable telemetry. Real-world observations cannot be silently discarded.
- Event integrity hashes detect bit changes when the hash is trusted; they do not authenticate a witness.
- No direct action, tool execution, model API, or network access.

## Commands

```bash
python -m unittest discover -s tests -v
python scripts/check_repository.py
```

W5 independently benchmarks quality, transaction safety, WAL footprint, and baseline comparison. Publish contrary results and failure cases.
