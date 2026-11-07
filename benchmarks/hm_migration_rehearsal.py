"""Disposable synthetic rehearsal of HyperMemory's owner-namespace migration.

Creates a private temporary *legacy* SQLite fixture; never opens any user
database and never accepts a source database path. The fixture is copied using
SQLite online backup before migration; the source stays intact. This is NOT
proof of production crash recovery, throughput or independent verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from openworld_superkernel.hyper_memory_p1e import HyperMemoryP1e

SCHEMA = "openworld.hm.synthetic-namespace-migration-rehearsal.v1"
COLUMNS = "owner_id,agent_id,seq,event_id,provenance,event_type,payload,payload_hash"

LEGACY_SCHEMA = """
CREATE TABLE agent_state (
    owner_id TEXT NOT NULL, agent_id TEXT NOT NULL, state_json TEXT NOT NULL,
    PRIMARY KEY(owner_id,agent_id)
);
CREATE TABLE exact_events (
    owner_id TEXT NOT NULL, agent_id TEXT NOT NULL, seq INTEGER NOT NULL,
    event_id TEXT NOT NULL UNIQUE, provenance TEXT NOT NULL,
    event_type TEXT NOT NULL, payload BLOB NOT NULL,
    payload_hash TEXT NOT NULL, PRIMARY KEY(owner_id,agent_id,seq)
);
"""


def disk_bytes(path: Path) -> dict:
    return {suffix or "db": (
        (file.stat().st_size if (file := Path(str(path) + suffix)).exists() else 0)
    ) for suffix in ("", "-wal", "-shm")}


def _payload(i: int, length: int) -> bytes:
    # Deterministic non-sensitive fixture; the payload has no natural-language
    # content and cannot be mistaken for a production observation.
    digest = hashlib.sha256(f"synthetic-fixture:{i}".encode("ascii")).digest()
    return (digest * ((length + len(digest) - 1) // len(digest)))[:length]


def make_legacy(path: Path, *, events: int, owners: int,
                agents_per_owner: int, payload_bytes: int) -> None:
    db = sqlite3.connect(path, isolation_level=None)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.executescript(LEGACY_SCHEMA)
        seq_by_agent: dict[tuple[str, str], int] = {}
        wins: dict[tuple[str, str], int] = {}
        db.execute("BEGIN IMMEDIATE")
        try:
            for i in range(events):
                owner = f"synthetic-owner-{i % owners:02d}"
                agent = f"agent-{(i // owners) % agents_per_owner:02d}"
                key = (owner, agent)
                seq_by_agent[key] = seq_by_agent.get(key, 0) + 1
                # Mix small and large payloads without exceeding caller bound.
                length = (64, 256, 1024, payload_bytes)[i % 4]
                payload = _payload(i, length)
                db.execute(
                    "INSERT INTO exact_events (" + COLUMNS + ") "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (owner, agent, seq_by_agent[key], f"synthetic-event-{i:08d}",
                     "simulated", "lab_only", payload,
                     hashlib.sha256(payload).hexdigest()),
                )
                wins[key] = wins.get(key, 0) + (i % 2)
            for (owner, agent), n in seq_by_agent.items():
                # Preserve a realistic agent_state row during schema migration;
                # no predictor is trained from this dummy state.
                state = {
                    "seq": n, "n": n, "successes": wins[(owner, agent)],
                    "receipt": "synthetic-only", "selected": "static",
                }
                db.execute(
                    "INSERT INTO agent_state VALUES(?,?,?)",
                    (owner, agent, json.dumps(state, sort_keys=True)),
                )
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise AssertionError("invalid source SQLite fixture")
    finally:
        db.close()


def fingerprint(db: sqlite3.Connection) -> dict:
    """Independent row framing for source, clone, migration and backup checks."""
    def digest_query(sql: str) -> tuple[int, str]:
        digest = hashlib.sha256()
        count = 0
        for row in db.execute(sql):
            for cell in row:
                if cell is None:
                    value = b"N"
                elif isinstance(cell, bytes):
                    value = b"B" + cell
                elif isinstance(cell, int):
                    value = b"I" + str(cell).encode("ascii")
                elif isinstance(cell, str):
                    value = b"T" + cell.encode("utf-8")
                else:
                    raise AssertionError("unexpected SQLite row type")
                digest.update(len(value).to_bytes(8, "big"))
                digest.update(value)
            count += 1
        return count, digest.hexdigest()

    events = digest_query(
        "SELECT " + COLUMNS + " FROM exact_events "
        "ORDER BY owner_id,agent_id,seq"
    )
    state = digest_query(
        "SELECT owner_id,agent_id,state_json FROM agent_state "
        "ORDER BY owner_id,agent_id"
    )
    return {
        "exact_event_count": events[0], "exact_event_rows_sha256": events[1],
        "agent_state_count": state[0], "agent_state_rows_sha256": state[1],
    }


def inspect(path: Path) -> dict:
    db = sqlite3.connect(path)
    try:
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise AssertionError(f"SQLite integrity check failed: {path.name}")
        return fingerprint(db)
    finally:
        db.close()


def _physical_total(path: Path) -> int:
    return sum(disk_bytes(path).values())


def _rss() -> dict:
    try:
        import resource
    except ImportError:
        return {"peak_rss_native": None, "rss_units": "unavailable"}
    v = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    units = "KiB on Linux; bytes on macOS; platform specific otherwise"
    return {"peak_rss_native": v, "rss_units": units}


def run(*, events: int = 20000, owners: int = 12,
        agents_per_owner: int = 4, payload_bytes: int = 2048) -> dict:
    if (type(events) is not int or not 100 <= events <= 100000 or
            type(owners) is not int or not 2 <= owners <= 32 or
            type(agents_per_owner) is not int or
            not 1 <= agents_per_owner <= 16 or
            type(payload_bytes) is not int or
            not 1024 <= payload_bytes <= 8192):
        raise ValueError("bounded positive synthetic workload parameters required")
    with tempfile.TemporaryDirectory(prefix="openworld-hm-migration-") as folder:
        root = Path(folder)
        original = root / "original-legacy.sqlite3"
        clone = root / "disposable-copy.sqlite3"
        preserved = root / "pre-migration-backup.sqlite3"

        creation_start = time.perf_counter()
        make_legacy(
            original, events=events, owners=owners,
            agents_per_owner=agents_per_owner, payload_bytes=payload_bytes,
        )
        setup_seconds = time.perf_counter() - creation_start
        source_fp = inspect(original)
        source_disk = disk_bytes(original)

        source_db = sqlite3.connect(original)
        target_db = sqlite3.connect(clone)
        try:
            source_db.backup(target_db)
        finally:
            target_db.close()
            source_db.close()
        clone_fp = inspect(clone)
        if source_fp != clone_fp:
            raise AssertionError("disposable SQLite backup mismatch")

        migration_start = time.perf_counter()
        cpu_start = time.process_time()
        with HyperMemoryP1e(
            clone, migrate_legacy=True, legacy_backup_path=preserved,
        ) as store:
            migration_seconds = time.perf_counter() - migration_start
            migration_cpu_seconds = time.process_time() - cpu_start
            migrated_fp = fingerprint(store.db)
            if migrated_fp != source_fp:
                raise AssertionError("migration changed original exact/state rows")
            if store.db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise AssertionError("migrated DB corruption")

            # Namespace collision is allowed across owners, but the test
            # transaction must roll back, preserving fingerprint equality.
            first_event = store.db.execute(
                "SELECT event_id,owner_id FROM exact_events ORDER BY event_id LIMIT 1"
            ).fetchone()
            same_id, original_owner = first_event
            outsider = "synthetic-rehearsal-outsider"
            if store.exact_event(same_id, requester_owner_id=outsider) is not None:
                raise AssertionError("foreign owner existence oracle")
            store.db.execute("BEGIN IMMEDIATE")
            try:
                payload = b"synthetic-namespace-probe"
                store.db.execute(
                    "INSERT INTO exact_events (" + COLUMNS + ") "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (outsider, "probe", 1, same_id, "simulated", "lab_only",
                     payload, hashlib.sha256(payload).hexdigest()),
                )
                if store.exact_event(same_id, requester_owner_id=outsider) != payload:
                    raise AssertionError("owner namespace collision not supported")
                if store.exact_event(same_id, requester_owner_id=original_owner) is None:
                    raise AssertionError("original owner lost access")
            finally:
                store.db.execute("ROLLBACK")
            if fingerprint(store.db) != source_fp:
                raise AssertionError("uncommitted probe changed migrated ledger")
            online_disk = disk_bytes(clone)
            migrated_page_stats = {
                "page_size": store.db.execute("PRAGMA page_size").fetchone()[0],
                "page_count": store.db.execute("PRAGMA page_count").fetchone()[0],
                "freelist_count": store.db.execute("PRAGMA freelist_count").fetchone()[0],
            }
            store.checkpoint()
            checkpoint_disk = disk_bytes(clone)

        backup_fp = inspect(preserved)
        final_fp = inspect(clone)
        final_source_fp = inspect(original)
        if not (source_fp == clone_fp == migrated_fp == backup_fp ==
                final_fp == final_source_fp):
            raise AssertionError("source/clone/migrated/backup fingerprint mismatch")

        with HyperMemoryP1e(clone) as opened:
            if fingerprint(opened.db) != source_fp:
                raise AssertionError("reopen altered migrated state")
        return {
            "schema": SCHEMA,
            "status": "PASS: disposable synthetic migration rehearsal ONLY",
            "environment": {
                "python": sys.version.split()[0],
                "sqlite": sqlite3.sqlite_version,
                "platform": platform.platform(),
                "processor": platform.processor(),
                **_rss(),
            },
            "parameters": {
                "events": events, "owners": owners,
                "agents_per_owner": agents_per_owner,
                "maximum_payload_bytes": payload_bytes,
                "source_is_synthetic": True,
            },
            "original_fingerprint": source_fp,
            "verified": {
                "initial_source_copy_matches": source_fp == clone_fp,
                "migration_retains_full_row_and_state_bytes": migrated_fp == source_fp,
                "backup_retains_full_row_and_state_bytes": backup_fp == source_fp,
                "source_untouched": final_source_fp == source_fp,
                "post_migration_reopen": final_fp == source_fp,
                "owner_namespace_isolation": True,
                "collision_probe_transaction_rolled_back": True,
            },
            "sqlite_pages_after_migration": migrated_page_stats,
            "disk_bytes": {
                "source_initial": source_disk,
                "migrated_online": online_disk,
                "migrated_after_checkpoint": checkpoint_disk,
                "preserved_backup": disk_bytes(preserved),
            },
            "timings_seconds": {
                "fixture_generation": setup_seconds,
                "explicit_migration_wall": migration_seconds,
                "explicit_migration_cpu": migration_cpu_seconds,
            },
            "limits": [
                "All event bytes are synthetic; this is NOT a real database migration",
                "Local single-process fixture; no concurrent production writers or power-loss test",
                "No original source was modified; all files discarded after the run",
                "Correct row digest and SQLite integrity do not prove real-world authenticity",
                "Filesystem block allocation and cross-store atomicity not tested",
                "RSS peak is process-wide and may include earlier test execution",
            ],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=20000)
    parser.add_argument("--owners", type=int, default=12)
    parser.add_argument("--agents-per-owner", type=int, default=4)
    parser.add_argument("--payload-bytes", type=int, default=2048)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = run(
        events=args.events, owners=args.owners,
        agents_per_owner=args.agents_per_owner,
        payload_bytes=args.payload_bytes,
    )
    report = json.dumps(result, sort_keys=True, indent=2, allow_nan=False)
    if args.out:
        with args.out.open("x", encoding="utf-8") as output:
            output.write(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
