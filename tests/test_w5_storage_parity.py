"""Deterministic, dependency-free W5 transaction parity contract checks.

The real PostgreSQL test is deliberately not part of default CI; the opt-in
benchmark uses one dedicated disposable PostgreSQL DB.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks"))

from openworld_superkernel.transactional_world import AtomicWorldLedger
from w5_storage_parity import TraceSummary, percentile, run_trace, run_contention


class ParityProtocolTests(unittest.TestCase):
    def test_synthetic_trace_sqlite(self):
        with tempfile.TemporaryDirectory() as path:
            with AtomicWorldLedger(Path(path) / "world.db") as ledger:
                report = run_trace(ledger)
        self.assertEqual(report.logical()["balances"],
                         {"agent-a": 91, "agent-b": 17, "agent-c": 22})
        self.assertEqual(report.tick, 2)
        self.assertEqual(report.receipts, 2)
        self.assertEqual(report.outbox, 2)
        self.assertEqual(report.total_units, 130)

    def test_deterministic_logical_outcomes(self):
        results = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as path:
                with AtomicWorldLedger(Path(path) / "world.db") as ledger:
                    results.append(run_trace(ledger).logical())
        self.assertEqual(results[0], results[1])

    def test_negative_cases_are_not_silenced(self):
        with tempfile.TemporaryDirectory() as path:
            with AtomicWorldLedger(Path(path) / "world.db") as ledger:
                outcomes = run_trace(ledger).logical()["outcomes"]
        for action in ("deny:receiver_missing", "deny:wrong_receiver",
                       "deny:changed_payload", "deny:revoked", "deny:stale_tick"):
            self.assertEqual(outcomes[action], "denied")
        self.assertEqual(outcomes["fault:after_debit"], "rolled_back")

    def test_accepted_replay_is_not_a_second_write(self):
        with tempfile.TemporaryDirectory() as path:
            with AtomicWorldLedger(Path(path) / "world.db") as ledger:
                result = run_trace(ledger)
                receipts = ledger.db.execute("SELECT count(*) FROM receipts").fetchone()[0]
                outbox = ledger.db.execute("SELECT count(*) FROM outbox").fetchone()[0]
        self.assertEqual(receipts, 2)
        self.assertEqual(outbox, 2)
        self.assertEqual(result.logical()["outcomes"]["replay:first"], "ok")
        self.assertEqual(result.logical()["outcomes"]["replay:second"], "ok")

    def test_two_independent_connections_cannot_commit_same_tick(self):
        with tempfile.TemporaryDirectory() as path:
            file_path = Path(path) / "world.db"
            with AtomicWorldLedger(file_path) as ledger:
                run_trace(ledger)
                outcome = run_contention(ledger, lambda: AtomicWorldLedger(file_path))
        self.assertEqual(outcome["committed"], 1)
        self.assertEqual(outcome["denied"], 1)
        self.assertEqual(outcome["tick"], 3)
        self.assertEqual(outcome["receipts"], 3)
        self.assertEqual(outcome["outbox"], 3)
        self.assertEqual(outcome["conserved_units"], 130)

    def test_refuses_nonempty_ledger(self):
        with tempfile.TemporaryDirectory() as path:
            with AtomicWorldLedger(Path(path) / "world.db") as ledger:
                ledger.seed_account("already-exists", "owner", 1)
                with self.assertRaises(RuntimeError):
                    run_trace(ledger)

    def test_refuses_existing_prepared_intent(self):
        from openworld_superkernel.transactional_world import TransferIntent
        with tempfile.TemporaryDirectory() as path:
            with AtomicWorldLedger(Path(path) / "world.db") as ledger:
                ledger.prepare(TransferIntent(
                    "stale", "a", "owner-a", "b", "owner-b",
                    1, "synthetic", "nonce-stale", 0, 2000,
                ))
                with self.assertRaises(RuntimeError):
                    run_trace(ledger)

    def test_nearest_rank_percentiles(self):
        samples = (1., 2., 3., 4., 5., 6.)
        self.assertEqual(percentile(samples, 0.5), 3.)
        self.assertEqual(percentile(samples, 0.95), 6.)
        self.assertEqual(percentile(samples, 0.99), 6.)

    def test_invalid_quantiles(self):
        for xs, q in (((), .5), ((1.,), -1), ((1.,), 1.1)):
            with self.subTest(xs=xs, q=q), self.assertRaises(ValueError):
                percentile(xs, q)

    def test_no_production_claim_in_report(self):
        # Explicitly require the interface to distinguish measured timings
        # from logical correctness and operational security guarantees.
        report = TraceSummary((('test', 'ok'),), (('a', 10),), 0, 0, 0, 10, (0.1,))
        self.assertNotIn('latency_ms', report.logical())
        self.assertNotIn('authenticated', report.logical())


if __name__ == "__main__":
    unittest.main()
