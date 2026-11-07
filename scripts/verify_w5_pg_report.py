"""Validate W5 synthetic SQLite/PostgreSQL parity artifacts; never certify real identities.

This script validates the shape and *stated* invariants of an externally produced
report. A syntactically valid report is not proof of genuine PostgreSQL execution;
inspect the matching trusted GitHub Actions run and service logs separately.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

_EXPECTED_OUTCOMES = {
    "seed:agent-a": "ok", "seed:agent-b": "ok", "seed:agent-c": "ok",
    "prepare:first": "ok", "approve:source": "ok",
    "deny:receiver_missing": "denied", "deny:wrong_receiver": "denied",
    "approve:receiver": "ok", "fault:after_debit": "rolled_back",
    "execute:first": "ok", "replay:first": "ok",
    "deny:changed_payload": "denied",
    "prepare:revoked": "ok", "approve:revoked:source": "ok",
    "approve:revoked:receiver": "ok", "revoke:receiver": "ok",
    "deny:revoked": "denied", "prepare:second": "ok",
    "approve:second:source": "ok", "approve:second:receiver": "ok",
    "execute:second": "ok", "replay:second": "ok",
    "prepare:stale": "ok", "approve:stale:source": "ok",
    "approve:stale:receiver": "ok", "deny:stale_tick": "denied",
}
_FINAL = {"outcomes": _EXPECTED_OUTCOMES,
          "balances": {"agent-a": 91, "agent-b": 17, "agent-c": 22},
          "tick": 2, "receipts": 2, "outbox": 2, "total_units": 130}
_RACE = {"committed": 1, "denied": 1, "tick": 3,
         "receipts": 3, "outbox": 3, "conserved_units": 130}
_HEX_SHA = re.compile(r"[a-f0-9]{40}\Z")


class InvalidParityReport(ValueError):
    """A report is missing evidence required by this synthetic protocol."""


def _object(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise InvalidParityReport(f"{name}: expected object")
    return value


def _nonnegative_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidParityReport(f"{name}: not a number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise InvalidParityReport(f"{name}: nonfinite or negative")
    return number


def _timing(value: Any, name: str) -> None:
    data = _object(value, name)
    n = data.get("operations")
    if type(n) is not int or n != len(_EXPECTED_OUTCOMES):
        raise InvalidParityReport(f"{name}: unexpected number of operations")
    measures = [_nonnegative_number(data.get(k), f"{name}.{k}")
                for k in ("total_ms", "median_ms", "p95_ms", "p99_ms")]
    _, median, p95, p99 = measures
    if not median <= p95 <= p99:
        raise InvalidParityReport(f"{name}: invalid percentile ordering")


def _race(value: Any, name: str) -> None:
    record = _object(value, name)
    for key, expected in _RACE.items():
        if type(record.get(key)) is not int or record[key] != expected:
            raise InvalidParityReport(f"{name}.{key}: invalid contention invariant")
    _nonnegative_number(record.get("wall_ms"), f"{name}.wall_ms")


def validate(report: Any, *, expected_sha: str | None = None,
             expected_run_id: str | None = None,
             require_postgres: bool = True) -> dict[str, Any]:
    """Validate claimed small-trace parity; metadata remains self-reported."""
    data = _object(report, "root")
    if data.get("protocol") != "openworld-storage-parity-p1":
        raise InvalidParityReport("wrong protocol")
    environment = _object(data.get("environment"), "environment")
    for field in ("python", "sqlite", "platform"):
        if not isinstance(environment.get(field), str) or not environment[field]:
            raise InvalidParityReport(f"missing environment.{field}")
    sqlite = _object(data.get("sqlite"), "sqlite")
    if sqlite.get("logical") != _FINAL:
        raise InvalidParityReport("SQLite trace differs from independent P1 expectation")
    _timing(sqlite.get("timing"), "sqlite.timing")
    _race(sqlite.get("contention"), "sqlite.contention")

    pg = _object(data.get("postgres"), "postgres")
    if pg.get("status") != "MATCH":
        if require_postgres:
            raise InvalidParityReport("real PostgreSQL run not evidenced")
        if pg != {"status": "NOT_RUN"}:
            raise InvalidParityReport("unexpected PostgreSQL state")
    else:
        if pg.get("logical") != _FINAL:
            raise InvalidParityReport("PostgreSQL and expected trace mismatch")
        if pg["logical"] != sqlite["logical"]:
            raise InvalidParityReport("backends report different results")
        _timing(pg.get("timing"), "postgres.timing")
        _race(pg.get("contention"), "postgres.contention")
        server = _object(pg.get("server"), "postgres.server")
        version = server.get("server_version")
        if not isinstance(version, str) or not version:
            raise InvalidParityReport("missing PostgreSQL server version")
        if server.get("database") != "ephemeral (name withheld)":
            raise InvalidParityReport("unexpected database disclosure/identity")

    if expected_sha is not None or expected_run_id is not None:
        origin = _object(data.get("execution"), "execution")
        if expected_sha is not None:
            if (not _HEX_SHA.fullmatch(expected_sha) or
                    origin.get("git_sha") != expected_sha):
                raise InvalidParityReport("run/check-out source SHA mismatch")
        if expected_run_id is not None:
            if (not expected_run_id.isdigit() or
                    origin.get("github_run_id") != expected_run_id):
                raise InvalidParityReport("run ID mismatch")
    return {"status": "REPORT_VALIDATED_NOT_ATTESTED",
            "protocol": data["protocol"],
            "postgres": pg["status"],
            "operations": len(_EXPECTED_OUTCOMES),
            "commit": data.get("execution", {}).get("git_sha")}


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise InvalidParityReport("duplicate JSON key")
        obj[key] = value
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--expected-sha")
    parser.add_argument("--expected-run-id")
    parser.add_argument("--allow-sqlite-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.report.stat().st_size > 1024 * 1024:
            raise InvalidParityReport("oversized research report")
        data = json.loads(args.report.read_text(encoding="utf-8"),
                          object_pairs_hook=_no_duplicate_keys,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              InvalidParityReport("nonfinite JSON value")))
        result = validate(data, expected_sha=args.expected_sha,
                          expected_run_id=args.expected_run_id,
                          require_postgres=not args.allow_sqlite_only)
    except (InvalidParityReport, OSError, UnicodeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"INVALID W5 REPORT: {exc}\n")
    print(json.dumps(result, sort_keys=True))
    print("Review trusted GitHub job logs: JSON alone does not attest PostgreSQL execution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())