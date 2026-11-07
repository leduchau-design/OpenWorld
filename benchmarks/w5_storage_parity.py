"""W5: deterministic *synthetic* SQLite/PostgreSQL transaction parity experiment.

SQLite is mandatory; PostgreSQL is a strictly opt-in, disposable database.
Neither ledger authenticates the claimed owner. No W3 cross-owner execution.

    python benchmarks/w5_storage_parity.py
    OPENWORLD_PG_TEST_ISOLATED=YES_EPHEMERAL_DB \
    OPENWORLD_PG_TEST_DSN='...' python benchmarks/w5_storage_parity.py --with-postgres
"""
from __future__ import annotations

import argparse
import concurrent.futures
import threading
import json
import os
import platform
import sqlite3
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from openworld_superkernel.transactional_world import (  # noqa: E402
    AtomicWorldLedger, TransactionDenied, TransferIntent,
)


@dataclass(frozen=True)
class TraceSummary:
    outcomes: tuple[tuple[str, str], ...]
    balances: tuple[tuple[str, int], ...]
    tick: int
    receipts: int
    outbox: int
    total_units: int
    latency_ms: tuple[float, ...]

    def logical(self) -> dict[str, Any]:
        """Return exact, platform-independent result (no time noise)."""
        return {"outcomes": dict(self.outcomes), "balances": dict(self.balances),
                "tick": self.tick, "receipts": self.receipts,
                "outbox": self.outbox, "total_units": self.total_units}


def percentile(xs: tuple[float, ...], q: float) -> float:
    """Nearest-rank percentile. Small-n estimates are not capacity evidence."""
    if not xs or not 0 <= q <= 1:
        raise ValueError("nonempty data and quantile in [0,1] required")
    ordered = sorted(xs)
    return ordered[max(0, min(len(xs) - 1, int(q * len(xs) + 0.999999999) - 1))]


def _intent(identifier: int, src: str, owner_a: str, dst: str, owner_b: str,
            amount: int, tick: int) -> TransferIntent:
    return TransferIntent(
        intent_id=f"parity-intent-{identifier}", source_agent=src,
        source_owner=owner_a, target_agent=dst, target_owner=owner_b,
        amount=amount, purpose="synthetic-storage-parity",
        nonce=f"parity-nonce-{identifier}", expected_tick=tick, expires_at=2000,
    )


def _snapshot(ledger: Any) -> tuple[tuple[tuple[str, int], ...], int, int, int]:
    """Read authoritative domain state; never rely on raw timing to compare correctness."""
    if hasattr(ledger, "conn"):  # PostgresWorldLedger
        balances = tuple(sorted(ledger.balances().items()))
        tick = ledger.tick()
        receipts = ledger.conn.execute("SELECT count(*) FROM ow_p1_receipts").fetchone()[0]
        outbox = ledger.conn.execute("SELECT count(*) FROM ow_p1_outbox").fetchone()[0]
    else:  # AtomicWorldLedger
        db = ledger.db
        balances = tuple(sorted(db.execute("SELECT agent,balance FROM accounts").fetchall()))
        tick = db.execute("SELECT tick FROM world_meta WHERE singleton=1").fetchone()[0]
        receipts = db.execute("SELECT count(*) FROM receipts").fetchone()[0]
        outbox = db.execute("SELECT count(*) FROM outbox").fetchone()[0]
    return balances, tick, receipts, outbox


