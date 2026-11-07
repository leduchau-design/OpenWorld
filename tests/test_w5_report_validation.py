"""Artifact verifier tests: synthetic fixtures are NOT live PostgreSQL evidence."""
from __future__ import annotations

import copy
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_w5_pg_report import (InvalidParityReport, _EXPECTED_OUTCOMES, validate)

_SHA = "a" * 40
_RUN = "123456789"


def sample():
    logical = {"outcomes": dict(_EXPECTED_OUTCOMES),
               "balances": {"agent-a": 91, "agent-b": 17, "agent-c": 22},
               "tick": 2, "receipts": 2, "outbox": 2, "total_units": 130}
    timing = {"operations": len(_EXPECTED_OUTCOMES), "total_ms": 3.0,
              "median_ms": .1, "p95_ms": .2, "p99_ms": .4}
    contention = {"committed": 1, "denied": 1, "tick": 3,
                  "receipts": 3, "outbox": 3, "conserved_units": 130,
                  "wall_ms": 1.2}
    return {"protocol": "openworld-storage-parity-p1",
            "environment": {"python": "3.11", "sqlite": "3.43", "platform": "linux"},
            "sqlite": {"logical": logical, "timing": timing, "contention": contention},
            "postgres": {"status": "MATCH", "logical": copy.deepcopy(logical),
                         "timing": copy.deepcopy(timing),
                         "contention": copy.deepcopy(contention),
                         "server": {"server_version": "16.4",
                                    "database": "ephemeral (name withheld)"}},
            "execution": {"git_sha": _SHA, "github_run_id": _RUN}}


class ArtifactValidatorTests(unittest.TestCase):
    def test_valid_report_is_only_claim_validation(self):
        self.assertEqual(validate(sample(), expected_sha=_SHA,
                                  expected_run_id=_RUN)["status"],
                         "REPORT_VALIDATED_NOT_ATTESTED")

    def test_refuses_missing_postgres_even_when_sqlite_valid(self):
        x = sample(); x["postgres"] = {"status": "NOT_RUN"}
        with self.assertRaises(InvalidParityReport): validate(x)
        self.assertEqual(validate(x, require_postgres=False)["postgres"], "NOT_RUN")

    def test_refuses_changed_outcome_even_if_both_backends_agree(self):
        x = sample()
        for k in ("sqlite", "postgres"):
            x[k]["logical"]["outcomes"]["deny:receiver_missing"] = "ok"
        with self.assertRaises(InvalidParityReport): validate(x)

    def test_refuses_lost_receipt_or_conservation(self):
        for prop in ("receipts", "total_units"):
            with self.subTest(prop=prop):
                x = sample()
                x["postgres"]["logical"][prop] -= 1
                with self.assertRaises(InvalidParityReport): validate(x)

    def test_race_does_not_allow_both_writers(self):
        x = sample(); x["postgres"]["contention"]["committed"] = 2
        with self.assertRaises(InvalidParityReport): validate(x)

    def test_rejects_invalid_timings(self):
        for value in (math.nan, math.inf, -1, "0.1", True):
            with self.subTest(value=value):
                x = sample(); x["postgres"]["timing"]["p99_ms"] = value
                with self.assertRaises(InvalidParityReport): validate(x)

    def test_percentile_order(self):
        x = sample(); x["sqlite"]["timing"]["p95_ms"] = 9
        with self.assertRaises(InvalidParityReport): validate(x)

    def test_rejects_mismatched_sha_and_run(self):
        with self.assertRaises(InvalidParityReport):
            validate(sample(), expected_sha="b" * 40)
        with self.assertRaises(InvalidParityReport):
            validate(sample(), expected_run_id="456")

    def test_rejects_wrong_database_identity(self):
        x = sample(); x["postgres"]["server"]["database"] = "production"
        with self.assertRaises(InvalidParityReport): validate(x)

    def test_rejects_bool_instead_of_integer(self):
        x = sample(); x["sqlite"]["contention"]["committed"] = True
        with self.assertRaises(InvalidParityReport): validate(x)

    def test_rejects_unknown_protocol(self):
        x = sample(); x["protocol"] = "different"
        with self.assertRaises(InvalidParityReport): validate(x)

    def test_fixture_does_not_access_network_or_pg(self):
        # Deliberately leaves the external DB absent; this is a schema-only test.
        self.assertIn("server", sample()["postgres"])


if __name__ == "__main__":
    unittest.main()