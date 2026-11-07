"""Single-DB synthetic consent/transfer atomicity reference tests."""
import sqlite3
import concurrent.futures
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from openworld_superkernel.transactional_world import (
    AtomicWorldLedger, TransferIntent, TransactionDenied,
)


def intent(**changes):
    fields = dict(intent_id='t-1', source_agent='agent-a', source_owner='owner-a',
                  target_agent='agent-b', target_owner='owner-b', amount=3,
                  purpose='synthetic-cooperation', nonce='nonce-1', expected_tick=0,
                  expires_at=200)
    fields.update(changes)
    return TransferIntent(**fields)


class AtomicLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'world.sqlite'
        self.ledger = AtomicWorldLedger(self.path)
        self.ledger.seed_account('agent-a', 'owner-a', 10)
        self.ledger.seed_account('agent-b', 'owner-b', 1)
        self.operation = intent()
        self.ledger.prepare(self.operation)

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def approve(self, role, owner, operation=None):
        op = operation or self.operation
        self.ledger.approve(intent_id=op.intent_id, role=role,
                            authenticated_owner=owner, expected_digest=op.digest())

    def both(self):
        self.approve('source', 'owner-a')
        self.approve('receiver', 'owner-b')

    def balances(self):
        return dict(self.ledger.db.execute('SELECT agent,balance FROM accounts'))

    def test_missing_receiver_denied(self):
        self.approve('source', 'owner-a')
        with self.assertRaises(TransactionDenied):
            self.ledger.execute(self.operation, now=120)
        self.assertEqual(self.balances(), {'agent-a': 10, 'agent-b': 1})

    def test_authorized_atomic_transfer_and_receipt(self):
        self.both()
        self.assertEqual(self.ledger.execute(self.operation, now=120), (0, 7, 4))
        self.assertEqual(self.balances(), {'agent-a': 7, 'agent-b': 4})
        self.assertEqual(self.ledger.db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 1)
        self.assertEqual(self.ledger.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0], 1)

    def test_idempotent_retry_same_intent(self):
        self.both()
        first = self.ledger.execute(self.operation, now=120)
        self.assertEqual(first, self.ledger.execute(self.operation, now=121))
        self.assertEqual(sum(self.balances().values()), 11)
        self.assertEqual(self.ledger.db.execute('SELECT tick FROM world_meta').fetchone()[0], 1)

    def test_wrong_independent_owner_denied(self):
        with self.assertRaises(TransactionDenied):
            self.approve('receiver', 'owner-a')
        self.assertEqual(self.ledger.db.execute('SELECT COUNT(*) FROM approvals').fetchone()[0], 0)

    def test_source_is_not_receiver(self):
        with self.assertRaises(ValueError):
            intent(target_owner='owner-a').canonical()

    def test_receiver_revocation_denied(self):
        self.both()
        self.ledger.revoke_consent(intent_id='t-1', role='receiver',
                                   authenticated_owner='owner-b')
        with self.assertRaises(TransactionDenied):
            self.ledger.execute(self.operation, now=120)
        self.assertEqual(self.balances()['agent-a'], 10)

    def test_injected_mid_transaction_failure_rolls_back_everything(self):
        self.both()
        with self.assertRaises(RuntimeError):
            self.ledger.execute(self.operation, now=120, inject_failure=True)
        self.assertEqual(self.balances(), {'agent-a': 10, 'agent-b': 1})
        self.assertEqual(self.ledger.db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 0)
        self.assertEqual(self.ledger.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0], 0)
        self.assertEqual(self.ledger.db.execute('SELECT tick FROM world_meta').fetchone()[0], 0)
        self.assertEqual(self.ledger.execute(self.operation, now=120), (0, 7, 4))

    def test_reopen_preserves_receipt_and_idempotency(self):
        self.both()
        self.ledger.execute(self.operation, now=120)
        self.ledger.close()
        self.ledger = AtomicWorldLedger(self.path)
        self.assertEqual(self.ledger.execute(self.operation, now=121), (0, 7, 4))

    def test_changed_payload_same_id_fails(self):
        with self.assertRaises(TransactionDenied):
            self.ledger.prepare(intent(amount=100))
        self.both()
        with self.assertRaises(TransactionDenied):
            self.ledger.execute(intent(amount=100), now=120)

    def test_expired_intent_denied(self):
        self.both()
        with self.assertRaises(TransactionDenied):
            self.ledger.execute(self.operation, now=200)

    def test_insufficient_resources_denied(self):
        self.both()
        self.ledger.db.execute('UPDATE accounts SET balance=2 WHERE agent=?', ('agent-a',))
        with self.assertRaises(TransactionDenied):
            self.ledger.execute(self.operation, now=120)

    def test_no_reapproval_after_execution(self):
        self.both()
        self.ledger.execute(self.operation, now=120)
        with self.assertRaises(TransactionDenied):
            self.approve('receiver', 'owner-b')

    def test_stale_tick_denied(self):
        self.both()
        self.ledger.db.execute('UPDATE world_meta SET tick=1')
        with self.assertRaises(TransactionDenied):
            self.ledger.execute(self.operation, now=120)

    def test_new_nonce_must_be_unique(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.ledger.prepare(intent(intent_id='t-2', amount=1))

    def test_ownership_drift_denied(self):
        self.both()
        self.ledger.db.execute('UPDATE accounts SET owner=? WHERE agent=?',
                               ('owner-mallory', 'agent-b'))
        with self.assertRaises(TransactionDenied):
            self.ledger.execute(self.operation, now=120)

    def test_target_balance_overflow_denied(self):
        self.both()
        self.ledger.db.execute('UPDATE accounts SET balance=? WHERE agent=?',
                               (2**63 - 1, 'agent-b'))
        with self.assertRaises(TransactionDenied):
            self.ledger.execute(self.operation, now=120)

    def test_reject_oversize_integer_before_sqlite_write(self):
        with self.assertRaises(ValueError):
            intent(amount=2**63).canonical()
        with self.assertRaises(ValueError):
            self.ledger.seed_account('agent-c', 'owner-c', 2**63)

    def test_competing_intents_do_not_both_consume_same_world_tick(self):
        another = intent(intent_id='t-2', nonce='nonce-2', amount=2)
        self.ledger.prepare(another)
        for i in (self.operation, another):
            self.ledger.approve(intent_id=i.intent_id, role='source',
                                authenticated_owner='owner-a', expected_digest=i.digest())
            self.ledger.approve(intent_id=i.intent_id, role='receiver',
                                authenticated_owner='owner-b', expected_digest=i.digest())

        def attempt(i):
            with AtomicWorldLedger(self.path) as db:
                try:
                    return db.execute(i, now=120)
                except TransactionDenied:
                    return 'denied'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, [self.operation, another]))
        self.assertEqual(sum(result != 'denied' for result in results), 1)
        self.assertEqual(self.ledger.db.execute('SELECT tick FROM world_meta').fetchone()[0], 1)
        self.assertEqual(sum(self.balances().values()), 11)

    def test_same_owner_cannot_approve_twice(self):
        self.approve('source', 'owner-a')
        with self.assertRaises(TransactionDenied):
            self.approve('source', 'owner-a')


if __name__ == '__main__':
    unittest.main()