def run_trace(ledger: Any) -> TraceSummary:
    """Identical ordered control-plane calls and negatives for both storage ports.

    Requires a *fresh empty test ledger*. Zero real identities and no external actions.
    Any unexpected success, exception, or domain divergence aborts the experiment.
    """
    if _snapshot(ledger) != ((), 0, 0, 0):
        raise RuntimeError("parity experiment requires a fresh empty ledger")
    if hasattr(ledger, "conn"):
        count = ledger.conn.execute(
            "SELECT (SELECT count(*) FROM ow_p1_intents) + "
            "(SELECT count(*) FROM ow_p1_approvals)"
        ).fetchone()[0]
    else:
        count = ledger.db.execute(
            "SELECT (SELECT count(*) FROM intents) + "
            "(SELECT count(*) FROM approvals)"
        ).fetchone()[0]
    if count:
        raise RuntimeError("parity experiment refuses pre-existing intents or approvals")

    steps: list[tuple[str, str]] = []
    latencies: list[float] = []

    def perform(label: str, function: Callable[[], Any], expected: str = "ok") -> Any:
        start = time.perf_counter_ns()
        try:
            result = function()
        except TransactionDenied:
            observed, result = "denied", None
        except RuntimeError as exc:
            # Fault injection uses a deliberately recognizable exception message.
            if str(exc) not in {"synthetic crash inside local transaction",
                                "synthetic failure after debit before commit"}:
                raise
            observed, result = "rolled_back", None
        finally:
            latencies.append((time.perf_counter_ns() - start) / 1_000_000)
        if "observed" not in locals():
            observed = "ok"
        if observed != expected:
            raise AssertionError(f"{label}: expected {expected}; got {observed}")
        steps.append((label, observed))
        return result

    for agent, owner, quantity in (("agent-a", "owner-a", 100),
                                   ("agent-b", "owner-b", 10),
                                   ("agent-c", "owner-c", 20)):
        perform(f"seed:{agent}", lambda a=agent, o=owner, q=quantity:
                ledger.seed_account(a, o, q))

    first = _intent(1, "agent-a", "owner-a", "agent-b", "owner-b", 7, 0)
    perform("prepare:first", lambda: ledger.prepare(first))
    perform("approve:source", lambda: ledger.approve(
        intent_id=first.intent_id, role="source", authenticated_owner="owner-a",
        expected_digest=first.digest()))
    perform("deny:receiver_missing", lambda: ledger.execute(first, now=1000), "denied")
    perform("deny:wrong_receiver", lambda: ledger.approve(
        intent_id=first.intent_id, role="receiver", authenticated_owner="owner-a",
        expected_digest=first.digest()), "denied")
    perform("approve:receiver", lambda: ledger.approve(
        intent_id=first.intent_id, role="receiver", authenticated_owner="owner-b",
        expected_digest=first.digest()))
    perform("fault:after_debit", lambda: ledger.execute(first, now=1000,
                                                         inject_failure=True), "rolled_back")
    if _snapshot(ledger) != ((("agent-a", 100), ("agent-b", 10),
                              ("agent-c", 20)), 0, 0, 0):
        raise AssertionError("mid-transfer failure leaked a partial write")
    receipt_1 = perform("execute:first", lambda: ledger.execute(first, now=1000))
    if receipt_1 != (0, 93, 17):
        raise AssertionError("first transfer was incorrectly applied")
    if perform("replay:first", lambda: ledger.execute(first, now=1500)) != receipt_1:
        raise AssertionError("same-intent replay did not return the original receipt")
    changed = _intent(1, "agent-a", "owner-a", "agent-b", "owner-b", 8, 0)
    perform("deny:changed_payload", lambda: ledger.prepare(changed), "denied")

    revoked = _intent(2, "agent-b", "owner-b", "agent-c", "owner-c", 5, 1)
    perform("prepare:revoked", lambda: ledger.prepare(revoked))
    for role, owner in (("source", "owner-b"), ("receiver", "owner-c")):
        perform(f"approve:revoked:{role}", lambda r=role, o=owner: ledger.approve(
            intent_id=revoked.intent_id, role=r, authenticated_owner=o,
            expected_digest=revoked.digest()))
    perform("revoke:receiver", lambda: ledger.revoke_consent(
        intent_id=revoked.intent_id, role="receiver", authenticated_owner="owner-c"))
    perform("deny:revoked", lambda: ledger.execute(revoked, now=1000), "denied")

    second = _intent(3, "agent-a", "owner-a", "agent-c", "owner-c", 2, 1)
    perform("prepare:second", lambda: ledger.prepare(second))
    for role, owner in (("source", "owner-a"), ("receiver", "owner-c")):
        perform(f"approve:second:{role}", lambda r=role, o=owner: ledger.approve(
            intent_id=second.intent_id, role=r, authenticated_owner=o,
            expected_digest=second.digest()))
    receipt_2 = perform("execute:second", lambda: ledger.execute(second, now=1000))
    if receipt_2 != (1, 91, 22):
        raise AssertionError("second transfer was incorrectly applied")
    if perform("replay:second", lambda: ledger.execute(second, now=1500)) != receipt_2:
        raise AssertionError("second retry changed its durable receipt")

    stale = _intent(4, "agent-a", "owner-a", "agent-b", "owner-b", 1, 1)
    perform("prepare:stale", lambda: ledger.prepare(stale))
    for role, owner in (("source", "owner-a"), ("receiver", "owner-b")):
        perform(f"approve:stale:{role}", lambda r=role, o=owner: ledger.approve(
            intent_id=stale.intent_id, role=r, authenticated_owner=o,
            expected_digest=stale.digest()))
    perform("deny:stale_tick", lambda: ledger.execute(stale, now=1000), "denied")

    balances, tick, receipts, outbox = _snapshot(ledger)
    result = TraceSummary(tuple(steps), balances, tick, receipts, outbox,
                          sum(v for _, v in balances), tuple(latencies))
    if result.logical()["balances"] != {"agent-a": 91, "agent-b": 17, "agent-c": 22}:
        raise AssertionError("unexpected final balances")
    if (tick, receipts, outbox, result.total_units) != (2, 2, 2, 130):
        raise AssertionError("tick/receipt/outbox or conserved quantity mismatch")
    return result


