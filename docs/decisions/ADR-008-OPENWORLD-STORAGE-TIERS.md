# ADR-008 — Storage tiers for OpenWorld (SQLite local, PostgreSQL authority)

**Status:** Proposed (review required)  
**Date:** 2026-10-29  
**Related:** SEC-002 #34, bilateral consent #35, security gate #11, W1/W3/W4/W5.

## Context

OpenWorld started with Python 3.11+ standard-library, CPU-only experimentation. Local `sqlite3` provides file-backed transactions and reproducible research without installing a service or paying for cloud infrastructure. HyperMemory's predictive state and protected exact-event lane can commit atomically in **one SQLite connection / database**. SEC-002's grant registry can atomically debit use counts with `BEGIN IMMEDIATE` inside **its own database**.

Those are limited local guarantees, not proof of authenticated provenance, distributed transactions, nonrollbackable revocation, service identity or million-agent scale.

SQLite WAL allows concurrent readers and one writer at a time **per database file**. SQLite WAL requires users of that database to be on the same host; using one shared WAL file on network storage across hosts is not a supported architecture.

## Decision

**Keep SQLite as the default reference and local agent-state engine.** Do not force the entire OpenWorld infrastructure into SQLite.

**Use PostgreSQL as the preferred candidate for the shared authoritative control plane** when OpenWorld needs authenticated multi-tenant access, multi-service transactional consent or many concurrent writers. This is an architectural direction, **not an implemented database migration** and not an assertion that PostgreSQL alone makes the system secure.

| Data domain | Initial backend | Potential multi-host backend | Consistency / trust boundary |
|---|---|---|---|
| Agent predictive memory / epigenome | SQLite per local runtime/shard | Host-local SQLite or PostgreSQL after benchmarks | Agent-owner isolation, state version and replay |
| Protected exact-event history | Local SQLite with independent external anchor | PostgreSQL + separately protected immutable evidence/object storage | Explicit retention/erasure and independently witnessed provenance |
| Principal, agent ownership, grants, revocations | SQLite SEC-002 prototype | **PostgreSQL** as authoritative control-plane candidate | Trusted session issuer, grant/state atomic transaction where possible |
| Receiver consent and world operation ledger | Prohibited until implementation | **One PostgreSQL transaction boundary**, or reviewed coordination protocol | Both independent permissions, resource effects and replay receipt |
| Cache, routing, ephemeral sessions | In-memory initially | Redis or equivalent *cache only* | Cannot overrule authoritative consent or revocation |
| Offline evaluation/analytics | Standard Python, SQLite | DuckDB / analytical store | Not an authorization source |

### Why not switch immediately?

1. Adding PostgreSQL now increases setup, maintenance, driver and CI burden without measured benefit for small deterministic prototypes.
2. A database replacement cannot fix forged caller identity, missing consent, keys inside an untrusted process, or database restoration to an older (internally consistent) point.
3. The current system is **not** built around a backend-independent storage contract. Migrating in place would increase security risk without a verified dual-write/cutover plan.
4. No benchmark yet proves unacceptable SQLite lock contention, WAL overhead or multi-process latency for the declared local workload.

### No false atomicity

Two separate SQLite files do **not** become one durable security transaction merely because each has local `BEGIN IMMEDIATE` and WAL. A separately committed grant consumption can survive a failure while the world operation does not, or the opposite. Do not enable cross-owner `signal`/`transfer` until grant consumption, receiver consent, ownership, world-state update and durable receipt have a reviewed common commit boundary or explicit, tested recovery/reconciliation semantics.

Even with PostgreSQL, an external action (HTTP call, tool invocation or payment) cannot simply be rolled back with an SQL transaction. Use idempotency, transactional outbox and explicit compensation/inquiry procedures where appropriate; never claim a network external effect is SQL-atomic.

### Known negative: restore can resurrect a revoked grant

A validly signed, unexpired capability issued before a backup can become usable again if the authority's SQLite database is restored from the backup **taken before its revocation**, while the HMAC key remains available. Ordinary local DB integrity checks and signatures do not detect this security history rollback. [`test_sec002_storage_rollback.py`](../../tests/test_sec002_storage_rollback.py) contains an **expected-failure regression** for the missing protection.

Corrective design must bind every grant verification to an independently protected non-rollbackable epoch, ledger tip or authoritative monotonic state outside the restored database's failure domain; its custody, availability, backup and recovery need independent review. It is insufficient merely to add an epoch stored in the same database.

### Re-evaluation triggers (not invented numerical thresholds)

- Two or more hosts need to authorize against one shared owner/grant/consent domain.
- A single atomic transaction must coordinate independent owners, grants, world balances and auditable events.
- Measured SQLite write lock contention, p95/p99 latency or WAL growth exceeds a separately established workload SLO.
- Operations require managed backup, security roles, failover, recovery-point/recovery-time objectives or audit retention that local storage cannot establish.
- Multi-process tests show failure and recovery modes not safely controlled by the local runtime.

## Migration plan (conditional)

1. Define versioned interfaces for capability state, world journals, read-side scopes and immutable receipts. Keep the existing reference implementation intact.
2. Independently test on SQLite and PostgreSQL using **identical trace data and invariant assertions**, including concurrent grant consumption, revocation/restart and crash injection.
3. Design a single authoritative write path: read-only shadow migration first, explicit checkpoint and digest comparison; do not silently use dual-authoritative writes.
4. Specify backups, schema evolution, disaster recovery, external anti-rollback witness and key custody.
5. Obtain operator/security review, then choose cutover; preserve SQLite for offline agent memory where it remains beneficial.

## Alternatives

- **PostgreSQL everywhere:** simpler shared relational consistency but higher baseline operations cost, less natural embedded/offline use; benchmark first.
- **RocksDB / other LSM KV:** useful for large local key-value states but SQL joins, constraints and multi-entity consent semantics require extra design.
- **Redis:** helpful for caching but never the unique source of grant revocation, owner identity, exact evidence or bilateral consent.
- **DuckDB:** analytics and benchmark summaries, not our authoritative multi-writer transaction coordinator.
- **Event streaming/log systems:** may complement an audited event plane; do not by themselves provide transactional consent or authenticate event truth.

## Sources

- SQLite: [appropriate uses](https://sqlite.org/whentouse.html), [WAL](https://sqlite.org/wal.html), [network caveats](https://sqlite.org/useovernet.html).
- PostgreSQL: [MVCC and transaction isolation](https://www.postgresql.org/docs/current/mvcc-intro.html).

## Owner gates

- [ ] Approve ADR-008 scope, storage port boundary and data ownership.
- [ ] Document independent trust/anti-rollback authority and prove it is not restored from the same failure domain.
- [ ] Reproduce known-negative rollback and separated authorization/effect counterexamples.
- [ ] Define SLO/RPO/RTO and benchmark before migration.
- [ ] Continue to deny cross-owner world execution; #35 remains a protocol proposal.
- [ ] Do not mark #34 or #11 production complete.
