"""SEC-003 failure-focused witness tests; all local/synthetic.

An in-memory witness models independent custody *only for this fixture*.
It is not an external secure monotonic service.
"""
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from openworld_superkernel.anti_rollback import (
    InMemoryWitness, WitnessUnavailable, WitnessedAuthority,
    authority_fingerprint,
)


class TestAuthority:
    """Narrow SQLite mock matching SEC-002 storage, not an authenticator."""

    def __init__(self, path):
        self.db = sqlite3.connect(str(path), isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS authority_config (
            singleton INTEGER PRIMARY KEY, issuer TEXT, audience TEXT, active_kid TEXT);
        CREATE TABLE IF NOT EXISTS signing_keys (kid TEXT PRIMARY KEY, status TEXT);
        CREATE TABLE IF NOT EXISTS grants (
            jti TEXT PRIMARY KEY, body_json TEXT, key_id TEXT, owner TEXT,
            subject TEXT, used INTEGER, max_uses INTEGER, revoked INTEGER);
        CREATE TABLE IF NOT EXISTS audit_log (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT, jti TEXT,
            actor TEXT, occurred_at INTEGER);
        ''')
        if self.db.execute('SELECT COUNT(*) FROM authority_config').fetchone()[0] == 0:
            self.db.execute('INSERT INTO authority_config VALUES(1,?,?,?)',
                            ('issuer', 'audience', 'k1'))
            self.db.execute('INSERT INTO signing_keys VALUES(?,?)', ('k1', 'active'))

    def issue(self, name='g1'):
        self.db.execute('INSERT INTO grants VALUES(?,?,?,?,?,?,?,?)',
                        (name, '{}', 'k1', 'owner', 'subject', 0, 1, 0))
        self.db.execute('INSERT INTO audit_log(event,jti,actor,occurred_at) VALUES(?,?,?,?)',
                        ('issue', name, 'owner', 1000))
        return name

    def revoke(self, name='g1'):
        self.db.execute('UPDATE grants SET revoked=1 WHERE jti=?', (name,))
        self.db.execute('INSERT INTO audit_log(event,jti,actor,occurred_at) VALUES(?,?,?,?)',
                        ('revoke', name, 'owner', 1001))

    def authorize(self, name='g1'):
        changed = self.db.execute('UPDATE grants SET used=used+1 WHERE jti=? '
                                  'AND revoked=0 AND used<max_uses', (name,)).rowcount
        if changed != 1:
            raise PermissionError('revoked or exhausted')
        self.db.execute('INSERT INTO audit_log(event,jti,actor,occurred_at) VALUES(?,?,?,?)',
                        ('consume', name, 'subject', 1002))
        return 'subject'

    def close(self):
        self.db.close()


class AntiRollbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'auth.db'
        self.backup = Path(self.temp.name) / 'backup.db'
        self.raw = TestAuthority(self.path)
        self.witness = InMemoryWitness()
        self.safe = WitnessedAuthority(self.raw, self.witness)
        self.safe.initialize_empty_genesis()

    def tearDown(self):
        self.raw.close()
        self.temp.cleanup()

    def restart(self):
        self.raw.close()
        self.raw = TestAuthority(self.path)
        self.safe = WitnessedAuthority(self.raw, self.witness)

    def make_backup(self):
        with sqlite3.connect(str(self.backup)) as output:
            self.raw.db.backup(output)

    def restore(self):
        self.raw.close()
        shutil.copyfile(self.backup, self.path)
        self.raw = TestAuthority(self.path)
        self.safe = WitnessedAuthority(self.raw, self.witness)

    def test_fresh_genesis_is_explicit(self):
        self.assertEqual(self.safe.verify_current().epoch, 0)
        with self.assertRaises(WitnessUnavailable):
            self.safe.initialize_empty_genesis()

    def test_normal_issue_revoke_and_restart(self):
        self.safe.issue('op1')
        self.safe.revoke('op2')
        self.restart()
        self.safe.verify_current()
        with self.assertRaises(PermissionError):
            self.raw.authorize()

    def test_restored_backup_after_revocation_denied(self):
        self.safe.issue('op1')
        self.make_backup()
        self.safe.revoke('op2')
        self.restore()
        with self.assertRaises(WitnessUnavailable):
            self.safe.verify_current()
        with self.assertRaises(WitnessUnavailable):
            self.safe.authorize('op3')

    def test_restored_backup_after_consumption_denied(self):
        self.safe.issue('op1')
        self.make_backup()
        self.assertEqual(self.safe.authorize('op2'), 'subject')
        self.restore()
        with self.assertRaises(WitnessUnavailable):
            self.safe.authorize('op3')

    def test_missing_witness_rejects(self):
        self.safe.issue('op1')
        self.witness.available = False
        with self.assertRaises(WitnessUnavailable):
            self.safe.revoke('op2')

    def test_loss_of_witness_cannot_be_reprovisioned_on_nonempty(self):
        self.safe.issue('op1')
        another = InMemoryWitness()
        with self.assertRaises(WitnessUnavailable):
            WitnessedAuthority(self.raw, another).initialize_empty_genesis()

    def test_pending_after_effect_failure_denies(self):
        with self.assertRaises(RuntimeError):
            self.safe._mutate('op1', lambda: (_ for _ in ()).throw(RuntimeError('crash')))
        with self.assertRaises(WitnessUnavailable):
            self.safe.verify_current()
        with self.assertRaises(WitnessUnavailable):
            self.safe.issue('op2')

    def test_pending_after_commit_before_finalize_denies(self):
        def mutation():
            self.raw.issue()
            raise RuntimeError('crash before external finalize')
        with self.assertRaises(RuntimeError):
            self.safe._mutate('op1', mutation)
        self.restart()
        with self.assertRaises(WitnessUnavailable):
            self.safe.verify_current()

    def test_stale_expected_fence_denied(self):
        before = self.witness.head()
        self.safe.issue('op1')
        with self.assertRaises(WitnessUnavailable):
            self.witness.begin(expected=before, operation_id='stale')

    def test_raw_db_bypass_is_detected_but_not_prevented(self):
        self.raw.issue('untrusted-direct-write')
        with self.assertRaises(WitnessUnavailable):
            self.safe.verify_current()

    def test_refuse_bootstrap_after_restore(self):
        self.safe.issue('op1')
        self.make_backup()
        self.safe.revoke('op2')
        self.restore()
        with self.assertRaises(WitnessUnavailable):
            self.safe.initialize_empty_genesis()

    def test_initial_fingerprint_changes_with_security_mutation(self):
        before = authority_fingerprint(self.raw.db)
        self.raw.issue('x')
        self.assertNotEqual(before, authority_fingerprint(self.raw.db))


if __name__ == '__main__':
    unittest.main()
