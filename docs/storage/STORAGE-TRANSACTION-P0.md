# Issue #42 — Single-Authority Transaction Reference (SQLite P0)

**Status:** Research prototype, not a production cross-owner gateway.  
**Date:** 2026-10-29.  
**Related:** ADR-008, SEC-002 #34, bilateral consent #35, #41 (rollback witness), Gate #11.

## Research objective

Demonstrate an **all-or-nothing local transaction** spanning a synthetic sender approval, receiver consent, resource balance update, durable receipt, and outbox record. This is deliberately performed in **one SQLite database file, one `BEGIN IMMEDIATE` transaction** to prove the database consistency boundary without a cross-database two-phase commit claim.

Python 3.11 stdlib only, WAL and `synchronous=FULL`; no authentication provider, real credentials, real coins, network calls or production world changes.

## Invariants

1. `TransferIntent` is immutable, canonicalized, hashed and bound to source/target agent and owner, amount, purpose, nonce, world tick and expiration.
2. Both parties must approve **the same hash** in independent `source`/`receiver` roles; one owner cannot approve on the other's behalf *within the simulated assertions*.
3. Approval can be revoked before execution; duplicate approval or reused nonce is rejected.
4. A transfer can execute only if both approvals are active, ownership matches at commit, the balance is sufficient, and `expected_tick` is current.
5. Resource debit, credit, intent status, durable receipt, tick advancement and outbox event are committed together; injected failure before completion rolls back all effects.
6. Identical replay returns the previous receipt, not a second debit. Conflicting request content is rejected.
7. Outbox is **data**, not an external side effect. An external dispatcher must separately enforce idempotency and delivery semantics.

## Important security and operational limitations

- `authenticated_owner` is a string provided by a **trusted test harness**. It is *not* verified by SEC-002, OIDC or mTLS. This code is **NOT safe to expose as a network service**.
- It does not consume real SEC-002 capabilities or independently anchor authorization state. Integration of those stores as separate SQLite files would reintroduce non-atomicity.
- It does not execute the existing W3 world reducer or change `world_guard.py`; real cross-owner actions remain denied. The world tick here is a minimal test state.
- The `seed_account` function is a fixture-only administrative primitive; a malicious caller with raw database access can bypass all invariants.
- One SQLite writer per DB file still limits concurrent writes. No multi-process/large-world benchmark or crash-after-fsync certification is claimed.
- The recipient's consent is a simulated assertion, not proof of an actual authenticated person. There is no actual billing, payment, or data privacy policy.
- The reference assumes world resource amounts fit SQLite integer constraints; research code checks SQLite signed 64-bit amount/balance bounds, but a full domain-level quantity policy is still missing.
- A database restored from an old backup can still revert balances and consent unless an independently trusted epoch/anchor (Issue #41) is used.

## Conditional PostgreSQL pilot (not executed)

The next workstream should implement **the identical semantics** behind a versioned `AuthorizationTransaction` storage port using PostgreSQL with row-level locks / constraints and one authoritative commit for all affected tables. No PostgreSQL instance was installed, run or benchmarked in this PR.

Required comparative evaluation: matched synthetic traces, concurrent operations and failure injections, p50/p95/p99 commit latency, throughput, WAL/disk, RSS/CPU, backup recovery RPO/RTO, and permission denied rates. A separate remote witness remains mandatory for anti-rollback regardless of SQL backend.

The decision to move shared control-plane authority from SQLite to PostgreSQL must follow those measurements; local HyperMemory may remain SQLite.

## Verification


tests: `python -m unittest discover -s tests -v`  
Focused local prototype: **19/19 passing** (Python 3.13.5, synthetic only). GitHub Actions on integrated repository is required before review.

**Gate:** No real cross-owner execution until authenticated receiver consent, SEC-002 capability debit, world resource effect, receipt and audit share a reviewed atomic boundary or recoverable protocol with independent witness and owner approval.
