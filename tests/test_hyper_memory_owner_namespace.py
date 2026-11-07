"""Operator-gated SQLite migration and exact-event namespace safety tests."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openworld_superkernel.hyper_memory_p1e import (
    EvidenceIntegrityError, HyperMemoryP1e, LegacyNamespaceMigrationRequired,
    UnexpectedExactEventSchema,
    Observation,
)
from openworld_superkernel.memory_contracts import MemoryEvent, Provenance
from openworld_superkernel.trust_boundaries import (
    ledger_snapshot, online_backup,
)


LEGACY_DDL = """
CREATE TABLE exact_events (
    owner_id TEXT NOT NULL, agent_id TEXT NOT NULL, seq INTEGER NOT NULL,
    event_id TEXT NOT NULL UNIQUE, provenance TEXT NOT NULL,
    event_type TEXT NOT NULL, payload BLOB NOT NULL,
    payload_hash TEXT NOT NULL, PRIMARY KEY (owner_id, agent_id, seq)
);
"""


def make_legacy(path: Path, *, count: int = 3, tamper: bool = False,
                custom_index: bool = False, trigger: bool = False):
    with sqlite3.connect(path) as conn:
        conn.executescript(LEGACY_DDL)
        for i in range(1, count + 1):
            data = f"protected legacy event {i}".encode("ascii")
            hash_value = hashlib.sha256(data).hexdigest()
            if tamper and i == 1:
                hash_value = "f" * 64
            conn.execute(
                "INSERT INTO exact_events VALUES(?,?,?,?,?,?,?,?)",
                ("owner-a", "agent-a", i, f"same:{i}", "observed_recorded",
                 "payment", data, hash_value),
            )
        if custom_index:
            conn.execute("CREATE INDEX extra_event_index ON exact_events(event_type)")
        if trigger:
            conn.execute(
                "CREATE TRIGGER protected_change AFTER UPDATE ON exact_events "
                "BEGIN SELECT 1; END")


def new_event(owner: str, *, event_id: str, data: bytes = b"owner-b event"):
    return Observation(
        event=MemoryEvent(
            event_id=event_id, owner_id=owner, event_type="payment",
            provenance=Provenance.OBSERVED_RECORDED,
            payload=data, protected=True,
        ),
        agent_id="agent-b", sequence_number=1, outcome=1,
    )


class TestOwnerNamespaceMigration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "legacy.sqlite"
        self.backup = self.root / "before-migration.sqlite"

    def test_reopen_legacy_refuses_silent_migration(self):
        make_legacy(self.source)
        with self.assertRaises(LegacyNamespaceMigrationRequired):
            HyperMemoryP1e(self.source)
        self.assertFalse(self.backup.exists())
        with sqlite3.connect(self.source) as db:
            unique = [row[1] for row in db.execute("PRAGMA index_list('exact_events')")]
            self.assertTrue(unique)
            self.assertEqual(db.execute(
                "SELECT count(*) FROM exact_events").fetchone()[0], 3)

    def test_migration_requires_explicit_backup_path(self):
        make_legacy(self.source)
        with self.assertRaises(LegacyNamespaceMigrationRequired):
            HyperMemoryP1e(self.source, migrate_legacy=True)
        with self.assertRaises(ValueError):
            HyperMemoryP1e(self.source, legacy_backup_path=self.backup)
        self.assertFalse(self.backup.exists())

    def test_atomic_copy_backup_bytes_and_owner_collision(self):
        make_legacy(self.source, count=5)
        with sqlite3.connect(self.source) as db:
            originals = list(db.execute(
                "SELECT * FROM exact_events ORDER BY owner_id,agent_id,seq"))
            snapshot_before = ledger_snapshot(db, owner="owner-a", agent="agent-a")
        with HyperMemoryP1e(self.source, migrate_legacy=True,
                            legacy_backup_path=self.backup) as store:
            self.assertTrue(self.backup.exists())
            migrated = list(store.db.execute(
                "SELECT * FROM exact_events ORDER BY owner_id,agent_id,seq"))
            self.assertEqual(originals, migrated)
            self.assertEqual(store.db.execute(
                "PRAGMA integrity_check").fetchone(), ("ok",))
            self.assertEqual(ledger_snapshot(
                store.db, owner="owner-a", agent="agent-a"), snapshot_before)
            self.assertEqual(
                store.exact_event("same:1", requester_owner_id="owner-a"),
                b"protected legacy event 1")
            self.assertIsNone(
                store.exact_event("same:1", requester_owner_id="owner-b"))
            other = new_event("owner-b", event_id="same:1")
            store.apply_batch([other], requester_owner_id="owner-b")
            self.assertEqual(store.exact_event(
                "same:1", requester_owner_id="owner-b"), other.event.payload)
            self.assertEqual(store.exact_event(
                "same:1", requester_owner_id="owner-a"),
                b"protected legacy event 1")
        with sqlite3.connect(self.backup) as db:
            self.assertEqual(db.execute(
                "PRAGMA integrity_check").fetchone(), ("ok",))
            self.assertEqual(list(db.execute(
                "SELECT * FROM exact_events ORDER BY owner_id,agent_id,seq")),
                originals)
            self.assertEqual(ledger_snapshot(
                db, owner="owner-a", agent="agent-a"), snapshot_before)
        # Reopen migrated database without migration flag and no new backup.
        with HyperMemoryP1e(self.source) as store:
            self.assertEqual(
                store.exact_event("same:1", requester_owner_id="owner-b"),
                b"owner-b event")

    def test_preexisting_backup_fails_closed_without_modifying_source(self):
        make_legacy(self.source)
        self.backup.write_bytes(b"do not overwrite")
        with self.assertRaises(FileExistsError):
            HyperMemoryP1e(self.source, migrate_legacy=True,
                            legacy_backup_path=self.backup)
        self.assertEqual(self.backup.read_bytes(), b"do not overwrite")
        with sqlite3.connect(self.source) as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM exact_events").fetchone()[0], 3)
        with self.assertRaises(LegacyNamespaceMigrationRequired):
            HyperMemoryP1e(self.source)

    def test_tampered_payload_rejected_before_backup_or_mutation(self):
        make_legacy(self.source, tamper=True)
        with self.assertRaises(EvidenceIntegrityError):
            HyperMemoryP1e(self.source, migrate_legacy=True,
                            legacy_backup_path=self.backup)
        self.assertFalse(self.backup.exists())
        with sqlite3.connect(self.source) as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM exact_events").fetchone()[0], 3)

    def test_custom_index_refused_without_discarding_it(self):
        make_legacy(self.source, custom_index=True)
        with self.assertRaises(UnexpectedExactEventSchema):
            HyperMemoryP1e(self.source, migrate_legacy=True,
                            legacy_backup_path=self.backup)
        with sqlite3.connect(self.source) as db:
            self.assertIsNotNone(db.execute(
                "SELECT name FROM sqlite_master WHERE name='extra_event_index'"
            ).fetchone())
        self.assertFalse(self.backup.exists())

    def test_refused_legacy_open_has_no_schema_or_journal_side_effect(self):
        make_legacy(self.source)
        with sqlite3.connect(self.source) as db:
            before_schema = list(db.execute(
                "SELECT name,sql FROM sqlite_master ORDER BY name"))
            before_journal = db.execute("PRAGMA journal_mode").fetchone()
        with self.assertRaises(LegacyNamespaceMigrationRequired):
            HyperMemoryP1e(self.source)
        with sqlite3.connect(self.source) as db:
            self.assertEqual(list(db.execute(
                "SELECT name,sql FROM sqlite_master ORDER BY name")), before_schema)
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone(),
                             before_journal)

    def test_one_thousand_preserved_exact_rows_and_backup(self):
        make_legacy(self.source, count=1000)
        with HyperMemoryP1e(
            self.source, migrate_legacy=True, legacy_backup_path=self.backup
        ) as store:
            self.assertEqual(store.db.execute(
                "SELECT count(*) FROM exact_events").fetchone()[0], 1000)
            self.assertEqual(store.exact_event(
                "same:1000", requester_owner_id="owner-a"),
                b"protected legacy event 1000")
            self.assertEqual(store.db.execute(
                "PRAGMA integrity_check").fetchone(), ("ok",))
        with sqlite3.connect(self.backup) as backup:
            self.assertEqual(backup.execute(
                "SELECT count(*) FROM exact_events").fetchone()[0], 1000)

    def test_custom_trigger_refused_without_discarding_it(self):
        make_legacy(self.source, trigger=True)
        with self.assertRaises(UnexpectedExactEventSchema):
            HyperMemoryP1e(self.source, migrate_legacy=True,
                            legacy_backup_path=self.backup)
        with sqlite3.connect(self.source) as db:
            self.assertIsNotNone(db.execute(
                "SELECT name FROM sqlite_master WHERE name='protected_change'"
            ).fetchone())
        self.assertFalse(self.backup.exists())

    def test_scoped_new_store_does_not_require_backup(self):
        with HyperMemoryP1e(self.root / "new.sqlite") as store:
            item = new_event("owner-a", event_id="repeat")
            store.apply_batch([item], requester_owner_id="owner-a")
            self.assertEqual(store.exact_event(
                "repeat", requester_owner_id="owner-a"), item.event.payload)
        self.assertFalse(self.backup.exists())

    def test_authenticated_gates_still_required(self):
        # The lower-level store expects an already authenticated owner string.
        # A forged owner string is NOT an authorization grant; callers must use
        # the capability/identity facade and not expose the raw store.
        with HyperMemoryP1e(self.root / "new.sqlite") as store:
            own = new_event("owner-a", event_id="private")
            store.apply_batch([own], requester_owner_id="owner-a")
            self.assertIsNone(store.exact_event(
                "private", requester_owner_id="owner-b"))
            with self.assertRaises(PermissionError):
                store.get_state(owner_id="owner-a", agent_id="agent-b",
                                requester_owner_id="owner-b")
            with self.assertRaises(PermissionError):
                store.apply_batch(
                    [new_event("owner-b", event_id="private")],
                    requester_owner_id="owner-a")


if __name__ == "__main__":
    unittest.main()
