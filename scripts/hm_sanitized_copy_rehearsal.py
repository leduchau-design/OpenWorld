"""Local-only, fail-closed inspection/rehearsal of an AUTHORIZED SANITIZED SQLite copy.

Never migrates the supplied file. Inspect uses immutable read-only mode; a
rehearsal uses a second SQLite online backup inside a temporary directory.
No payload, event ID, owner ID, path or row digest is printed or exported.
Authorization and genuine sanitization CANNOT be proven by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks"))

from hm_migration_rehearsal import fingerprint, disk_bytes
from openworld_superkernel.hyper_memory_p1e import HyperMemoryP1e

ACK = "AUTHORIZED_AND_SANITIZED_COPY"
SCHEMA = "openworld.hm.sanitized-copy-review.v1"
EXACT_COLUMNS = (
    "owner_id", "agent_id", "seq", "event_id", "provenance",
    "event_type", "payload", "payload_hash",
)
STATE_COLUMNS = ("owner_id", "agent_id", "state_json")


class InspectionBlocked(RuntimeError):
    """Input cannot safely be assessed with the narrow supported contract."""


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _readonly(source: Path) -> sqlite3.Connection:
    # Require a checkpointed, detached copy. Immutable SQLite does NOT read
    # external WAL and therefore must never be used on a live WAL database.
    url = "file:" + quote(str(source.resolve()), safe="/:") + "?mode=ro&immutable=1"
    con = sqlite3.connect(url, uri=True, timeout=10)
    con.execute("PRAGMA query_only=ON")
    return con


def _indexes(db: sqlite3.Connection) -> set[tuple[str, ...]]:
    found = set()
    for _seq, name, unique, _origin, partial in db.execute(
            "PRAGMA index_list('exact_events')"):
        if partial:
            raise InspectionBlocked("partial exact-event indexes require manual review")
        if unique:
            escaped = name.replace('"', '""')
            found.add(tuple(row[2] for row in db.execute(
                f'PRAGMA index_info("{escaped}")')))
    return found


def _preflight(db: sqlite3.Connection) -> tuple[dict, dict]:
    if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
        raise InspectionBlocked("SQLite integrity_check failed")
    exact_cols = tuple(row[1] for row in db.execute(
        "PRAGMA table_info('exact_events')"))
    state_cols = tuple(row[1] for row in db.execute(
        "PRAGMA table_info('agent_state')"))
    if exact_cols != EXACT_COLUMNS or state_cols != STATE_COLUMNS:
        raise InspectionBlocked("unknown exact/state table columns")
    indexes = _indexes(db)
    if indexes != {("event_id",), ("owner_id", "agent_id", "seq")}:
        raise InspectionBlocked("not the exact supported legacy unique schema")
    for name, sql in db.execute(
            "SELECT name,sql FROM sqlite_master WHERE "
            "type='index' AND tbl_name='exact_events'"):
        if sql is not None or not name.startswith("sqlite_autoindex_exact_events_"):
            raise InspectionBlocked("custom exact-event indexes not supported")
    if db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='trigger' "
            "AND tbl_name='exact_events'").fetchone():
        raise InspectionBlocked("exact-event triggers not supported")
    if db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='view' "
            "AND lower(sql) LIKE '%exact_events%'").fetchone():
        raise InspectionBlocked("dependent views not supported")
    for (name,) in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"):
        escaped = name.replace('"', '""')
        if any(row[2] == "exact_events" for row in db.execute(
                f'PRAGMA foreign_key_list("{escaped}")')):
            raise InspectionBlocked("dependent foreign keys not supported")
    if db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='exact_events_namespace_v2'"
            ).fetchone():
        raise InspectionBlocked("staging table exists; manual review required")
    # This iterates over all exact payloads and state JSON, never exports any
    # raw row or hash. The result is used for internal equality only.
    try:
        counts_and_digest = fingerprint(db)
    except (ValueError, TypeError, sqlite3.Error) as error:
        raise InspectionBlocked("invalid exact event/state values") from error
    for payload, expected in db.execute(
            "SELECT payload,payload_hash FROM exact_events"):
        if not isinstance(payload, bytes) or not isinstance(expected, str):
            raise InspectionBlocked("invalid exact event payload or digest")
        if hashlib.sha256(payload).hexdigest() != expected:
            raise InspectionBlocked("protected payload hash mismatch")
    meta = {
        "exact_event_count": counts_and_digest["exact_event_count"],
        "agent_state_count": counts_and_digest["agent_state_count"],
        "source_schema": "legacy_global_event_id_unique",
        "page_size": db.execute("PRAGMA page_size").fetchone()[0],
        "page_count": db.execute("PRAGMA page_count").fetchone()[0],
        "freelist_count": db.execute("PRAGMA freelist_count").fetchone()[0],
    }
    return meta, counts_and_digest


def run(*, source: Path, acknowledgment: str, mode: str = "inspect") -> dict:
    if acknowledgment != ACK:
        raise PermissionError("explicit owner-approved sanitized-copy acknowledgment required")
    if mode not in ("inspect", "rehearse"):
        raise ValueError("unknown mode")
    source = Path(source)
    if (source.is_symlink() or not source.is_file() or
            source.stat().st_size == 0):
        raise InspectionBlocked("source must be a nonempty regular sanitized copy")
    # Refuse a live/multi-file WAL store. An operator should use SQLite online
    # backup to create a DETACHED, checkpointed, sanitized source first.
    if any(Path(str(source) + suffix).exists() for suffix in ("-wal", "-shm")):
        raise InspectionBlocked("WAL/SHM sidecars present; provide detached checkpointed copy")
    original_sha = _file_sha256(source)
    db = _readonly(source)
    try:
        before, source_fingerprint = _preflight(db)
    finally:
        db.close()
    # The source file is never opened in read-write mode.
    if mode == "inspect":
        if _file_sha256(source) != original_sha:
            raise InspectionBlocked("input file changed during inspection")
        return {
            "schema": SCHEMA, "status": "INSPECT_ONLY", "source_untouched": True,
            "source_is_claimed_sanitized_not_verified": True,
            "aggregate": before, "mode": "inspect",
            "no_production_migration": True,
        }

    # Any file operation after this point is confined to a new temporary
    # directory. Private sanitized input is NOT copied to a repository or CI.
    free_bytes = shutil.disk_usage(tempfile.gettempdir()).free
    physical_size = source.stat().st_size
    suggested_free = max(128 * 1024 * 1024, physical_size * 6)
    if free_bytes < suggested_free:
        raise InspectionBlocked("insufficient free space for bounded test; no change attempted")
    with tempfile.TemporaryDirectory(prefix="hm-sanitized-rehearsal-") as temp:
        path = Path(temp)
        clone = path / "detached-copy.sqlite3"
        backup = path / "preserved-legacy-backup.sqlite3"
        started = time.perf_counter()
        source_db = _readonly(source)
        try:
            with sqlite3.connect(clone) as clone_db:
                source_db.backup(clone_db)
        finally:
            source_db.close()
        with sqlite3.connect(clone) as clone_db:
            if fingerprint(clone_db) != source_fingerprint:
                raise InspectionBlocked("source and disposable clone mismatch")
        start_migration = time.perf_counter()
        with HyperMemoryP1e(
                clone, migrate_legacy=True, legacy_backup_path=backup) as hm:
            migrated = fingerprint(hm.db)
            if migrated != source_fingerprint:
                raise InspectionBlocked("migrated state/ledger mismatch")
            # Confirm structural owner scope and keep any probe out of this
            # report: no source owner/event IDs are exposed.
            new_indexes = _indexes(hm.db)
            if new_indexes != {
                    ("owner_id", "event_id"),
                    ("owner_id", "agent_id", "seq")}:
                raise InspectionBlocked("new indexes not owner-scoped")
            migrate_seconds = time.perf_counter() - start_migration
            page_stats = {
                "page_size": hm.db.execute("PRAGMA page_size").fetchone()[0],
                "page_count": hm.db.execute("PRAGMA page_count").fetchone()[0],
                "freelist_count": hm.db.execute("PRAGMA freelist_count").fetchone()[0],
            }
            online_bytes = disk_bytes(clone)
            hm.checkpoint()
            after_checkpoint_bytes = disk_bytes(clone)
        with sqlite3.connect(backup) as backup_db:
            if fingerprint(backup_db) != source_fingerprint:
                raise InspectionBlocked("preserved backup not identical")
        with HyperMemoryP1e(clone) as reopened:
            if fingerprint(reopened.db) != source_fingerprint:
                raise InspectionBlocked("reopening migrated clone changed rows")
        total_seconds = time.perf_counter() - started
        results = {
            "source_clone_equal": True, "migrated_rows_equal": True,
            "preserved_backup_equal": True, "reopen_equal": True,
            "legacy_source_unchanged": None, "new_owner_indexes_valid": True,
        }
        store_bytes = {
            "temporary_migrated_online_total": sum(online_bytes.values()),
            "temporary_migrated_post_checkpoint_total":
                sum(after_checkpoint_bytes.values()),
            "temporary_preserved_backup_total": sum(disk_bytes(backup).values()),
        }
    # Check source a second time AFTER all temporary clones are removed.
    results["legacy_source_unchanged"] = (
        _file_sha256(source) == original_sha)
    if not all(results.values()):
        raise InspectionBlocked("source or copied rows changed during rehearsal")
    return {
        "schema": SCHEMA, "status": "PASS_DISPOSABLE_COPY_ONLY", "mode": "rehearse",
        "source_is_claimed_sanitized_not_verified": True,
        "aggregate": before, "checks": results, "sqlite_pages_after": page_stats,
        "scratch_disk_bytes": store_bytes,
        "wall_seconds": {"migration": migrate_seconds, "total": total_seconds},
        "free_disk_preflight_bytes": free_bytes,
        "suggested_min_free_bytes_not_guarantee": suggested_free,
        "no_production_migration": True,
        "limitations": [
            "No independent reviewer or authentic source/backup witness",
            "Acknowledgment does not prove consent or effective sanitization",
            "Read-only detached source only; live WAL/SHM databases prohibited",
            "Only disposable clones are migrated and deleted after the run",
            "No concurrency, power-loss, ENOSPC injection or long-run lock test",
            "No payload, event ID, owner ID, row digest or file path is exported",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="local-only detached sanitized copy; no live DB")
    parser.add_argument("--ack", required=True,
                        help="literal AUTHORIZED_AND_SANITIZED_COPY")
    parser.add_argument("--mode", choices=("inspect", "rehearse"),
                        default="inspect")
    parser.add_argument("--out", type=Path,
                        help="new JSON manifest path; never overwrites")
    args = parser.parse_args()
    data = run(source=args.source, acknowledgment=args.ack, mode=args.mode)
    payload = json.dumps(data, indent=2, sort_keys=True, allow_nan=False)
    if args.out is not None:
        with args.out.open("x", encoding="utf-8") as file:
            file.write(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
