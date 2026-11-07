"""HM-P1e experimental, cost-aware Bernoulli memory with an exact evidence lane.

Only synthetic/research workloads are supported. No API, LLM, or user data.
The SQLite transaction boundary is local to one database, not distributed.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .memory_contracts import MemoryEvent, MemoryRoute, Provenance, route_memory_event


class StaleRetryError(ValueError):
    """A retry predates the most recent retained idempotency receipt."""


class ConflictingRetryError(ValueError):
    """The same sequence number was supplied with different content."""


class EvidenceIntegrityError(ValueError):
    """An exact ledger record's payload digest does not match."""


class LegacyNamespaceMigrationRequired(RuntimeError):
    """The legacy globally-unique ledger needs an operator-approved migration."""


class UnexpectedExactEventSchema(RuntimeError):
    """Refuse to rebuild an unknown or dependent exact-event schema."""


_EVENT_COLUMNS = ("owner_id", "agent_id", "seq", "event_id",
                  "provenance", "event_type", "payload", "payload_hash")
_EVENT_COLUMNS_SQL = ",".join(_EVENT_COLUMNS)


@dataclass(frozen=True, slots=True)
class Observation:
    event: MemoryEvent
    agent_id: str
    sequence_number: int
    outcome: int

    def __post_init__(self) -> None:
        if not self.agent_id:
            raise ValueError("agent_id required")
        if type(self.sequence_number) is not int or self.sequence_number < 1:
            raise ValueError("sequence_number must be a positive integer")
        if type(self.outcome) is not int or self.outcome not in (0, 1):
            raise ValueError("outcome must be 0 or 1")
        if self.event.provenance == Provenance.UNAVAILABLE:
            raise ValueError("unavailable evidence cannot train a predictor")


def _initial_state() -> dict:
    return {
        "seq": 0, "receipt": "",
        "n": 0, "successes": 0,
        "fast_s": 0.0, "fast_w": 0.0,
        "slow_s": 0.0, "slow_w": 0.0,
        "loss_static": 0.25, "loss_fast": 0.25, "loss_slow": 0.25,
        "selected": "static",
    }


def _probabilities(s: dict) -> dict[str, float]:
    return {
        "static": (s["successes"] + 1.0) / (s["n"] + 2.0),
        "fast": (s["fast_s"] + 1.0) / (s["fast_w"] + 2.0),
        "slow": (s["slow_s"] + 1.0) / (s["slow_w"] + 2.0),
    }


def _choose(s: dict, penalty: float) -> str:
    if s["n"] < 8:
        return "static"
    best = min(("fast", "slow"), key=lambda n: (s["loss_" + n], n))
    if s["loss_static"] - s["loss_" + best] > penalty:
        return best
    return "static"


