# RFC-006 — Versioned Agent and Memory Contracts

**Status:** Proposed for owner review  
**Workstream:** W0 Architecture  
**Issue:** #1  
**Scope:** Contract definitions, not a claim of implementation or production readiness.

## 1. Normative terms

**MUST** denotes a condition required before a component can claim compatibility with RFC-006. An **agent** is an identity that can reference shared models; it is not an exclusive model-weights allocation. A **memory record** is not equivalent to a statement verified about the world.

## 2. Versioned interfaces

Every persisted envelope MUST declare `schema_version` (currently `"1.0"`), `event_id` (stable identifier), `owner_id`, `agent_id`, `event_type`, `provenance`, `payload_encoding`, `payload_digest`, and `timestamp_utc` (RFC 3339 UTC). Records MUST carry a monotonically ordered `sequence_number` within a named `stream_id` after successful commit. Event identifiers are unique within a namespace and retries with different content MUST conflict.

A writer MUST reject unknown schema major versions and ambiguous or invalid provenance. Clock time is for human interpretation, NOT a total ordering guarantee. Each stream has an append ordering and a documented consistency scope. A global total order across shards is not assumed.

`agent_id`, `owner_id`, and a runtime `model_ref` are distinct concepts. A genome reference MUST not imply authorization to use another owner's memory. Agent traits and predictive state MAY evolve; `agent_id` MUST remain stable.

## 3. Provenance

| Label | Meaning | Allowed as proof of outside-world event? |
|---|---|---|
| `OBSERVED_RECORDED` | Received a source record, without independent verification | No |
| `VERIFIED` | Source claim passed a defined verification policy | Only with accompanying verification context |
| `INFERRED` | Derived by a model or estimator | No |
| `SIMULATED` | Produced by a declared simulation and inputs | No |
| `UNAVAILABLE` | Insufficient retained information | No |

Every recall response MUST return both its value and provenance; `SIMULATED` and `INFERRED` MUST NOT be promoted to `OBSERVED_RECORDED` or `VERIFIED` by rephrasing. Provenance is about the record's origin, not an unlimited truth guarantee.

## 4. Exact vs compact memory

Protected, consent, payment, ownership-transfer, promise, contract, permission-change, safety-incident and external-action events MUST route to an **exact** ledger. Newly observed external events default to exact unless an explicit, reviewed retention/classification policy permits compaction. A predictive summary or generative program MUST NOT substitute for a legally or operationally required event.

An exact ledger preserves bytes and event ordering **for the declared retention window**, not forever: user-authorized erasure and applicable retention obligations take precedence. A checksum is evidence of data-integrity consistency, not origin authentication. Authenticity requires a trust anchor and identity/key management.

The memory compiler MUST support at least `EXACT`, `PREDICTIVE`, `GENERATIVE`, and `DENY` decisions. Denial covers missing consent, invalid input and unauthorized cross-owner access; permitted records may still be retained for security auditing according to policy.

## 5. Reproducibility and stochastic state

For controlled stochastic process `X[t+1] ~ K_theta(. | X[t], action[t], environment[t])`, generated replay requires the exact algorithm version, floating-point/runtime assumptions, initial checkpoint, PRNG algorithm/seed/counter and all external inputs. A single marginal characteristic function does NOT uniquely identify a time-dependent stochastic process.

A compact predictive state `Z[t]` is sufficient only relative to a defined model family, action space, prediction horizon and evaluation loss. No claim that any fixed-size representation preserves arbitrary history is permitted.

## 6. Security and consent

Actions MUST be checked against scoped, revocable capabilities bound to the requesting principal and target resource. Deny by default. Cross-owner reads require audited grants. Tool responses and retrieved context are untrusted; instructions embedded in them MUST NOT modify capabilities or memory provenance.

## 7. Transaction and recovery semantics

An update which changes both predictive state and protected evidence MUST either commit atomically at its declared local consistency boundary or fail without partial visibility. Recovery MUST recognize already-applied commands without silently accepting divergent retries. In a multi-node deployment, the consistency and failure model must be re-specified; SQLite transactionality is NOT a distributed guarantee.

## 8. Compatibility checklist

1. Reject unknown major schema and invalid provenance.
2. Preserve byte-identical protected events for retention term, plus deterministic commit ordering.
3. Distinguish observed, verified, inferred and simulated recall.
4. Prove idempotent retry / conflicting retry behavior.
5. Prove rollback of state plus evidence on injected failure.
6. Enforce owner isolation and deny-by-default capabilities.
7. Measure resident memory, WAL/runtime disk, CPU, latency and decision quality.
8. Record adverse results, negative controls and limitations.

## 9. Open questions and planned review

- External provenance authorities and key custody.
- Per-class retention schedules and erasure/replication semantics.
- Schema evolution, stream partitioning, and causal order across agents.
- The exact predictive sufficiency test family and regret tolerance.

**Decision:** RFC-006 remains PROPOSED until independently reviewed under Issue #1. Do not declare these guarantees fulfilled just because this file exists.
