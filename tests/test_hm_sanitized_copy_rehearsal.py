"""Safe local sanitized-copy gate: no real data and no production migrations."""
from __future__ import annotations

import hashlib
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "benchmarks"))

from hm_sanitized_copy_rehearsal import (
    ACK, SCHEMA, InspectionBlocked, run,
)
from hm_migration_rehearsal import make_legacy, fingerprint


class TestSanitizedCopyInspection(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="hm-authorized-sanitized-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "claimed-sanitized-copy.sqlite"
        make_legacy(
            self.source, events=200, owners=4, agents_per_owner=2,
            payload_bytes=1024,
        )

    def test_unauthorized_refused_before_source_access(self):
        for ack in ("", "yes", "AUTHORIZED", "authorized_and_sanitized_copy"):
            with self.subTest(ack=ack):
                with self.assertRaises(PermissionError):
                    run(source=self.source, acknowledgment=ack, mode="rehearse")

    def test_inspect_only_preserves_original_and_hides_identifiers(self):
        before = self.source.read_bytes()
        report = run(source=self.source, acknowledgment=ACK, mode="inspect")
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["status"], "INSPECT_ONLY")
        self.assertEqual(report["aggregate"]["exact_event_count"], 200)
        self.assertEqual(report["aggregate"]["agent_state_count"], 8)
        self.assertEqual(report["aggregate"]["source_schema"],
                         "legacy_global_event_id_unique")
        self.assertEqual(self.source.read_bytes(), before)
        output = json.dumps(report)
        for forbidden in ("synthetic-event-", "synthetic-owner-",
                          "agent-00", "exact_event_rows_sha256",
                          str(self.source), "payload_hash"):
            self.assertNotIn(forbidden, output)

    def test_rehearsal_only_mutates_temporary_clones(self):
        before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with closing(sqlite3.connect(self.source)) as db:
            rows_before = fingerprint(db)
        report = run(source=self.source, acknowledgment=ACK, mode="rehearse")
        self.assertEqual(report["status"], "PASS_DISPOSABLE_COPY_ONLY")
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(report["aggregate"]["exact_event_count"], 200)
        self.assertGreater(report["scratch_disk_bytes"]
                           ["temporary_preserved_backup_total"], 0)
        self.assertGreater(report["sqlite_pages_after"]["page_count"], 0)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), before)
        with closing(sqlite3.connect(self.source)) as db:
            self.assertEqual(fingerprint(db), rows_before)
            indexes = [
                tuple(v[2] for v in db.execute(
                    'PRAGMA index_info("' + row[1] + '")'))
                for row in db.execute("PRAGMA index_list('exact_events')")
                if row[2]
            ]
            self.assertIn(("event_id",), indexes)
        output = json.dumps(report)
        self.assertNotIn(str(self.source), output)
        self.assertNotIn("synthetic-event-", output)
        self.assertNotIn("exact_event_rows_sha256", output)

    def test_rejects_sidecars_and_symlinks(self):
        (Path(str(self.source) + "-wal")).write_bytes(b"")
        with self.assertRaises(InspectionBlocked):
            run(source=self.source, acknowledgment=ACK, mode="inspect")
        Path(str(self.source) + "-wal").unlink()
        alias = self.root / "link.sqlite"
        try:
            alias.symlink_to(self.source)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unsupported on this platform")
        with self.assertRaises(InspectionBlocked):
            run(source=alias, acknowledgment=ACK, mode="rehearse")

    def test_unknown_schema_and_bad_digest_fail_closed(self):
        with closing(sqlite3.connect(self.source)) as db:
            db.execute("CREATE INDEX extra_event_type ON exact_events(event_type)")
        with self.assertRaises(InspectionBlocked):
            run(source=self.source, acknowledgment=ACK, mode="rehearse")
        with closing(sqlite3.connect(self.source)) as db:
            db.execute("DROP INDEX extra_event_type")
            db.execute(
                "UPDATE exact_events SET payload=X'AA' "
                "WHERE event_id='synthetic-event-00000000'"
            )
            db.commit()
        with self.assertRaises(InspectionBlocked):
            run(source=self.source, acknowledgment=ACK, mode="inspect")

    def test_cli_manifest_exclusive_and_no_source_path_leak(self):
        out = self.root / "report.json"
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "hm_sanitized_copy_rehearsal.py"),
            "--source", str(self.source),
            "--ack", ACK, "--mode", "inspect", "--out", str(out),
        ]
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                              timeout=60, check=True)
        report = json.loads(proc.stdout)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8")), report)
        self.assertNotIn(str(self.source), proc.stdout)
        saved = out.read_bytes()
        denied = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                                timeout=60, check=False)
        self.assertNotEqual(denied.returncode, 0)
        self.assertEqual(out.read_bytes(), saved)


if __name__ == "__main__":
    unittest.main()
