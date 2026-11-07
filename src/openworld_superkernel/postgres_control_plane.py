"""Optional PostgreSQL reference for the Issue #42 atomic-world research contract.

No default migration: PostgreSQL and psycopg are optional and explicitly
requested by an operator. This module does NOT authenticate the caller, consume
SEC-002 bearer capabilities, communicate over a network, or deliver the outbox.
"""
from __future__ import annotations

import json
from typing import Any

from .transactional_world import MAX_INT64, TransactionDenied, TransferIntent

# Fixed SQL identifiers; no user-controlled SQL identifier or formatted clauses.
# Each statement is individually executable by psycopg 3 in autocommit mode.
SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS ow_p1_meta (
        singleton SMALLINT PRIMARY KEY CHECK(singleton = 1),
        tick BIGINT NOT NULL CHECK(tick >= 0))""",
    "INSERT INTO ow_p1_meta(singleton,tick) VALUES (1,0) ON CONFLICT (singleton) DO NOTHING",
    """CREATE TABLE IF NOT EXISTS ow_p1_accounts (
        agent TEXT PRIMARY KEY, owner TEXT NOT NULL,
        balance BIGINT NOT NULL CHECK(balance >= 0))""",
    """CREATE TABLE IF NOT EXISTS ow_p1_intents (
        id TEXT PRIMARY KEY, body TEXT NOT NULL, digest CHAR(64) NOT NULL,
        nonce TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL CHECK(status IN ('prepared','executed')))""",
    """CREATE TABLE IF NOT EXISTS ow_p1_approvals (
        intent_id TEXT NOT NULL REFERENCES ow_p1_intents(id),
        role TEXT NOT NULL CHECK(role IN ('source','receiver')),
        owner TEXT NOT NULL, digest CHAR(64) NOT NULL,
        revoked BOOLEAN NOT NULL DEFAULT FALSE,
        PRIMARY KEY(intent_id,role))""",
    """CREATE TABLE IF NOT EXISTS ow_p1_receipts (
        intent_id TEXT PRIMARY KEY REFERENCES ow_p1_intents(id),
        digest CHAR(64) NOT NULL, tick BIGINT NOT NULL,
        source_balance BIGINT NOT NULL, target_balance BIGINT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS ow_p1_outbox (
        event_id TEXT PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL,
        delivered BOOLEAN NOT NULL DEFAULT FALSE)""",
)


class PostgresUnavailable(RuntimeError):
    """No PostgreSQL driver/service was provided; no simulated success."""


def connect_postgres(conninfo: str):
    """Explicit opt-in psycopg3 connection; no automatic local fallback."""
    if not isinstance(conninfo, str) or not conninfo:
        raise ValueError("explicit PostgreSQL DSN required")
    try:
        import psycopg
    except ImportError as exc:
        raise PostgresUnavailable("install psycopg 3 for PostgreSQL opt-in") from exc
    return psycopg.connect(conninfo, autocommit=True)


class PostgresWorldLedger:
    """P1 evaluation port: same simulated intent semantics as SQLite P0.

    A global tick row lock serializes execution. This is *deliberately* a
    correctness fixture, not a proven high-throughput multi-shard runtime.
    A connection using implicit transactions must be rejected: otherwise
    `conn.transaction()` could be only a SAVEPOINT and lose commit atomicity.
    """

    def __init__(self, connection: Any, *, initialize: bool = False):
        if getattr(connection, "autocommit", None) is not True:
            raise ValueError("a psycopg autocommit=True connection is required")
        if not callable(getattr(connection, "transaction", None)):
            raise TypeError("connection must provide transaction contexts")
        self.conn = connection
        if initialize:
            # Only an operator with schema privileges may initialize a new DB.
            # Do not call automatically at process startup with a production role.
            for statement in SCHEMA_STATEMENTS:
                self.conn.execute(statement)

    @classmethod
    def open(cls, conninfo: str, *, initialize: bool = False):
        connection = connect_postgres(conninfo)
        try:
            return cls(connection, initialize=initialize)
        except BaseException:
            connection.close()
            raise

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def balances(self) -> dict[str, int]:
        return dict(self.conn.execute(
            "SELECT agent,balance FROM ow_p1_accounts ORDER BY agent").fetchall())

    def tick(self) -> int:
        row = self.conn.execute(
            "SELECT tick FROM ow_p1_meta WHERE singleton=1").fetchone()
        if row is None:
            raise TransactionDenied("missing world metadata")
        return row[0]

    def seed_account(self, agent: str, owner: str, balance: int) -> None:
        """Operator-only simulation fixture, never a client-facing API."""
        if (not isinstance(agent, str) or not agent or not isinstance(owner, str)
                or not owner or type(balance) is not int
                or not 0 <= balance <= MAX_INT64):
            raise ValueError("invalid account")
        with self.conn.transaction():
            self.conn.execute(
                "INSERT INTO ow_p1_accounts(agent,owner,balance) VALUES (%s,%s,%s)",
                (agent, owner, balance),
            )

    def prepare(self, intent: TransferIntent) -> str:
        body, digest = intent.canonical(), intent.digest()
        with self.conn.transaction():
            existing = self.conn.execute(
                "SELECT body FROM ow_p1_intents WHERE id=%s FOR UPDATE",
                (intent.intent_id,),
            ).fetchone()
            if existing is not None:
                if existing[0] != body:
                    raise TransactionDenied("same intent ID, changed payload")
                return digest
            self.conn.execute(
                "INSERT INTO ow_p1_intents(id,body,digest,nonce,status) "
                "VALUES (%s,%s,%s,%s,'prepared')",
                (intent.intent_id, body, digest, intent.nonce),
            )
        return digest

    def approve(self, *, intent_id: str, role: str, authenticated_owner: str,
                expected_digest: str) -> None:
        """The authenticated owner is an ASSERTION from a trusted fixture."""
        if role not in ("source", "receiver"):
            raise ValueError("invalid role")
        with self.conn.transaction():
            row = self.conn.execute(
                "SELECT body,digest,status FROM ow_p1_intents WHERE id=%s FOR UPDATE",
                (intent_id,),
            ).fetchone()
            if row is None or row[1] != expected_digest or row[2] != "prepared":
                raise TransactionDenied("absent, changed or executed intent")
            intent = TransferIntent(**json.loads(row[0]))
            owner = intent.source_owner if role == "source" else intent.target_owner
            if authenticated_owner != owner:
                raise TransactionDenied("wrong independently approving owner")
            existing = self.conn.execute(
                "SELECT 1 FROM ow_p1_approvals WHERE intent_id=%s AND role=%s",
                (intent_id, role),
            ).fetchone()
            if existing:
                raise TransactionDenied("duplicate approval")
            self.conn.execute(
                "INSERT INTO ow_p1_approvals(intent_id,role,owner,digest) "
                "VALUES (%s,%s,%s,%s)", (intent_id, role, owner, expected_digest),
            )

    def revoke_consent(self, *, intent_id: str, role: str, authenticated_owner: str):
        if role not in ("source", "receiver"):
            raise ValueError("invalid role")
        with self.conn.transaction():
            row = self.conn.execute(
                "SELECT i.status,a.owner FROM ow_p1_intents i "
                "JOIN ow_p1_approvals a ON a.intent_id=i.id "
                "WHERE i.id=%s AND a.role=%s FOR UPDATE OF i, a",
                (intent_id, role),
            ).fetchone()
            if not row or row != ("prepared", authenticated_owner):
                raise TransactionDenied("not an active approval for that owner")
            self.conn.execute(
                "UPDATE ow_p1_approvals SET revoked=TRUE WHERE intent_id=%s AND role=%s",
                (intent_id, role),
            )

    def execute(self, intent: TransferIntent, *, now: int,
                inject_failure: bool = False) -> tuple[int, int, int]:
        body, digest = intent.canonical(), intent.digest()
        if type(now) is not int or now < 0:
            raise ValueError("invalid clock")
        with self.conn.transaction():
            # Lock the global tick even on retries. This P1 design favors
            # deterministic ordering, not maximum concurrent throughput.
            tick_row = self.conn.execute(
                "SELECT tick FROM ow_p1_meta WHERE singleton=1 FOR UPDATE"
            ).fetchone()
            if tick_row is None:
                raise TransactionDenied("missing world tick")
            tick = tick_row[0]
            row = self.conn.execute(
                "SELECT body,digest,status FROM ow_p1_intents WHERE id=%s FOR UPDATE",
                (intent.intent_id,),
            ).fetchone()
            if row is None or row[0] != body or row[1] != digest:
                raise TransactionDenied("missing or altered intent")
            receipt = self.conn.execute(
                "SELECT digest,tick,source_balance,target_balance FROM ow_p1_receipts "
                "WHERE intent_id=%s", (intent.intent_id,),
            ).fetchone()
            if row[2] == "executed":
                if receipt is None or receipt[0] != digest:
                    raise TransactionDenied("missing or mismatched receipt")
                return (receipt[1], receipt[2], receipt[3])
            if receipt is not None or now >= intent.expires_at or tick != intent.expected_tick:
                raise TransactionDenied("receipt conflict, expiry or stale world tick")
            approvals = self.conn.execute(
                "SELECT role,owner,digest,revoked FROM ow_p1_approvals "
                "WHERE intent_id=%s", (intent.intent_id,),
            ).fetchall()
            if len(approvals) != 2 or {r[0] for r in approvals} != {"source", "receiver"}:
                raise TransactionDenied("missing bilateral consent")
            for role, owner, stored_digest, revoked in approvals:
                expected_owner = (intent.source_owner if role == "source"
                                  else intent.target_owner)
                if revoked or owner != expected_owner or stored_digest != digest:
                    raise TransactionDenied("revoked or out-of-scope approval")
            # Lock rows in lexicographic agent order for predictable lock order.
            account_rows = self.conn.execute(
                "SELECT agent,owner,balance FROM ow_p1_accounts "
                "WHERE agent IN (%s,%s) ORDER BY agent FOR UPDATE",
                (intent.source_agent, intent.target_agent),
            ).fetchall()
            accounts = {agent: (owner, balance) for agent, owner, balance in account_rows}
            source, target = accounts.get(intent.source_agent), accounts.get(intent.target_agent)
            if (source is None or target is None or source[0] != intent.source_owner
                    or target[0] != intent.target_owner or source[1] < intent.amount):
                raise TransactionDenied("ownership changed or insufficient balance")
            source_new, target_new = source[1] - intent.amount, target[1] + intent.amount
            if target_new > MAX_INT64:
                raise TransactionDenied("target balance overflow")
            self.conn.execute(
                "UPDATE ow_p1_accounts SET balance=%s WHERE agent=%s",
                (source_new, intent.source_agent),
            )
            if inject_failure:
                raise RuntimeError("synthetic failure after debit before commit")
            self.conn.execute(
                "UPDATE ow_p1_accounts SET balance=%s WHERE agent=%s",
                (target_new, intent.target_agent),
            )
            self.conn.execute(
                "INSERT INTO ow_p1_receipts(intent_id,digest,tick,source_balance,target_balance) "
                "VALUES (%s,%s,%s,%s,%s)",
                (intent.intent_id, digest, tick, source_new, target_new),
            )
            self.conn.execute(
                "INSERT INTO ow_p1_outbox(event_id,kind,body,delivered) "
                "VALUES (%s,'simulated.transfer',%s,FALSE)",
                (intent.intent_id, body),
            )
            self.conn.execute(
                "UPDATE ow_p1_intents SET status='executed' WHERE id=%s",
                (intent.intent_id,),
            )
            self.conn.execute("UPDATE ow_p1_meta SET tick=tick+1 WHERE singleton=1")
            return (tick, source_new, target_new)