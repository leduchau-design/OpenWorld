# HM namespace migration — 20,000-event synthetic rehearsal

**Status:** Research-only, disposable synthetic fixture. Not a live migration
approval or proof of independent production-scale safety. Read
[the ADR-009 runbook](../security/HM-EVENT-NAMESPACE-MIGRATION.md).

## Experiment

- Generate 20,000 SIMULATED exact events (12 owners, 4 agents each), with
  payloads of 64, 256, 1,024 and 2,048 bytes. No private data or tokens.
- Create a legacy global-UNIQUE(event_id) SQLite database under a private
  temporary directory. Never accept a user-supplied source DB path.
- Create a disposable copy using the SQLite online backup API. Explicitly
  invoke HyperMemoryP1e(migrate_legacy=True, legacy_backup_path=...) on
  that copy only; never alter the original source fixture.
- Independently stream SHA256 of every exact row and agent_state JSON row,
  comparing original, clone, migrated clone, backup and source after trial.
- Verify integrity_check, owner collision semantics, scoped read, rollback
  of probe changes, and reopening the migrated clone without opt-in.
- Measure wall/CPU migration time, peak process RSS (platform-specific),
  Python/SQLite/OS and SQLite DB/WAL/SHM sizes before and after checkpoint.

## Commands

```sh
python benchmarks/hm_migration_rehearsal.py --events 20000 --owners 12 --agents-per-owner 4 --payload-bytes 2048 --out hm-migration-20k-local.json
OPENWORLD_SLOW_TESTS=1 python -m unittest discover -s tests -p 'test_hm_migration_rehearsal.py' -v
```

The current full CI job sets OPENWORLD_SLOW_TESTS=1; the gated test prints
OPENWORLD_HM_MIGRATION_SYNTHETIC_20K_JSON and a SHA256 of that JSON. A PASS
means only that the tested disposable rows, backup and state matched.
These checks are not a third-party signature or a production migration.

## Remaining independent gates

1. Obtain exact-head CI success, full unredacted *synthetic* output, and
   a second reviewer for correctness and failure-path examination.
2. Independently rehearse on an authorized, sanitized copy of the real
   schema and *representative* data volume; no customer data in public CI.
3. Measure migration lock and disk headroom with concurrent readers/writers
   and full WAL. Test interrupted migration, ENOSPC, crash/power-loss
   restore, immutable backup custody and external signed anchors.
4. Keep Issue #11 OPEN until the second contributor has confirmed the
   outstanding W0/W1/W5 independent acceptance checks.

**Rollback is not simply reverting source code:** once owners share an
event ID, old global uniqueness cannot be restored without reconciliation.
Keep original backups. No production deployment or model promotion is
authorized by this document.
