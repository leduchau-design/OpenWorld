"""Static, dependency-free safety gate for the manual PostgreSQL workflow.

These checks intentionally do NOT execute the PostgreSQL service, do NOT verify
billing, and do NOT certify any database or real-user security property.
"""
from pathlib import Path
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "w5-postgres-parity-manual.yml"


class ManualPostgresWorkflowSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_only_has_explicit_dispatch_event(self) -> None:
        yaml = self.workflow
        self.assertIn("on:\n  workflow_dispatch:\n", yaml)
        for trigger in ("push:", "pull_request:", "schedule:", "workflow_call:"):
            with self.subTest(trigger=trigger):
                self.assertNotIn("\n  " + trigger, yaml)

    def test_requires_literal_owner_budget_acknowledgement(self) -> None:
        yaml = self.workflow
        self.assertIn("      budget_ack:", yaml)
        self.assertIn("        required: true", yaml)
        self.assertIn("        type: string", yaml)
        self.assertIn("inputs.budget_ack == 'YES_BUDGET_CHECKED'", yaml)

    def test_never_runs_on_non_main_branch(self) -> None:
        self.assertIn("github.ref == 'refs/heads/main'", self.workflow)
        self.assertIn("    if: ${{ github.ref ==", self.workflow)

    def test_uses_only_disposable_database_and_no_production_network_action(self) -> None:
        yaml = self.workflow
        self.assertIn("POSTGRES_DB: openworld_ephemeral_ci", yaml)
        self.assertIn("OPENWORLD_PG_TEST_ISOLATED: YES_EPHEMERAL_DB", yaml)
        self.assertIn("python benchmarks/w5_storage_parity.py --with-postgres", yaml)
        self.assertNotIn("OPENWORLD_PRODUCTION", yaml)

    def test_report_checked_before_short_retention_artifact(self) -> None:
        yaml = self.workflow
        self.assertLess(
            yaml.index("python scripts/verify_w5_pg_report.py"),
            yaml.index("actions/upload-artifact@v4"),
        )
        self.assertIn("retention-days: 7", yaml)


if __name__ == "__main__":
    unittest.main()
