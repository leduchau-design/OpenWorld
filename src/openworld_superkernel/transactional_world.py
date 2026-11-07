"""Issue #42: local single-database atomic world/consent experiment.

Research only. Principals are asserted by test harness, NOT authenticated. No
real transfers, external tool calls or cross-owner W3 gateway enablement.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


MAX_INT64 = 2**63 - 1


class TransactionDenied(PermissionError):
    """Operation is unauthorized, stale, altered or already invalidated."""


@dataclass(frozen=True)
class TransferIntent:
    intent_id: str
    source_agent: str
    source_owner: str
    target_agent: str
    target_owner: str
    amount: int
    purpose: str
    nonce: str
    expected_tick: int
    expires_at: int

    def canonical(self) -> str:
        if any(not isinstance(x, str) or not x or len(x) > 256 for x in
               (self.intent_id, self.source_agent, self.source_owner,
                self.target_agent, self.target_owner, self.purpose, self.nonce)):
            raise ValueError('invalid identity, purpose or nonce')
        if (self.source_agent == self.target_agent
                or self.source_owner == self.target_owner
                or type(self.amount) is not int or not 1 <= self.amount <= MAX_INT64
                or type(self.expected_tick) is not int or self.expected_tick < 0
                or type(self.expires_at) is not int or self.expires_at < 1):
            raise ValueError('invalid cross-owner transfer intent')
        return json.dumps(vars(self), sort_keys=True, separators=(',', ':'),
                          ensure_ascii=True, allow_nan=False)

    def digest(self) -> str:
        return hashlib.sha256(self.canonical().encode('ascii')).hexdigest()


class AtomicWorldLedger:
    """One-file SQLite transaction proof; NOT integrated with SEC-002 tokens.

    The caller MUST independently authenticate both owner assertions. This
    reference intentionally exposes no network interface and cannot execute
    effects outside this database transaction.
    """

    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=15)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS world_meta (singleton INTEGER PRIMARY KEY,
            tick INTEGER NOT NULL CHECK(tick >= 0));
        INSERT OR IGNORE INTO world_meta VALUES(1, 0);
        CREATE TABLE IF NOT EXISTS accounts (agent TEXT PRIMARY KEY, owner TEXT NOT NULL,
            balance INTEGER NOT NULL CHECK(balance >= 0));
        CREATE TABLE IF NOT EXISTS intents (id TEXT PRIMARY KEY, body TEXT NOT NULL,
            digest TEXT NOT NULL, nonce TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL CHECK(status IN ('prepared','executed')));
        CREATE TABLE IF NOT EXISTS approvals (intent_id TEXT NOT NULL REFERENCES intents(id),
            role TEXT NOT NULL CHECK(role IN ('source','receiver')),
            owner TEXT NOT NULL, digest TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(intent_id,role));
        CREATE TABLE IF NOT EXISTS receipts (intent_id TEXT PRIMARY KEY REFERENCES intents(id),
            digest TEXT NOT NULL, tick INTEGER NOT NULL,
            source_balance INTEGER NOT NULL, target_balance INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS outbox (event_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL, body TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0);
        ''')

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def seed_account(self, agent: str, owner: str, balance: int):
        """Trusted fixture provisioning only; never expose to untrusted users."""
        if not agent or not owner or type(balance) is not int or not 0 <= balance <= MAX_INT64:
            raise ValueError('invalid account')
        self.db.execute('INSERT INTO accounts VALUES(?,?,?)', (agent, owner, balance))

    def prepare(self, intent: TransferIntent) -> str:
        body, digest = intent.canonical(), intent.digest()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            existing = self.db.execute('SELECT body,status FROM intents WHERE id=?',
                                       (intent.intent_id,)).fetchone()
            if existing is not None:
                if existing[0] != body:
                    raise TransactionDenied('same intent ID, changed payload')
                self.db.execute('COMMIT')
                return digest
            self.db.execute('INSERT INTO intents VALUES(?,?,?,?,?)',
                            (intent.intent_id, body, digest, intent.nonce, 'prepared'))
            self.db.execute('COMMIT')
            return digest
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def approve(self, *, intent_id: str, role: str, authenticated_owner: str,
                expected_digest: str) -> None:
        """Only a trusted caller may supply authenticated_owner in this fixture."""
        if role not in ('source', 'receiver'):
            raise ValueError('invalid role')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT body,digest,status FROM intents WHERE id=?',
                                  (intent_id,)).fetchone()
            if row is None or row[2] != 'prepared' or row[1] != expected_digest:
                raise TransactionDenied('absent, executed or changed intent')
            original = TransferIntent(**json.loads(row[0]))
            correct = original.source_owner if role == 'source' else original.target_owner
            if authenticated_owner != correct:
                raise TransactionDenied('wrong independent approving owner')
            if self.db.execute('SELECT 1 FROM approvals WHERE intent_id=? AND role=?',
                               (intent_id, role)).fetchone():
                raise TransactionDenied('approval cannot be overwritten')
            self.db.execute('INSERT INTO approvals(intent_id,role,owner,digest) '
                            'VALUES(?,?,?,?)', (intent_id, role, correct, expected_digest))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def revoke_consent(self, *, intent_id: str, role: str, authenticated_owner: str):
        if role not in ('source', 'receiver'):
            raise ValueError('invalid role')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            match = self.db.execute('SELECT a.owner,i.status FROM approvals a '
                                    'JOIN intents i ON i.id=a.intent_id '
                                    'WHERE a.intent_id=? AND a.role=?',
                                    (intent_id, role)).fetchone()
            if not match or match != (authenticated_owner, 'prepared'):
                raise TransactionDenied('no active owner consent to revoke')
            self.db.execute('UPDATE approvals SET revoked=1 WHERE intent_id=? AND role=?',
                            (intent_id, role))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def execute(self, intent: TransferIntent, *, now: int,
                inject_failure: bool = False) -> tuple[int, int, int]:
        """Atomically consume both approvals, modify balances and emit receipt.

        No SEC-002 grant consumption occurs here: this remains a synthetic
        ownership/consent reference, NOT an integrated authorization gateway.
        """
        body, digest = intent.canonical(), intent.digest()
        if type(now) is not int or now < 0:
            raise ValueError('invalid now')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT body,digest,status FROM intents WHERE id=?',
                                  (intent.intent_id,)).fetchone()
            if row is None or row[0] != body or row[1] != digest:
                raise TransactionDenied('missing or changed intent')
            receipt = self.db.execute('SELECT digest,tick,source_balance,target_balance '
                                      'FROM receipts WHERE intent_id=?',
                                      (intent.intent_id,)).fetchone()
            if row[2] == 'executed':
                if receipt is None or receipt[0] != digest:
                    raise TransactionDenied('corrupted execution receipt')
                self.db.execute('COMMIT')
                return (receipt[1], receipt[2], receipt[3])
            tick = self.db.execute('SELECT tick FROM world_meta WHERE singleton=1').fetchone()[0]
            if now >= intent.expires_at or tick != intent.expected_tick:
                raise TransactionDenied('expired or stale world tick')
            grants = self.db.execute('SELECT role,owner,digest,revoked FROM approvals '
                                     'WHERE intent_id=?', (intent.intent_id,)).fetchall()
            if (len(grants) != 2 or
                    {r[0] for r in grants} != {'source', 'receiver'} or
                    any(r[3] or r[2] != digest or r[1] !=
                        (intent.source_owner if r[0] == 'source' else intent.target_owner)
                        for r in grants)):
                raise TransactionDenied('missing or invalid bilateral consent')
            source = self.db.execute('SELECT owner,balance FROM accounts WHERE agent=?',
                                     (intent.source_agent,)).fetchone()
            target = self.db.execute('SELECT owner,balance FROM accounts WHERE agent=?',
                                     (intent.target_agent,)).fetchone()
            if (source is None or target is None or source[0] != intent.source_owner
                    or target[0] != intent.target_owner or source[1] < intent.amount):
                raise TransactionDenied('ownership changed or insufficient balance')
            source_new, target_new = source[1] - intent.amount, target[1] + intent.amount
            if target_new > MAX_INT64:
                raise TransactionDenied('target balance would overflow SQLite integer')
            self.db.execute('UPDATE accounts SET balance=? WHERE agent=?',
                            (source_new, intent.source_agent))
            if inject_failure:
                raise RuntimeError('synthetic crash inside local transaction')
            self.db.execute('UPDATE accounts SET balance=? WHERE agent=?',
                            (target_new, intent.target_agent))
            self.db.execute('INSERT INTO receipts VALUES(?,?,?,?,?)',
                            (intent.intent_id, digest, tick, source_new, target_new))
            self.db.execute('INSERT INTO outbox VALUES(?,?,?,0)',
                            (intent.intent_id, 'simulated.transfer', body))
            self.db.execute('UPDATE intents SET status=? WHERE id=?',
                            ('executed', intent.intent_id))
            self.db.execute('UPDATE world_meta SET tick=tick+1 WHERE singleton=1')
            self.db.execute('COMMIT')
            return (tick, source_new, target_new)
        except BaseException:
            self.db.execute('ROLLBACK')
            raise
