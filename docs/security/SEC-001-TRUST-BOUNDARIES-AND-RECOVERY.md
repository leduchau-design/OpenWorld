# SEC-001 — Trust Boundaries, Ledger Anchors, and SQLite Recovery

**Status:** Research implementation candidate; **not** production security approval.  
**Related:** RFC-006, Gate #11, W1 HyperMemory and W3 World Runtime.

## Motivation

The OpenWorld prototype preserves exact-event payload hashes alongside compact learned state. A payload hash stored in the **same mutable database** cannot prove the history has not been deliberately rewritten together with its hash. Likewise, accepting a plain `requester_owner_id` string does not authenticate the real requester. A valid probability model does not fix either issue.

SEC-001 adds two **optional, explicitly scoped primitives** in `src/openworld_superkernel/trust_boundaries.py`:

1. **Exact-event ledger anchor:** independently exported HMAC-signed snapshot for one `(owner_id, agent_id)` stream. Verification performs an **O(n) full scan** of exact-event rows and compares the current snapshot with the authenticated anchor. It catches deletion, insertion, reordered/reassigned metadata, payload editing and payload+digest rewriting after the anchor was created. Anchoring is **not** automatic; a separate trusted operator must actually export and retain the signed snapshot. A new legitimate append changes the snapshot, so use a newly approved anchor or a separate prefix-extension verification design. This API deliberately does not claim prefix verification.
2. **Scoped HMAC capability:** an exact-match grant bound to issuer, audience, externally authenticated principal identifier, owner, resource, action and validity window (maximum 3600 seconds). Signature validation uses constant-time HMAC comparison, strict key length and duplicate-JSON-key rejection. An optional `ScopedMemoryReader` wraps existing HM-P1e read methods with deny-by-default capability verification.

`online_backup()` uses SQLite's native backup API, verifies `PRAGMA integrity_check`, refuses overwrites and supports WAL-backed databases. A backup is not equivalent to a tested disaster-recovery plan or an offsite retention policy.

## Trust diagram

```
Trusted external identity provider --(authenticated principal)--> Capability Gateway
Trusted key custody --(HMAC key)--> Capability Authority / Anchor Verifier
Untrusted message ------------------------> Capability Gateway (reject by default)
Capability Gateway --(authorized read)--> HyperMemory API
HyperMemory exact_events --(full scan)--> External signed anchor comparison
HyperMemory database --(online backup)--> Protected copy / offline restore test
```

**Critical:** A system with direct access to the unwrapped `HyperMemoryP1e` instance can bypass the example `ScopedMemoryReader`. Production requires an authenticated server boundary that exposes **only** policy-enforced APIs, keeps keys out of untrusted runtime, handles durable revocation and carefully restricts database/file permissions. Passing this module's unit tests does **not** establish those properties.

## Evidence tiers

| Evidence | What is demonstrated | What is NOT demonstrated |
| --- | --- | --- |
| SHA-256 stored in SQLite | Detect accidental bit flips if digest itself is unchanged | Tamper resistance against a DB writer changing both bytes and digest |
| HMAC anchor retained outside SQLite | Detect subsequent divergence from signed exact-ledger snapshot (assuming safe key/anchor custody) | Truth of an original outside-world event; public non-repudiation |
| Scoped signed capability | A grant was issued by someone with the symmetric key, for a narrowly specified operation | Real-world identity of the requesting person without an external authentication system |
| SQLite online backup | Consistent database copy and successful integrity check under tested conditions | Crash/power-loss durability, offsite custody, restore time objectives, encryption, retention compliance |

## External anchoring procedure (research)

1. Stop/coordinate concurrent writes or obtain a consistent authoritative snapshot of the exact ledger.
2. Compute `capture_anchor()` with a key independently held outside the SQLite store and compromised application state.
3. Export the returned signed payload to a separately protected append-only medium. **Do not store the only anchor next to the database.**
4. For audit, call `verify_anchor()` against the snapshot using an independently obtained verification key.
5. If the ledger has grown legitimately, verify the older checkpoint via a retained backed-up snapshot or a future safe prefix-extension verifier. Do not falsely report a signature mismatch as necessarily malicious.
6. Never use this proof to assert that the signed bytes are a trustworthy statement about the external world; that requires source authentication.

## Required negative controls

- Corrupt a payload but leave its in-database hash unchanged: rejected.
- Modify both payload and in-database hash: rejected by independently saved anchor.
- Delete an old record, change stream ownership, or append after a checkpoint: rejected by exact-snapshot verification.
- Present the wrong external HMAC key or mismatched owner: rejected.
- Present a scope-forged, duplicate-key, expired, revoked, wrong-audience or wrong-principal capability: rejected.
- Restore an online SQLite backup with WAL records: compare to a previously issued anchor.

## Measured local research evidence

The isolated SEC-001 standard-library Python implementation passed **30/30 tests** on a local Python 3.13 environment. These tests use only synthetic identities, secrets and payloads. A clean GitHub Actions run on the proposed PR and the exact integrated SHA are separate required gates. The tests neither benchmark large scale nor validate external identity, external anchor publication, multi-process conflicts or physical sudden power loss.

## Unresolved production blockers

- Replace symmetric demo issuer with a real identity + key-management service, support durable revocation/rotation and audited grants.
- Authenticate event ingestion sources and separately establish what `VERIFIED` means; HMAC of database content alone is not event truth.
- Preserve time semantics, retention/erasure and external anchor lifecycle in a formally reviewed policy.
- Test multiple simultaneous writers, OS process crashes, file corruption, WAL readers, backup/restore RPO and RTO, and mutation/replay abuse.
- Harden API exposure so callers cannot bypass the capability gateway or supply an arbitrary authenticated principal.
- Bind W3 interaction messages to proper owner-scoped capabilities before any cross-owner or network deployment.

**Decision:** Integrate only as a separately reviewable research primitive. Keep Gate #11 open and default production authorization disabled.