def run_contention(ledger: Any, connection_factory: Callable[[], Any]) -> dict[str, int | float]:
    """Two independently connected writers race against one world tick.

    Exactly one may commit; the other must fail closed. Which writer wins is
    scheduler-dependent, so never compare winners across database products.
    """
    balances, tick, receipts, outbox = _snapshot(ledger)
    if tick != 2 or receipts != 2 or outbox != 2:
        raise RuntimeError("contention fixture must follow the completed trace")
    racers = (
        _intent(5, "agent-a", "owner-a", "agent-b", "owner-b", 3, tick),
        _intent(6, "agent-a", "owner-a", "agent-c", "owner-c", 4, tick),
    )
    for intent in racers:
        ledger.prepare(intent)
        ledger.approve(intent_id=intent.intent_id, role="source",
                       authenticated_owner="owner-a", expected_digest=intent.digest())
        ledger.approve(intent_id=intent.intent_id, role="receiver",
                       authenticated_owner=intent.target_owner,
                       expected_digest=intent.digest())

    gate = threading.Barrier(2)

    def race(intent: TransferIntent) -> str:
        with connection_factory() as connection:
            gate.wait(timeout=15)
            try:
                connection.execute(intent, now=1000)
                return "committed"
            except TransactionDenied:
                return "denied"

    start = time.perf_counter_ns()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = tuple(pool.map(race, racers))
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
    after_balances, new_tick, new_receipts, new_outbox = _snapshot(ledger)
    if (sorted(outcomes) != ["committed", "denied"]
            or (new_tick, new_receipts, new_outbox) != (3, 3, 3)
            or sum(quantity for _, quantity in after_balances) != 130):
        raise AssertionError("concurrent writers violated single-tick state invariants")
    return {"committed": 1, "denied": 1, "tick": new_tick,
            "receipts": new_receipts, "outbox": new_outbox,
            "conserved_units": 130, "wall_ms": elapsed_ms}


def _timing(summary: TraceSummary) -> dict[str, float | int]:
    samples = summary.latency_ms
    return {"operations": len(samples), "total_ms": sum(samples),
            "median_ms": statistics.median(samples), "p95_ms": percentile(samples, 0.95),
            "p99_ms": percentile(samples, 0.99)}


def _run_postgres() -> tuple[TraceSummary, dict[str, str], dict[str, int | float]]:
    if os.environ.get("OPENWORLD_PG_TEST_ISOLATED") != "YES_EPHEMERAL_DB":
        raise RuntimeError("explicit OPENWORLD_PG_TEST_ISOLATED=YES_EPHEMERAL_DB required")
    dsn = os.environ.get("OPENWORLD_PG_TEST_DSN")
    if not dsn:
        raise RuntimeError("OPENWORLD_PG_TEST_DSN must identify a disposable database")
    from openworld_superkernel.postgres_control_plane import (  # noqa: E402
        PostgresWorldLedger, connect_postgres,
    )
    conn = connect_postgres(dsn)
    try:
        name = conn.execute("SELECT current_database()").fetchone()[0]
        if not isinstance(name, str) or not name.startswith("openworld_ephemeral_"):
            raise RuntimeError("refusing non-ephemeral PostgreSQL database name")
        # These DDL calls are intentionally permitted *only* after the DB-name
        # guard. A privileged operator must create the dedicated DB first.
        db = PostgresWorldLedger(conn, initialize=True)
        summary = run_trace(db)
        contention = run_contention(db, lambda: PostgresWorldLedger(
            connect_postgres(dsn), initialize=False))
        server_version = conn.execute("SHOW server_version").fetchone()[0]
        return summary, {"database": "ephemeral (name withheld)",
                         "server_version": server_version}, contention
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-postgres", action="store_true",
                        help="use an explicitly provisioned disposable PostgreSQL DB")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="ow-w5-parity-") as directory:
        path = Path(directory) / "sqlite_world.db"
        with AtomicWorldLedger(path) as sqlite_ledger:
            sqlite = run_trace(sqlite_ledger)
            sqlite_contention = run_contention(
                sqlite_ledger, lambda: AtomicWorldLedger(path))
        report: dict[str, Any] = {
            "protocol": "openworld-storage-parity-p1",
            "environment": {"python": platform.python_version(),
                            "sqlite": sqlite3.sqlite_version,
                            "platform": platform.platform()},
            "sqlite": {"logical": sqlite.logical(), "timing": _timing(sqlite),
                       "contention": sqlite_contention},
            "postgres": {"status": "NOT_RUN"},
            "warning": "Tiny synthetic trace; timing includes backend-specific Python/IPC overhead; "
                       "no production, identity, security or throughput conclusion.",
        }
        if args.with_postgres:
            postgres, server, pg_contention = _run_postgres()
            if postgres.logical() != sqlite.logical():
                raise AssertionError("storage backends disagree on logical trace")
            report["postgres"] = {"status": "MATCH", "logical": postgres.logical(),
                                  "timing": _timing(postgres), "server": server,
                                  "contention": pg_contention}
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
