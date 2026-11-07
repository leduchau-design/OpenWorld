# OpenWorld — Canonical Project Continuity

**Status:** Consolidated working context; not a proof of implementation or scientific performance.  
**Updated:** 2026-10-28  
**Repository:** https://github.com/CocAgent/OpenWorld  
**Language:** English for all repository materials.

This document consolidates the project decisions **visible in the current OpenWorld working conversation**, the repository state checked via the connected GitHub account, and the existence of two externally shared ChatGPT conversations that could not be read. It is not a transcript and does not attribute content to inaccessible sessions. See [Session Source Register](SESSION-SOURCE-REGISTER.md).

## 1. Mission and product boundary

**OpenWorld** is an independent, open-source ecosystem for adaptive, collaborative, evolving agents. It is separate from AHappy and must not reference AHappy infrastructure, user data, deployments, accounts, or repositories as dependencies. A possible future public-facing product is *OpenWorld Companion*, but product readiness is not established.

> Many agent identities can share a small pool of inference models without storing a distinct set of foundation-model weights for every identity.

The primary purpose is to deliver useful, affordable, accountable AI capabilities to people across languages and hardware environments. Large-scale agent populations are research goals, not demonstrated production capacities. Do not equate a billion stored identities with a billion active reasoning processes.

## 2. Names and repository strategy

| Term | Meaning |
|---|---|
| OpenWorld | The overall project, ecosystem and canonical GitHub repository |
| SuperKernel | Agent lifecycle, identity, scheduling, capabilities, resource budgets and reasoning routing |
| HyperMemory | Evidence-preserving exact records, compact predictive state, stochastic/generative replay and controlled sharing |
| MathKernel | Formal stochastic processes, statistics, information theory and decision optimization |
| World Runtime | Sparse-event simulation, interactions, reproducible transitions |
| Open Protocols | Bounded, permissioned communication and tool interoperability |
| OpenWorld Genesis | Possible research theme for agent creation and evolution; not the official repository name |
| OpenWorld Civilization | Possible future society simulation; not the official repository name |

**Canonical repository:** `CocAgent/OpenWorld` (not `openworld-superkernel`, `openworld-genesis`, or `openworld-civilization`). Use a single monorepo and English public documentation, source comments, issues and PRs. Publish new work under Apache-2.0 unless separately licensed. Review all inherited third-party assets and earlier research archives before any public upload.

## 3. Conceptual architecture and mathematical contract

An agent is a persistent identity with genome/configuration, evolving state, memories, relationships, permissions and a policy reference. A dedicated neural model is **not** required per agent.

The model family for agent `i` may be written as:

```text
Agent_i(t) = (Identity_i, Genome_i, Epigenome_i(t), PredictiveState_i(t),
              ExactLedger_i, Relationships_i(t), PolicyRef_i(t))
```

A proposed coupled controlled stochastic system:

```text
X[t+1] ~ K_theta( . | X[t], action[t], environment[t] )
Z[t+1] = F_phi( Z[t], observation[t+1], action[t] )
action[t] ~ pi_psi( . | Z[t], goals[t], constraints[t] )
```

Here `K` is a controlled stochastic transition kernel and `Z` a compressed predictive state; an exact evidence ledger is distinct from `Z`. The seed and transition-model version may permit replay of **generated simulation outcomes** only when initial conditions, PRNG, versions and all exogenous inputs are preserved.

A characteristic function describes a random variable's distribution. **A single marginal characteristic function does not determine a stochastic process**; finite-dimensional joint laws or explicit transition/dependence structure are required. Thus numerical DNA/seed is a useful *generative representation*, not a lossless encoding of arbitrary real-world history.

Predictive sufficiency depends on a specified observation model, task family, policy/horizon and loss; there is no universal constant-size memory for all possible questions.

## 4. Evolution of HyperMemory research (historical context)

These phase descriptions and numbers were *reported in earlier conversation messages*, not independently reproduced from the current public repository. They are recorded for continuity, not as verified performance claims.

| Phase | Conceptual deliverable | Status and caveat |
|---|---|---|
| Genome & Memory v1.0 | Small identity/genome representation, state snapshots, independent memory | Prior local prototype; source import pending rights/security review |
| Psi-Memory v0.1 | Generative stochastic replay, seed, process parameters, checkpoints and protected events | Toy Gaussian AR(1) experiments; compression ratios not generalizable |
| HyperMemory v2.0 / HM-P0 | Predictive/semantic/exact memory separation, memory compiler, provenance and local experiments | Previous synthetic result reported ~92.61% compacted-size reduction; not a product claim |
| HM-P1 | Epigenome adaptation and regime drift | Previous compacted-size result reported ~74.72%; online WAL footprint differed substantially |
| HM-P1c | SQLite batched writes, checkpoint handling, exact-event behavior | Previous experiments reported speed gains varying by workload; benchmark revalidation required |
| HM-P1d | Online mixture of long/fast/slow predictors | Improved synthetic drift scenarios but added CPU/storage overhead and did not win all baselines |
| HM-P1e | Heuristically cost-gated predictor, exact event lane, SQLite local transaction | Current public repository implementation; independent merged-main execution pending |

