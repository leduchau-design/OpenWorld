# HyperMemory — authorized sanitized-copy review

**Status:** local-only safety tool for investigating legacy SQLite migration.
**No real/sanitized database has been provided or processed by this project
session.** The tool and its CI tests use exclusively synthetic fixtures.
See [ADR-009 migration runbook](HM-EVENT-NAMESPACE-MIGRATION.md).

## Privacy and authorization boundaries

1. A data owner and authorized operator must approve the source and
   the purposes of evaluation. Do not use production databases directly.
2. Produce a **detached sanitized copy** locally using the SQLite backup
   API during an authorized maintenance procedure. Remove/transform every
   personal, confidential, account, financial, consent and key-bearing
   value per an approved redaction policy. Redaction can invalidate ledger
   digests or external anchors; preserve those separately under authorized
   custody, **never fake their validity on the sanitized copy**.
3. Recompute internal payload hashes as appropriate for the sanitized
   fixture under an approved data-transformation protocol. A passing
   sanitized test does not prove the untouched real ledger will migrate.
4. Checkpoint/close the detached copy so that **no -wal/-shm sidecars**
   exist. The tool refuses such inputs; immutable SQLite reads deliberately
   do not include uncheckpointed WAL.
5. Run on a trusted local machine with enough private disk space. Do not
   upload any copy or raw logs to GitHub/public CI, Drive or ChatGPT.
6. Only aggregate counts/timings are emitted, not database paths, IDs,
   payloads or raw row hashes. Counts may themselves be sensitive:
   share the output only after privacy review.

## Commands (first inspection, then disposable rehearsal)

```sh
python scripts/hm_sanitized_copy_rehearsal.py --source /path/to/approved-sanitized-copy.sqlite3 --ack AUTHORIZED_AND_SANITIZED_COPY --mode inspect
python scripts/hm_sanitized_copy_rehearsal.py --source /path/to/approved-sanitized-copy.sqlite3 --ack AUTHORIZED_AND_SANITIZED_COPY --mode rehearse --out /path/to/new-private-report.json
```

The tool **never writes to the supplied source**. Inspection uses SQLite
read-only immutable mode after refusing symlinks and existing WAL/SHM
sidecars. It validates integrity, supported legacy schema, unique indexes,
absence of custom dependencies, every exact payload hash and compact
state rows. It computes internal stream digests, but never exposes them.

Rehearsal checks a conservative **advisory** free-space floor (the larger
of 128 MiB and six times the input size), then makes an isolated online
SQLite clone inside a private temporary directory, runs the existing
explicit migration only on that clone, verifies every exact/state row
against the input and the preserved temporary backup, and reopens the
migrated clone. It records elapsed time, page/freelist counters and
temporary disk use. All temporary databases are removed after the run;
the optional JSON report refuses overwrite.

**A six-times heuristic is not a disk allocation guarantee**. Real WAL
growth, backup staging, block allocation, I/O contention and recovery
may demand more. Neither inspect nor rehearse tests hardware power loss,
active writers, cross-store atomicity, external source authenticity or
legal/regulatory consent. The acknowledgment flag is a human assertion
that the script cannot authenticate.

## Required independent review before real migration

- Independent reviewer confirms owner approval, actual sanitization,
  retention requirements and test hardware; no data exfiltration.
- Confirm schema matches the restricted legacy model. If not, STOP;
  do not disable fail-closed checks to force migration.
- Inspect evidence of equality and recovery, backup custody,
  missing/pending WAL and free-space behavior.
- Run controlled failure, concurrent read/write, ENOSPC and backup restore
  tests separately on authorized, nonproduction infrastructure.
- Sign off Gate #11 and migration-specific gate separately. A successful
  rehearsal does **not** authorize any live deployment.

The existing 20,000-event synthetic test remains the **only measured
volume-based dataset in this workflow** until an authorized sanitized copy
has been provided and an independent reviewer has acted.
