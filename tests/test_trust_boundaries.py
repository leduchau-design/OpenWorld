"""Research-only trust boundary regression tests; no real identities or data."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from openworld_superkernel.trust_boundaries import (
    CapabilityAuthority, ScopedMemoryReader, TrustBoundaryError,
    capture_anchor, ledger_snapshot, online_backup, verify_anchor,
)

KEY = b'externally managed verification demo key of 64 bytes!_N0T_REAL'


class TestCapabilityGrants(unittest.TestCase):
    def setUp(self):
        self.authority = CapabilityAuthority(KEY, issuer='synthetic-issuer',
                                             audience='synthetic-openworld')
        self.token = self.authority.issue(principal='user-one', owner='owner-one',
                                           resource='agent-one', action='read_state',
                                           valid_from=100, expires_at=160,
                                           nonce='test-once')

    def _verify(self, token=None, **overrides):
        kwargs = dict(authenticated_principal='user-one', owner='owner-one',
                      resource='agent-one', action='read_state', now=120)
        kwargs.update(overrides)
        return self.authority.verify(token or self.token, **kwargs)

    def test_valid_exact_scope(self):
        self.assertEqual(self._verify().nonce, 'test-once')

    def test_unknown_caller_rejected(self):
        with self.assertRaises(PermissionError):
            self._verify(authenticated_principal='user-two')

    def test_cross_owner_rejected(self):
        with self.assertRaises(PermissionError):
            self._verify(owner='owner-two')

    def test_cross_resource_rejected(self):
        with self.assertRaises(PermissionError):
            self._verify(resource='agent-two')

    def test_action_escalation_rejected(self):
        with self.assertRaises(PermissionError):
            self._verify(action='write_agent')

    def test_expiration_boundary(self):
        self.assertTrue(self._verify(now=159))
        with self.assertRaises(PermissionError):
            self._verify(now=160)
        with self.assertRaises(PermissionError):
            self._verify(now=99)

    def test_revocation(self):
        self.authority.revoke('test-once')
        with self.assertRaises(PermissionError):
            self._verify()

    def test_tampered_claim(self):
        token = json.loads(self.token)
        token['body']['resource'] = 'agent-two'
        with self.assertRaises(TrustBoundaryError):
            self._verify(json.dumps(token))

    def test_tampered_signature(self):
        token = json.loads(self.token)
        token['signature'] = '0' * 64
        with self.assertRaises(TrustBoundaryError):
            self._verify(json.dumps(token))

    def test_wrong_verification_key(self):
        alternate = CapabilityAuthority(b'another distinct signing secret must be long enough',
                                         issuer='synthetic-issuer',
                                         audience='synthetic-openworld')
        with self.assertRaises(TrustBoundaryError):
            alternate.verify(self.token, authenticated_principal='user-one',
                             owner='owner-one', resource='agent-one',
                             action='read_state', now=120)

    def test_wrong_audience(self):
        alternate = CapabilityAuthority(KEY, issuer='synthetic-issuer',
                                         audience='different-audience')
        with self.assertRaises(TrustBoundaryError):
            alternate.verify(self.token, authenticated_principal='user-one',
                             owner='owner-one', resource='agent-one',
                             action='read_state', now=120)

    def test_duplicate_json_keys(self):
        # Reject duplicate keys rather than silently choosing the last claim.
        token = self.token.replace('"signature":', '"signature":"bad","signature":')
        with self.assertRaises(TrustBoundaryError):
            self._verify(token)

    def test_max_ttl(self):
        with self.assertRaises(TrustBoundaryError):
            self.authority.issue(principal='u', owner='o', resource='a',
                                 action='read_state', valid_from=1, expires_at=99999)

    def test_weak_key_rejected(self):
        with self.assertRaises(ValueError):
            CapabilityAuthority(b'weak', issuer='x', audience='y')

    def test_unknown_action_rejected(self):
        with self.assertRaises(TrustBoundaryError):
            self.authority.issue(principal='u', owner='o', resource='a',
                                 action='sudo', valid_from=1, expires_at=2)


class TestAnchoredExactLedger(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'base.db'
        self.db = sqlite3.connect(self.path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('''CREATE TABLE exact_events (
            owner_id TEXT NOT NULL, agent_id TEXT NOT NULL, seq INTEGER NOT NULL,
            event_id TEXT UNIQUE NOT NULL, provenance TEXT NOT NULL,
            event_type TEXT NOT NULL, payload BLOB NOT NULL,
            payload_hash TEXT NOT NULL,
            PRIMARY KEY(owner_id,agent_id,seq))''')
        self._insert(2, b'consent granted')
        self._insert(5, b'payment evidence')
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.folder.cleanup()

    def _insert(self, seq, payload, owner='owner-one', agent='agent-one'):
        self.db.execute('INSERT INTO exact_events VALUES (?,?,?,?,?,?,?,?)',
                        (owner, agent, seq, f'{owner}/{agent}:{seq}',
                         'observed_recorded', 'consent', payload,
                         hashlib.sha256(payload).hexdigest()))

    def _anchor(self):
        return capture_anchor(self.db, owner='owner-one', agent='agent-one',
                              external_signing_key=KEY)

    def _verify(self, signed=None):
        return verify_anchor(self.db, signed_anchor=signed or self._anchor(),
                             external_verification_key=KEY,
                             owner='owner-one', agent='agent-one')

    def test_correct_snapshot(self):
        signed = self._anchor()
        self.assertTrue(self._verify(signed))
        info = ledger_snapshot(self.db, owner='owner-one', agent='agent-one')
        self.assertEqual(info['count'], 2)
        self.assertEqual(info['last_sequence'], 5)
        self.assertEqual(len(info['head_sha256']), 64)

    def test_payload_tampering(self):
        signed = self._anchor()
        self.db.execute("UPDATE exact_events SET payload=? WHERE seq=2", (b'edited',))
        with self.assertRaises(TrustBoundaryError):
            self._verify(signed)

    def test_payload_and_hash_tampering(self):
        signed = self._anchor()
        changed = b'edited and rehashed'
        self.db.execute('UPDATE exact_events SET payload=?, payload_hash=? WHERE seq=2',
                        (changed, hashlib.sha256(changed).hexdigest()))
        with self.assertRaisesRegex(TrustBoundaryError, 'diverges'):
            self._verify(signed)

    def test_delete_old_record_detected(self):
        signed = self._anchor()
        self.db.execute('DELETE FROM exact_events WHERE seq=2')
        with self.assertRaises(TrustBoundaryError):
            self._verify(signed)

    def test_insert_after_anchor_fails_exact_checkpoint(self):
        signed = self._anchor()
        self._insert(7, b'new evidence')
        with self.assertRaises(TrustBoundaryError):
            self._verify(signed)

    def test_wrong_owner(self):
        with self.assertRaises(PermissionError):
            verify_anchor(self.db, signed_anchor=self._anchor(),
                          external_verification_key=KEY,
                          owner='other-owner', agent='agent-one')

    def test_wrong_key(self):
        with self.assertRaises(TrustBoundaryError):
            verify_anchor(self.db, signed_anchor=self._anchor(),
                          external_verification_key=b'correct-length but totally different demo signing key',
                          owner='owner-one', agent='agent-one')

    def test_valid_empty_anchor_has_no_historical_guarantee(self):
        signed = capture_anchor(self.db, owner='never-seen', agent='agent',
                                external_signing_key=KEY)
        self.assertTrue(verify_anchor(self.db, signed_anchor=signed,
                                      external_verification_key=KEY,
                                      owner='never-seen', agent='agent'))
        self.assertEqual(ledger_snapshot(self.db, owner='never-seen',
                                          agent='agent')['count'], 0)

    def test_modified_owner_field_detected(self):
        signed = self._anchor()
        self.db.execute('UPDATE exact_events SET owner_id=? WHERE seq=2',
                        ('owner-two',))
        with self.assertRaises(TrustBoundaryError):
            self._verify(signed)

    def test_online_backup_restore_snapshot(self):
        signed = self._anchor()
        backup_file = Path(self.folder.name) / 'backup.db'
        online_backup(self.db, backup_file)
        with sqlite3.connect(backup_file) as restored:
            self.assertTrue(verify_anchor(restored, signed_anchor=signed,
                                          external_verification_key=KEY,
                                          owner='owner-one', agent='agent-one'))
        with self.assertRaises(FileExistsError):
            online_backup(self.db, backup_file)

    def test_online_backup_includes_wal_records(self):
        self._insert(9, b'event in uncheckpointed WAL')
        self.db.commit()
        signed = self._anchor()
        backup_file = Path(self.folder.name) / 'wal-copy.db'
        online_backup(self.db, backup_file)
        with sqlite3.connect(backup_file) as restored:
            self.assertTrue(verify_anchor(restored, signed_anchor=signed,
                                          external_verification_key=KEY,
                                          owner='owner-one', agent='agent-one'))
            self.assertEqual(ledger_snapshot(restored, owner='owner-one',
                                              agent='agent-one')['count'], 3)


class FakeMemoryStore:
    def get_state(self, *, owner_id, agent_id, requester_owner_id):
        return {'owner': owner_id, 'agent': agent_id, 'requester': requester_owner_id}

    def exact_event(self, event_id, *, requester_owner_id):
        return (event_id + '/' + requester_owner_id).encode()


class TestScopedMemoryReader(unittest.TestCase):
    def setUp(self):
        self.identity = 'u1'
        self.authority = CapabilityAuthority(KEY, issuer='synthetic', audience='app')
        self.reader = ScopedMemoryReader(FakeMemoryStore(), self.authority,
                                          authenticated_principal=lambda: self.identity)
        now = __import__('time').time()
        self.start = int(now) - 5
        self.end = int(now) + 120

    def grant(self, action, resource):
        return self.authority.issue(principal='u1', owner='owner-1', resource=resource,
                                    action=action, valid_from=self.start,
                                    expires_at=self.end)

    def test_read_state_scoped(self):
        token = self.grant('read_state', 'agent-1')
        self.assertEqual(self.reader.read_state(token, owner='owner-1', agent='agent-1')['agent'],
                         'agent-1')
        with self.assertRaises(PermissionError):
            self.reader.read_state(token, owner='owner-1', agent='agent-2')

    def test_read_event_scoped(self):
        token = self.grant('read_event', 'event-1')
        self.assertEqual(self.reader.read_event(token, owner='owner-1', event_id='event-1'),
                         b'event-1/owner-1')
        with self.assertRaises(PermissionError):
            self.reader.read_event(token, owner='owner-2', event_id='event-1')

    def test_spoofed_principal_rejected(self):
        token = self.grant('read_state', 'agent-1')
        self.identity = 'attacker'
        with self.assertRaises(PermissionError):
            self.reader.read_state(token, owner='owner-1', agent='agent-1')

    def test_wrong_action_rejected(self):
        token = self.grant('read_event', 'agent-1')
        with self.assertRaises(PermissionError):
            self.reader.read_state(token, owner='owner-1', agent='agent-1')


if __name__ == '__main__':
    unittest.main()
