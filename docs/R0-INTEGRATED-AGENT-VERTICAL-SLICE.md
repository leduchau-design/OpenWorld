# R0 — Integrated Agent Vertical Slice

**Status:** Implementation target, not a shipped unified SuperKernel. R0 does not authorize real-world actions or cross-owner interactions. Independent gate [#11](https://github.com/CocAgent/OpenWorld/issues/11) remains open.

## Why

The existing repository has useful but separate memory, world, capability and population research fixtures. R0 must demonstrate a single **trusted-host, CPU-only, deterministic, same-owner, simulated** agent cycle. A user should understand and run it in one command, with failure modes shown, before new workstreams are admitted.

## Minimal cycle

1. Set a local agent goal and obtain an owner-scoped, capability-checked world observation.
2. Read a provenance-aware predictive memory state; label prediction as **INFERRED** and world evidence as **SIMULATED**.
3. Select a bounded action via a transparent rule, including the no-transfer/abstain baseline.
4. Verify host-provided principal, actor/recipient ownership, capability, resource and per-tick budget; deny by default.
5. Execute **only** the local W3 reducer; account for all resources.
6. Record a labeled simulated outcome in HyperMemory; never promote it to verified/real evidence.
7. Reconstruct W3 state from recorded inputs; expose accepted/rejected IDs, digest and memory evidence for inspection.

## Critical transaction boundary

The in-memory W3 reducer and SQLite HM-P1e are **not one atomic transaction**. A successful local demonstration cannot claim a durable, exactly-once action+memory commit, crash recovery, external action safety, or persistent revocation. An in-memory capability issuer is not authenticated identity. Cross-owner consent and PostgreSQL source-of-truth remain separate research gates (#34, #35, #42). Any crash between W3 and HM-P1e must be disclosed, never concealed as an atomic commit.

## Acceptance matrix

| Gate | Evidence and failure control | Status |
|---|---|---|
| G1 Onboarding | Single documented local command on clean Python 3.11+, no model key/cloud | Pending independent run |
| G2 Integration | Observe → predict → authorize → act → record → replay in one walkthrough | Pending integration |
| G3 Safety | Missing/revoked/expired/wrong-owner grants; budget/insufficient resources; replay divergence | Pending integrated negative tests |
| G4 Scientific utility | Compare fixed hold, fixed-rule and memory-aware policies with equal opportunities, task-specific reward, holdout seed families; retain losing results | Not demonstrated |
| G5 Reproducibility | Exact SHA, Python/SQLite versions, OS/CPU, seed, raw results, CPU/RSS/WAL and independent second reviewer | Gate #11 OPEN |

Passing unit tests does not imply G4 or G5. An illustrative one-seed demo is not a benchmark. Protected real-world events and external tools are forbidden in R0.

## Future admission sequence

- **R0** Integrate a reproducible agent cycle without hidden model services.
- **R1** Multiple independent agent cycles and bounded same-owner coordination; retain deterministic replay.
- **R2** Learn/adapt only when held-out decision utility exceeds fixed baselines net of actual compute and exposure costs.
- **R3** Authenticate distinct owners, implement bilateral consent and one authoritative transaction with safe retries before cross-owner effects.
- **R4** Scale measured workloads with budgets, resource controls, privacy, recovery and independent replication; no population-number extrapolation.

The W0–W5 modules are workstreams, not release stages. Earlier R0–R6 milestones are archived in [the legacy roadmap](ROADMAP-LEGACY-20261029.md), not erased or silently rebranded.

## Stop conditions

Stop and report if authorization is bypassed, simulated evidence becomes observed/verified, state and ledger disagree without an explicit boundary, a baseline is unavailable, held-out results are tuned retrospectively, or independent review is missing. Prefer one integrated result over additional RFCs.
