# SEC-003 — Anti-Rollback Witness (Research P0)

**Status:** Implemented research reference, not a production security boundary.  
**Issues:** #41 (primary), #34, #11, #42.  
**Date:** 2026-10-29.

## Why this exists

SEC-002 persists grant revocation, but its state can be rolled back by restoring an older, internally consistent SQLite backup. A valid HMAC token and ordinary `PRAGMA integrity_check` cannot distinguish that restore from the legitimate historical state. `test_sec002_storage_rollback.py` on main preserves this as a known-negative `expectedFailure`.

The reference adds a **separately trusted witness contract**, not a stronger digest stored inside the same database. Every authority mutation must pass through a fencing step before touching SEC-002. At authorization time, a witness comparison rejects an old database or a pending transaction.

### Witness state

`WitnessHead(epoch, digest, pending_operation)`:

- `epoch`: monotonic logical number owned by the external witness (not the host SQLite DB).
- `digest`: SHA-256 of canonicalized SEC-002 authority configuration, signing key states, grant rows, and audit log.
- `pending_operation`: independent fence recorded **before** touching the DB. If any stage crashes, the witness stays pending and all operations fail closed.

A correct production witness must provide authenticated, nonrollbackable, strongly consistent compare-and-set with a durable audit trail and independent fault domain. **`InMemoryWitness` does not meet any of these operational requirements.** It is a deterministic stand-in to test the protocol logic. It must not be deployed or serialized beside the authority DB.

### Sequence

1. An authorized operator provisions a **fresh empty** SEC-002 authority. A missing witness on a nonempty DB is a hard failure, never a bootstrap opportunity.
2. Before any operation, compare current authority fingerprint with witness digest; reject mismatch/pending.
3. Call witness `begin(expected_head, operation_id)` to advance the independent epoch into `pending` state atomically under the witness's serialization rule.
4. Invoke the existing SEC-002 database transaction (`issue`, `revoke`, `authorize`, `rotate`, `revoke_key`).
5. Only when that operation returns successfully, finalize the witness with the new fingerprint and clear `pending`.
6. If any step fails, including an invalid authorization request after `begin`, **leave `pending` intact**. No automatic rollback of witness to a historical epoch; manual recovery needs separate evidence.

### Assumptions and limitations

- **Single trusted authority service** owns DB and witness client; nobody else modifies grants, audit or signing keys. A directly imported SEC-002 object or raw DB connection **bypasses** this wrapper, and the next verification only detects the change. Process/service separation is mandatory before exposing to hostile tenants.
- Fingerprint queries are not an atomic multi-table snapshot in the face of *unwrapped concurrent writers*. The trusted host must serialize mutation and snapshot reads.
- Witness and DB are separate failure domains; they are **not atomically committed**. A crash can leave the witness pending, intentionally causing unavailability instead of replaying an old authorization. An independently specified recovery protocol must assess the log and reconcile to a trusted state before any reopening.
- An in-memory witness loses state at process exit. This reference demonstrates simulated rollback detection only when the witness object survives independently. It cannot prove actual durability, KMS security, physical-failure resilience, or remote identity.
- It does not make a validly signed event an authenticated fact about the outside world.
- A standalone SEC-002 `authorize()` already commits capability use before an optional memory/world operation. An anti-rollback witness **does not** make this downstream effect atomic. Issue #42 must establish a separate transaction model.
- Full authority snapshot hashing is O(number of grants + audit records), intentionally not optimized. Do not extrapolate high-throughput capacity from P0.
- Denial and crash may strand `pending`, even for harmless bad input. Availability and recovery must be designed and measured; fail-closed is a safety policy, not evidence of high availability.

## Tests and gates

`python -m unittest discover -s tests -v` includes twelve local security tests (synthetic identities) covering:

- Valid issuance, revocation and ordinary restart.
- Rejection of authority DB restored from a backup before revocation, and before a grant was consumed.
- Missing external witness and refusal to silently reprovision a nonempty authority.
- Pending fence before DB mutation and after DB mutation but before witness finalize.
- Stale compare-and-set request, direct raw-DB bypass detection and fingerprint mutation.

Initial local focused run: **12/12 tests passed** using Python 3.13.5, with a synthetic SEC-002 storage fixture. GitHub Actions on integrated source is required for independent acceptance.

**Not closed:** verified external witness custody, survival across independent process power failure, authenticated transport, key lifecycle, robust in-doubt recovery, stress concurrency, and SEC-002 + world-effect atomicity. Leave Issues #41/#11 open and do not enable cross-owner execution.
