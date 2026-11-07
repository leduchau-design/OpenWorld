"""P1 optional PostgreSQL port invariants: no paid services or external writes.

The PostgreSQL integration case is disabled unless the operator explicitly
provisions a throwaway, empty PostgreSQL database and opt-in environment vars.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from openworld_superkernel.postgres_control_plane import (
    PostgresUnavailable, PostgresWorldLedger, SCHEMA_STATEMENTS,
    connect_postgres,
)
from openworld_superkernel.transactional_world import (
    AtomicWorldLedger, TransactionDenied, TransferIntent,
)


class FakeConnection:
    autocommit = True

    def __init__(self):
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)

    def transaction(self):
        raise AssertionError('only schema is tested with fake connection')


class InvalidConnection(FakeConnection):
    autocommit = False


class PostgresPortContractTests(unittest.TestCase):
    def test_requires_explicit_autocommit(self):
        with self.assertRaises(ValueError):
            PostgresWorldLedger(InvalidConnection())

    def test_missing_transaction_context_rejected(self):
        class NoTransaction:
            autocommit = True
        with self.assertRaises(TypeError):
            PostgresWorldLedger(NoTransaction())

    def test_schema_is_explicit_operator_action(self):
        conn = FakeConnection()
        PostgresWorldLedger(conn, initialize=False)
        self.assertEqual(conn.statements, [])
        PostgresWorldLedger(conn, initialize=True)
        self.assertEqual(conn.statements, list(SCHEMA_STATEMENTS))

    def test_schema_has_unique_intent_nonce_and_receipt(self):
        sql = '\n'.join(SCHEMA_STATEMENTS)
        for constraint in ('nonce TEXT NOT NULL UNIQUE',
                           'intent_id TEXT PRIMARY KEY REFERENCES',
                           'PRIMARY KEY(intent_id,role)',
                           'balance BIGINT NOT NULL CHECK(balance >= 0)',
                           'delivered BOOLEAN NOT NULL DEFAULT FALSE'):
            self.assertIn(constraint, sql)

    def test_schema_contains_no_auto_delivery(self):
        sql = '\n'.join(SCHEMA_STATEMENTS).lower()
        self.assertNotIn('http://', sql)
        self.assertNotIn('https://', sql)
        self.assertNotIn('dblink', sql)

    def test_explicit_dsn_required(self):
        for dsn in ('', None, 42):
            with self.subTest(dsn=dsn), self.assertRaises(ValueError):
                connect_postgres(dsn)

    def test_transaction_reference_is_not_a_security_gateway(self):
        # Two intentionally asserted owners. The reference should be called
        # only inside a trusted test harness, never through a real API.
        with tempfile.TemporaryDirectory() as temp:
            with AtomicWorldLedger(Path(temp) / 'world.sqlite') as ledger:
                ledger.seed_account('agent-a', 'alice', 100)
                ledger.seed_account('agent-b', 'bob', 10)
                intent = TransferIntent('i-a', 'agent-a', 'alice',
                                        'agent-b', 'bob', 25, 'sim',
                                        'nonce-a', 0, 4000)
                digest = ledger.prepare(intent)
                with self.assertRaises(TransactionDenied):
                    ledger.approve(intent_id='i-a', role='receiver',
                                   authenticated_owner='alice', expected_digest=digest)
                ledger.approve(intent_id='i-a', role='source',
                               authenticated_owner='alice', expected_digest=digest)
                ledger.approve(intent_id='i-a', role='receiver',
                               authenticated_owner='bob', expected_digest=digest)
                with self.assertRaises(RuntimeError):
                    ledger.execute(intent, now=1000, inject_failure=True)
                self.assertEqual(dict(ledger.db.execute(
                    'SELECT agent,balance FROM accounts')), {'agent-a': 100, 'agent-b': 10})
                receipt = ledger.execute(intent, now=1000)
                self.assertEqual(receipt, (0, 75, 35))
                self.assertEqual(ledger.execute(intent, now=3000), receipt)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 1)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0], 1)

    def test_sqlite_reference_rejects_mutated_intent(self):
        with tempfile.TemporaryDirectory() as temp:
            with AtomicWorldLedger(Path(temp) / 'world.sqlite') as ledger:
                intent = TransferIntent('i-a', 'a', 'alice', 'b', 'bob', 1,
                                        'study', 'nonce-a', 0, 5000)
                ledger.prepare(intent)
                changed = TransferIntent('i-a', 'a', 'alice', 'b', 'bob', 2,
                                         'study', 'nonce-a', 0, 5000)
                with self.assertRaises(TransactionDenied):
                    ledger.prepare(changed)


PG_DSN = os.environ.get('OPENWORLD_PG_TEST_DSN')
PG_PERMISSION = os.environ.get('OPENWORLD_PG_TEST_ISOLATED') == 'YES_EPHEMERAL_DB'


@unittest.skipUnless(PG_DSN and PG_PERMISSION,
                     'requires explicit isolated throwaway PostgreSQL DSN and opt-in')
class OptionalRealPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.ledger = PostgresWorldLedger.open(PG_DSN, initialize=True)
        except PostgresUnavailable as exc:
            raise unittest.SkipTest(str(exc)) from exc
        # This test must never mutate a reused database with other data.
        if cls.ledger.tick() != 0 or cls.ledger.balances():
            cls.ledger.close()
            raise RuntimeError('PostgreSQL pilot demands a fresh, empty dedicated database')

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'ledger'):
            cls.ledger.close()

    def test_atomic_rollback_and_exactly_once_receipt(self):
        db = self.ledger
        db.seed_account('agent-a', 'owner-a', 20)
        db.seed_account('agent-b', 'owner-b', 0)
        intent = TransferIntent('p1-test-1', 'agent-a', 'owner-a',
                                'agent-b', 'owner-b', 7, 'synthetic',
                                'p1-nonce-1', 0, 4000)
        h = db.prepare(intent)
        db.approve(intent_id=intent.intent_id, role='source',
                   authenticated_owner='owner-a', expected_digest=h)
        db.approve(intent_id=intent.intent_id, role='receiver',
                   authenticated_owner='owner-b', expected_digest=h)
        with self.assertRaises(RuntimeError):
            db.execute(intent, now=1000, inject_failure=True)
        self.assertEqual(db.balances(), {'agent-a': 20, 'agent-b': 0})
        first = db.execute(intent, now=1000)
        self.assertEqual(first, (0, 13, 7))
        self.assertEqual(db.execute(intent, now=2000), first)
        self.assertEqual(db.balances(), {'agent-a': 13, 'agent-b': 7})
        self.assertEqual(db.tick(), 1)


if __name__ == '__main__':
    unittest.main()