"""SEC-003 diagnostic checks, including ambiguity of a seemingly unchanged DB."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openworld_superkernel.witness_recovery import (
    assess_authority, RecoveryState,
)
import test_anti_rollback as fixture


class WitnessRecoveryTests(unittest.TestCase):
    """Use existing synthetic setup without inheriting its test cases."""

    def setUp(self):
        fixture.AntiRollbackTests.setUp(self)

    def tearDown(self):
        fixture.AntiRollbackTests.tearDown(self)

    def make_backup(self):
        fixture.AntiRollbackTests.make_backup(self)

    def restore(self):
        fixture.AntiRollbackTests.restore(self)

    def test_consistent_head_is_only_a_consistency_check(self):
        report = assess_authority(self.raw, self.witness)
        self.assertEqual(report.state, RecoveryState.CONSISTENT)
        self.assertTrue(report.digest_consistent_without_pending_fence)
        self.assertFalse(report.operator_review_required)
        self.assertEqual(report.witnessed_epoch, 0)

    def test_mutation_then_consistent_head(self):
        self.safe.issue("op1")
        report = assess_authority(self.raw, self.witness)
        self.assertEqual(report.state, RecoveryState.CONSISTENT)
        self.assertEqual(report.witnessed_epoch, 1)

    def test_missing_witness_denies(self):
        self.witness.available = False
        report = assess_authority(self.raw, self.witness)
        self.assertEqual(report.state, RecoveryState.WITNESS_UNAVAILABLE)
        self.assertFalse(report.digest_consistent_without_pending_fence)

    def test_pending_unchanged_still_requires_review(self):
        with self.assertRaises(RuntimeError):
            self.safe._mutate("bad", lambda: (_ for _ in ()).throw(RuntimeError()))
        report = assess_authority(self.raw, self.witness)
        self.assertEqual(report.state, RecoveryState.PENDING_UNCHANGED)
        self.assertEqual(report.pending_operation, "bad")
        self.assertFalse(report.digest_consistent_without_pending_fence)
        self.assertTrue(report.operator_review_required)

    def test_pending_changed_still_requires_review(self):
        def committed_but_not_finalized():
            self.raw.issue("g1")
            raise RuntimeError("synthetic crash")
        with self.assertRaises(RuntimeError):
            self.safe._mutate("op1", committed_but_not_finalized)
        report = assess_authority(self.raw, self.witness)
        self.assertEqual(report.state, RecoveryState.PENDING_CHANGED)
        self.assertFalse(report.digest_consistent_without_pending_fence)

    def test_rollback_clean_digest_does_not_release_pending(self):
        # Simulates committed effect followed by database rollback to the
        # original snapshot; identical bytes must not clear an old fence.
        self.make_backup()
        def committed_then_crash():
            self.raw.issue("g1")
            raise RuntimeError("crash")
        with self.assertRaises(RuntimeError):
            self.safe._mutate("op1", committed_then_crash)
        self.restore()
        report = assess_authority(self.raw, self.witness)
        self.assertEqual(report.state, RecoveryState.PENDING_UNCHANGED)
        self.assertFalse(report.digest_consistent_without_pending_fence)

    def test_unfenced_mutation_reports_divergence(self):
        self.raw.issue("direct-bypass")
        report = assess_authority(self.raw, self.witness)
        self.assertEqual(report.state, RecoveryState.DIVERGENT)
        self.assertFalse(report.digest_consistent_without_pending_fence)

    def test_missing_authority_data_fails_closed(self):
        self.raw.db.execute('DROP TABLE grants')
        report = assess_authority(self.raw, self.witness)
        self.assertEqual(report.state, RecoveryState.DIVERGENT)
        self.assertFalse(report.digest_consistent_without_pending_fence)
        self.assertIsNone(report.observed_digest)



if __name__ == "__main__":
    unittest.main()