def _receipt(item: Observation) -> str:
    e = item.event
    body = (
        e.event_id, e.owner_id, item.agent_id, e.event_type, e.provenance.value,
        e.payload.hex(), e.reconstructable, e.protected,
        item.sequence_number, item.outcome,
    )
    return hashlib.sha256(
        json.dumps(body, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()


class HyperMemoryP1e:
    """Experimental SQLite memory: bounded adaptive state and exact events.

    Only the latest receipt is retained per agent. Older retries are rejected;
    they are never reported as successful. SQLite supplies local atomicity.
    """

    def __init__(self, path: str | Path, *, gate_penalty: float = 0.007,
                 migrate_legacy: bool = False,
                 legacy_backup_path: str | Path | None = None):
        """Open the store; never silently rewrite a pre-existing exact ledger.

        Legacy migration is an explicit, operator-reviewed maintenance step:
        migrate_legacy=True AND a new, externally retained backup path. It is
        not an on-demand migration service or a production deployment process.
        """
        if not (0.0 <= gate_penalty <= 1.0):
            raise ValueError("gate_penalty out of range")
        if type(migrate_legacy) is not bool:
            raise TypeError("migrate_legacy must be bool")
        if not migrate_legacy and legacy_backup_path is not None:
            raise ValueError("backup path is only valid for an approved migration")
        self.gate_penalty = gate_penalty
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=15)
        try:
            # Check pre-existing databases BEFORE changing journal mode or
            # creating tables. An unapproved legacy open must leave the
            # original file untouched, including SQLite schema and journal.
            existed = self.db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='exact_events'").fetchone() is not None
            if existed:
                self._verify_or_migrate_namespace(
                    source_path=path, migrate_legacy=migrate_legacy,
                    legacy_backup_path=legacy_backup_path,
                )
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_state (
                    owner_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    PRIMARY KEY (owner_id, agent_id)
                );
                CREATE TABLE IF NOT EXISTS exact_events (
                    owner_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload BLOB NOT NULL,
                    payload_hash TEXT NOT NULL,
                    PRIMARY KEY (owner_id, agent_id, seq),
                    UNIQUE (owner_id, event_id)
                );
                """
            )
            if not existed:
                self._verify_or_migrate_namespace(
                    source_path=path, migrate_legacy=migrate_legacy,
                    legacy_backup_path=legacy_backup_path,
                )
        except BaseException:
            self.db.close()
            raise

    def _event_indexes(self) -> set[tuple[str, ...]]:
        indexes = set()
        for _seq, name, unique, origin, partial in self.db.execute(
                "PRAGMA index_list('exact_events')"):
            if not unique or partial:
                continue
            escaped = name.replace('"', '""')
            columns = tuple(row[2] for row in self.db.execute(
                f'PRAGMA index_info("{escaped}")'))
            indexes.add(columns)
        return indexes

    def _event_fingerprint(self, table: str, *, db: sqlite3.Connection | None = None) -> tuple[int, str]:
        """Count and full-row digest, using constant memory; compare BEFORE commit."""
        if table not in ("exact_events", "exact_events_namespace_v2"):
            raise ValueError("unknown migration table")
        sha = hashlib.sha256()
        count = 0
        source_db = self.db if db is None else db
        for row in source_db.execute(
                f"SELECT {_EVENT_COLUMNS_SQL} FROM {table} "
                "ORDER BY owner_id,agent_id,seq"):
            if not isinstance(row[6], bytes):
                raise EvidenceIntegrityError("legacy exact payload must be bytes")
            if hashlib.sha256(row[6]).hexdigest() != row[7]:
                raise EvidenceIntegrityError("legacy payload digest mismatch")
            packed = json.dumps(
                (*row[:6], row[6].hex(), row[7]), ensure_ascii=True,
                separators=(",", ":"), allow_nan=False,
            ).encode("ascii")
            sha.update(len(packed).to_bytes(8, "big"))
            sha.update(packed)
            count += 1
        return count, sha.hexdigest()

    def _assert_migration_schema_safe(self) -> None:
        columns = tuple(row[1] for row in self.db.execute(
            "PRAGMA table_info('exact_events')"))
        indexes = self._event_indexes()
        if (columns != _EVENT_COLUMNS or indexes != {
                ("event_id",), ("owner_id", "agent_id", "seq")}):
            raise UnexpectedExactEventSchema(
                "unexpected legacy columns or unique constraints")
        for name, sql in self.db.execute(
                "SELECT name,sql FROM sqlite_master WHERE type='index' "
                "AND tbl_name='exact_events'"):
            if sql is not None or not name.startswith("sqlite_autoindex_exact_events_"):
                raise UnexpectedExactEventSchema("custom indexes require manual migration")
        for (name,) in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' "
                "AND tbl_name='exact_events'"):
            raise UnexpectedExactEventSchema(
                f"custom trigger {name} requires manual migration")
        for name, sql in self.db.execute(
                "SELECT name,sql FROM sqlite_master WHERE type='view'"):
            if "exact_events" in (sql or "").lower():
                raise UnexpectedExactEventSchema(
                    f"dependent view {name} requires manual migration")
        for (name,) in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"):
            escaped = name.replace('"', '""')
            for key in self.db.execute(f'PRAGMA foreign_key_list("{escaped}")'):
                if key[2] == "exact_events":
                    raise UnexpectedExactEventSchema(
                        f"dependent foreign key in {name} requires manual migration")
        if self.db.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE name='exact_events_namespace_v2'").fetchone():
            raise UnexpectedExactEventSchema("staging table already exists")

    def _verify_or_migrate_namespace(
            self, *, source_path: str | Path, migrate_legacy: bool,
            legacy_backup_path: str | Path | None) -> None:
        indexes = self._event_indexes()
        scoped = ("owner_id", "event_id") in indexes
        global_unique = ("event_id",) in indexes
        if scoped and not global_unique:
            return
        if not global_unique or scoped:
            raise UnexpectedExactEventSchema(
                "unknown event uniqueness rules; manual schema review required")
        if not migrate_legacy or legacy_backup_path is None:
            raise LegacyNamespaceMigrationRequired(
                "legacy global event_id UNIQUE: stop; reopen with migrate_legacy=True "
                "and a new legacy_backup_path after operator review")
        if str(source_path) == ":memory:":
            raise ValueError("legacy migration requires a durable source file")
        self._assert_migration_schema_safe()
        if self.db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise EvidenceIntegrityError("source SQLite integrity_check failed")
        before = self._event_fingerprint("exact_events")

        # Backup must precede *any* destructive schema change; never overwrite.
        backup = Path(legacy_backup_path)
        source = Path(source_path)
        if source.resolve() == backup.resolve():
            raise ValueError("backup cannot overwrite source")
        backup.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(backup), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            with sqlite3.connect(str(backup)) as target:
                self.db.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise EvidenceIntegrityError("backup SQLite integrity_check failed")
                if self._event_fingerprint("exact_events", db=target) != before:
                    raise EvidenceIntegrityError("backup exact ledger differs")
        except BaseException:
            backup.unlink(missing_ok=True)
            raise

        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                "CREATE TABLE exact_events_namespace_v2 ("
                "owner_id TEXT NOT NULL, agent_id TEXT NOT NULL, seq INTEGER NOT NULL, "
                "event_id TEXT NOT NULL, provenance TEXT NOT NULL, "
                "event_type TEXT NOT NULL, payload BLOB NOT NULL, "
                "payload_hash TEXT NOT NULL, "
                "PRIMARY KEY (owner_id, agent_id, seq), UNIQUE (owner_id, event_id))")
            self.db.execute(
                "INSERT INTO exact_events_namespace_v2 "
                f"({_EVENT_COLUMNS_SQL}) SELECT {_EVENT_COLUMNS_SQL} "
                "FROM exact_events")
            if self._event_fingerprint("exact_events_namespace_v2") != before:
                raise EvidenceIntegrityError("exact ledger row fingerprint differs")
            self.db.execute("DROP TABLE exact_events")
            self.db.execute(
                "ALTER TABLE exact_events_namespace_v2 RENAME TO exact_events")
            if self._event_indexes() != {
                    ("owner_id", "agent_id", "seq"), ("owner_id", "event_id")}:
                raise UnexpectedExactEventSchema("new namespace indexes invalid")
            if self.db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise EvidenceIntegrityError("migrated SQLite integrity_check failed")
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            # Keep external backup as evidence and recovery path.
            raise

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "HyperMemoryP1e":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def get_state(self, *, owner_id: str, agent_id: str,
                  requester_owner_id: str) -> dict:
        if owner_id != requester_owner_id:
            raise PermissionError("cross-owner state access denied")
        row = self.db.execute(
            "SELECT state_json FROM agent_state WHERE owner_id=? AND agent_id=?",
            (owner_id, agent_id),
        ).fetchone()
        return json.loads(row[0]) if row else _initial_state()

    def predict(self, *, owner_id: str, agent_id: str,
                requester_owner_id: str) -> tuple[float, str]:
        s = self.get_state(owner_id=owner_id, agent_id=agent_id,
                           requester_owner_id=requester_owner_id)
        selected = _choose(s, self.gate_penalty)
        return _probabilities(s)[selected], selected

    def exact_event(self, event_id: str, *, requester_owner_id: str) -> bytes | None:
        """Return only the requester's event; foreign and absent IDs both give None.

        The trusted host remains responsible for *authenticating* the requester.
        A caller-controlled owner string is NOT an authorization capability.
        """
        if not isinstance(requester_owner_id, str) or not requester_owner_id:
            raise ValueError("requester_owner_id required")
        row = self.db.execute(
            "SELECT payload,payload_hash FROM exact_events "
            "WHERE owner_id=? AND event_id=?",
            (requester_owner_id, event_id),
        ).fetchone()
        if row is None:
            return None
        data = bytes(row[0])
        if hashlib.sha256(data).hexdigest() != row[1]:
            raise EvidenceIntegrityError("exact event payload corrupted")
        return data

    def apply_batch(self, items: Iterable[Observation], *,
                    requester_owner_id: str,
                    inject_failure: bool = False) -> int:
        """Apply all updates atomically. No partial state or ledger commit."""
        events = list(items)
        if not requester_owner_id:
            raise ValueError("requester identity required")
        for item in events:
            if item.event.owner_id != requester_owner_id:
                raise PermissionError("cross-owner mutation denied")

        applied = 0
        self.db.execute("BEGIN IMMEDIATE")
        try:
            for item in events:
                e = item.event
                row = self.db.execute(
                    "SELECT state_json FROM agent_state WHERE owner_id=? AND agent_id=?",
                    (e.owner_id, item.agent_id),
                ).fetchone()
                s = json.loads(row[0]) if row else _initial_state()
                digest = _receipt(item)
                if item.sequence_number == s["seq"]:
                    if digest != s["receipt"]:
                        raise ConflictingRetryError("latest sequence has different content")
                    continue
                if item.sequence_number <= s["seq"]:
                    raise StaleRetryError("older receipt not retained")
                if item.sequence_number != s["seq"] + 1:
                    raise ValueError("out-of-order update")
                prior = _probabilities(s)
                self._before_observation(item, prior, s)
                value = item.outcome
                for name, p in prior.items():
                    key = "loss_" + name
                    s[key] = 0.92 * s[key] + 0.08 * (p - value) ** 2
                s["n"] += 1
                s["successes"] += value
                s["fast_s"] = 0.65 * s["fast_s"] + value
                s["fast_w"] = 0.65 * s["fast_w"] + 1.0
                s["slow_s"] = 0.96 * s["slow_s"] + value
                s["slow_w"] = 0.96 * s["slow_w"] + 1.0
                s["seq"] = item.sequence_number
                s["receipt"] = digest
                s["selected"] = _choose(s, self.gate_penalty)
                aid = item.agent_id
                self.db.execute(
                    "INSERT INTO agent_state(owner_id,agent_id,state_json) VALUES(?,?,?) "
                    "ON CONFLICT(owner_id,agent_id) DO UPDATE SET state_json=excluded.state_json",
                    (e.owner_id, aid, json.dumps(s, separators=(",", ":"))),
                )
                if route_memory_event(e) == MemoryRoute.EXACT:
                    self.db.execute(
                        "INSERT INTO exact_events(owner_id,agent_id,seq,event_id,provenance,"
                        "event_type,payload,payload_hash) VALUES(?,?,?,?,?,?,?,?)",
                        (e.owner_id, aid, item.sequence_number, e.event_id,
                         e.provenance.value, e.event_type, e.payload,
                         hashlib.sha256(e.payload).hexdigest()),
                    )
                applied += 1
                if inject_failure:
                    raise RuntimeError("injected failure before commit")
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return applied

    def _before_observation(self, item: Observation, prior: dict[str, float],
                            previous_state: dict) -> None:
        """Optional in-transaction estimator hook, before seeing the outcome.

        Implementations must not carry external side effects: an exception rolls
        back the predictive state and exact ledger together.
        """
        return None

    def checkpoint(self) -> tuple[int, int, int]:
        """WAL checkpoint; busy readers can prevent truncation."""
        return tuple(self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
