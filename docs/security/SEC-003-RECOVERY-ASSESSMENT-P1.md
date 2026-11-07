# SEC-003 P1 — Read-only witness recovery assessment

**Status:** RESEARCH-ONLY, no automatic recovery and no production authorization.
**Related:** Issue #41, Issue #34, Gate #11, `anti_rollback.py`.

## Problem

The existing `WitnessedAuthority` fences mutation using a separately provided `MonotonicWitness`. An exception, sudden process exit or failed witness-finalization can leave a `pending` operation. The fail-closed behavior is correct, but an operator still needs to distinguish observable states before reviewing recovery evidence.

**A local database snapshot alone cannot determine whether a pending operation was never applied or was committed and subsequently rolled back to the old contents.** This ambiguity is fundamental: both cases yield the identical old fingerprint. Clearing `pending` just because the digest matches would be unsafe.

## This implementation

`witness_recovery.assess_authority(authority, witness)` reports one of five immutable, read-only classifications:

- `CONSISTENT`: no witness fence and observed fingerprint matches; **not** identity verification, not approval to execute operations.
- `WITNESS_UNAVAILABLE`: independent head cannot be obtained; refuse further authorization.
- `DIVERGENT`: a clean witness head disagrees with database, or its fingerprint cannot be computed.
- `PENDING_UNCHANGED`: an unfinished fence exists and current DB digest still matches the old digest; **may also represent a rollback after a successful commit**.
- `PENDING_CHANGED`: unfinished fence exists and the database differs from its old digest; may represent a committed operation or tampering.

All non-consistent outcomes request an independent operator review and retain fail-closed state. The diagnostics never call `finalize`, provision genesis, mutate SQLite, rewrite the witness or change access policies.

### Independent evidence required for future manual recovery

1. A protected external sequence of witness epochs and operation identifiers, with issuer identity and policy version.
2. An authenticated authoritative event/journal receipt identifying the exact mutation and transaction commit outcome.
3. A stable database snapshot and protected backup, plus proofs of ownership and key generation.
4. Independent operator review and a documented recovery receipt (`recover_to_epoch`, `old_head`, `new_head`, `reason`, `reviewer`, `proof_refs`), authenticated and logged outside the rolled-back database.
5. A reviewed `compare-and-set` recovery protocol that cannot silently rewrite previously finalized witness history, including handling of a lost witness and of conflicting concurrent operators.

**Do not implement automatic witness clearing based solely on this classification.** The existing `InMemoryWitness` remains a test double; no independently administered monotonic service or key custody exists here.

## Tests

Eight synthetic tests exercise clean and missing witness, pending before/after a database effect, committed effect followed by restore of an earlier backup (pending with *matching* digest), direct bypass mutation and database corruption. They run without network, third-party packages or personal data. They are diagnostic tests, not certified recovery proof.

## Integration plan

- Keep the default W1/W3 behavior unchanged. The diagnostic module is opt-in and read-only.
- Preserve existing `test_sec002_storage_rollback.py` expected failures; they are still open for the legacy SEC-002 direct path.
- First implement real independent witness custody and authenticated transport, then design fault-tolerant administrative recovery and audit receipts.
- Track available/durable witness, pending age, successful/failed recovery attempts and fail-closed downtime as operational metrics before any external deployment.