Important distinctions: a synthetic benchmark does not measure language-memory recall, trustworthiness of users' data, LLM quality, production concurrency, model serving cost or capacity at global scale. All benchmark claims require version-pinned repeatable evidence.

## 5. Memory architecture: required invariants

- Exact ledger: protected events, externally consequential actions and observations requiring audit must preserve ordered records according to a valid retention policy. Do not silently substitute generated events.
- Predictive memory: keep bounded statistical state where the defined task permits it, while reporting quality loss and failure modes.
- Generative memory: replay only simulated paths for which model version, PRNG, checkpoints and exogenous inputs are sufficient.
- Provenance: `OBSERVED_RECORDED`, `VERIFIED`, `INFERRED`, `SIMULATED`, `UNAVAILABLE` have different meanings. A recorded claim is not automatically verified truth.
- Controlled collective memory: sharing requires scope/consent/provenance and revocable capabilities; no cross-owner default access.
- Privacy: export, deletion, retention, isolation and incident handling are design requirements before onboarding people.
- Measurements: disk including WAL/SHM, compacted disk, index/replica overhead, CPU, peak RAM, latency, prediction loss, exact recall and decision/regret metrics should be reported separately.

A memory compiler decides among *exact*, *predictive*, *generative*, and *deny* routes; source content cannot grant itself new execution or memory-access permissions. Public RFC-006 is **proposed**, not accepted as fully implemented.

## 6. Workstreams and sequence

| Stream | Responsibility | GitHub tracker |
|---|---|---|
| W0 Architecture | Ratify versioned agent/evidence interfaces, schema, ADR and policy | https://github.com/CocAgent/OpenWorld/issues/1 |
| W1 HyperMemory | HM-P1e and future trustworthy, cost-aware learning/runtime | https://github.com/CocAgent/OpenWorld/issues/2 |
| W2 MathKernel | Controlled stochastic kernels, predictive sufficiency, information-theoretic bounds | https://github.com/CocAgent/OpenWorld/issues/3 |
| W3 World Runtime | Replayable sparse social simulation, identity and world event processing | https://github.com/CocAgent/OpenWorld/issues/4 |
| W4 Protocols | Capability-based zero-trust MCP/A2A adapters | https://github.com/CocAgent/OpenWorld/issues/5 |
| W5 Evaluation | Independent experiments, negative controls, privacy/integrity tests | https://github.com/CocAgent/OpenWorld/issues/6 |

**Sequence:** Establish W0/W1/W5 on a validated merged baseline first, then proceed with scoped W2/W3/W4 and cross-track integration. Work on topic branches and independent PRs. Protect `main`; do not merge for passing unit tests alone.

## 7. Verified repository snapshot (2026-10-28)

The following states were checked through the GitHub connection during this consolidation:

- PR #7 (bootstrap), #8 (W0 contracts), #9 (W1 experimental HyperMemory), and #10 (W5 independent benchmark) were reported as **merged**.
- Main commit at time of check: `2b97fead0847054fa2b777973f4a6d59af10990f`.
- Current code includes `src/openworld_superkernel/hyper_memory_p1e.py`, `tests/test_hyper_memory_p1e.py`, `benchmarks/w5_memory.py`, and `docs/rfcs/RFC-006-MEMORY-AND-AGENT-CONTRACTS.md`.
- Gate issue #11 requests **independent execution** on merged `main`: https://github.com/CocAgent/OpenWorld/issues/11 .
- The prior chat counted 39 written tests across bootstrap and later work; **this number is an authored-test count, not a passing-test certification**.

This snapshot is time-bound. Re-check current Git refs and CI before relying on it.

## 8. Explicitly deferred

No claim of one-billion-active-agent capacity, production readiness, universal memory compression, verified general intelligence, proven model-independent personal safety, or globally available service. Do not copy earlier research ZIP archives into the public repository without origin, license, confidentiality and repeatability review.

## 9. Continuation rule for future work sessions

1. Read this page and the [Source Register](SESSION-SOURCE-REGISTER.md) first.
2. Reconcile the actual GitHub `main` SHA, open PRs, failing checks and Issue #11.
3. Treat *discussion*, *proposed design*, *committed source*, *independently tested*, and *production deployed* as separate statuses.
4. For new research, state a falsifiable claim, baselines, assumptions, datasets, costs and exit criteria.
5. Never invent the contents of unavailable chat share links. Record a pending source and request an export only if needed to complete the historical record.
6. Remain independent of AHappy and use English in committed artifacts.
