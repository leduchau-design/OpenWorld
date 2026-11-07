# OpenWorld roadmap — integration-first (2026-10-31)

**Status:** Owner-approved prioritization; future milestones are gated, not promises of production releases. This file replaces the earlier milestone labels for planning only; the [unmodified historical R0–R6 plan](ROADMAP-LEGACY-20261029.md) remains available. W0–W5 are technical workstreams, **not** release stages.

## R0 — One integrated agent vertical slice (current priority)

Compose **one local, CPU-only, single-owner** Observe → Memory → Policy → Authorization → World Action → Simulated Evidence → Replay cycle with a reproducible walkthrough, negative security tests and a fixed-rule baseline. No external effects or private user data. See [the R0 specification and G1–G5 gates](R0-INTEGRATED-AGENT-VERTICAL-SLICE.md). Closing independent [Gate #11](https://github.com/CocAgent/OpenWorld/issues/11) requires evidence and a second reviewer, not just passing CI.

## R1 — Bounded multi-agent coordination

Demonstrate several independent agents in a replayable same-owner world; constrain budgets, scheduling and action conflicts. Benchmark against simple scripted agents. No cross-owner permissions or distributed authority.

## R2 — Learning and adaptation with measured value

Compare memory-aware and role-shared policies with fixed hold/fixed cooperation, tabular and no-memory baselines under equal action budgets and disjoint seeds. Measure task utility minus compute, storage and resource exposure. Preserve P1–P6 negative results; do not adopt a model because its mathematics is sophisticated.

## R3 — Authenticated cross-owner exchange

Require independently reviewed real identity, durable grant revocation, bilateral consent, transaction receipts, crash tests and one authoritative mutation boundary before any cross-owner W3 effect. PostgreSQL is only a research candidate for shared control-plane transactions; local SQLite memory is not automatically migrated. Issues #34, #35 and #42 are blockers, not implicit approvals.

## R4 — Evidence-driven scale and interoperability

Only scale measured workloads after R0–R3 safety and utility. Introduce model/LLM adapters, MCP/A2A, sharding or federation when a concrete task and threat model require them. Report p50/p95/p99, CPU/RAM/WAL+disk, recovery cost, privacy and operating expense. No extrapolation from synthetic population counts to real active agents.

## Admission and scope control

- Default to **DEFER** for new RFCs, deep mathematical frameworks, federation, GPUs and agent evolution unless they unblock a failed gate; do not erase existing research.
- Record criticism as ACCEPT / EXPERIMENT / DEFER / REJECT with evidence and review triggers per [review policy](GOVERNANCE-REVIEW-POLICY.md).
- Distinguish **Proposed**, **Implemented**, **Independently verified** and **Production validated** for every capability.
- Keep project independent from AHappy, in English as canonical engineering language; [Vietnamese onboarding](vi/README.md) is explanatory only.
