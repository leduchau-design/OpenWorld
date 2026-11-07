# HyperMemory exact-event owner namespace — migration runbook

**Status:** Experimental security migration, not an automated deployment.
**ADR:** [ADR-009](../DECISIONS.md).
**Source:** the owner-supplied `0001-fix-memory-namespace-exact-event-ids-per-owner-to-cl.patch` is adapted with additional fail-closed migration controls; it is **not applied verbatim**.

## Why this change

Legacy SQLite `exact_events` has global `UNIQUE(event_id)`. This permits a requester to infer whether a foreign ID exists because the old lookup raised `PermissionError` rather than `None`, and it allows another owner's matching ID to block a write with `IntegrityError`. The new table uses `UNIQUE(owner_id,event_id)`, and reads filter `owner_id` in the SQL query. Missing and foreign IDs both yield `None`.

**This is not authentication.** The `requester_owner_id` argument is supplied by a trusted caller. Never expose raw `HyperMemoryP1e` directly to untrusted agents; use the existing independently authenticated capability facade. All owner-state and mutation checks remain in place.

## Operator-required prerequisites

1. Review permissions and stop all writers to the legacy SQLite database; arrange an exclusive maintenance window. Do not use an actively shared production database.
2. Copy the original file and its WAL/SHM state using SQLite's online backup API, not filesystem copy of a live WAL-mode database. Verify the original snapshot with `PRAGMA integrity_check` and externally held anchor/receipt evidence as applicable.
3. Review the exact schema. Migration intentionally refuses custom indexes/triggers, dependent views, foreign keys, staging tables, inconsistent unique indexes, corrupted exact payload hashes, or unknown table columns. Such databases require a separate migration design.
4. Choose a **new, unused, separately protected backup path**. The code refuses to overwrite the path and uses file mode 0600 for the created backup (subject to the host's filesystem controls).
5. Test on a **disposable copy** before even considering migration of an authorized persistent store.

## Explicit migration invocation (disposable fixture ONLY)

```python
from openworld_superkernel.hyper_memory_p1e import HyperMemoryP1e

source = "/path/to/disposable-copy.sqlite3"
backup = "/path/to/new-preserved-backup.sqlite3"
with HyperMemoryP1e(
    source, migrate_legacy=True, legacy_backup_path=backup
) as store:
    print(store.db.execute("PRAGMA integrity_check").fetchone())
```

Ordinary `HyperMemoryP1e(source)` **refuses to open** a legacy schema with `LegacyNamespaceMigrationRequired`; it never silently migrates. The explicit migration preflights unique indexes and dependent objects, checks full-row SHA-256/row count, saves and checks an SQLite online backup, rebuilds within a single `BEGIN IMMEDIATE` transaction, rechecks the full-row hash/indexes/integrity before commit and retains the backup after success or failure. This checks byte preservation within SQLite but **does not** establish tamper-proof authenticity: externally verified anchors remain separate.

## Required verification after migration

- Verify the migrated database integrity and exact payload equality with the preserved backup and owner/agent ledger snapshots or external signed anchors.
- Verify duplicate event IDs can be independently inserted by different owners, while a duplicate within one owner remains rejected.
- Confirm a foreign ID and a missing ID both return `None`; test authenticated facade authorization separately.
- Confirm idempotent reopening without migration flags and no unexpected new schema objects.
- Check migration time, database size, WAL/SHM, disk free space, SQLite version, I/O errors, rollback from a test failure and backup accessibility; repeat for a realistic copy at real data volume.
- Keep complete SHA/OS/Python/SQLite/test artifacts. Require owner review of the exact PR head and independent reproduction before enabling any persistent migration.

## Restore / rollback is NOT a code-only revert

Restoring the original code after owner-scoped duplicate IDs have been written would **not** re-establish global event-ID uniqueness. Reverting the migration requires a deliberate decision: stop writers, preserve the migrated DB, restore the **pre-migration backup** and accept loss/reconciliation of post-migration writes, or author an independently reviewed reverse migration that proves collisions are absent. Never overwrite the preserved backup.

## Boundaries

No cross-owner consent, identity proof, encryption, privacy guarantees, or shared world/SQLite atomicity is created by this patch. Production data migration and irreversible deployment are explicitly out of scope.
