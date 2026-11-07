"""Issue #11 independent reproduction bundle: raw, pinned, CPU-only evidence.

Requires a separate human reviewer to clone clean merged main and specify its
40-hex commit SHA. This tool does not certify the reviewer's independence,
real-world provenance, key custody, W3/SQLite atomicity, or production readiness.
It never invokes paid APIs or external services.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "openworld.gate11.raw-reproduction-bundle.v1"


def command_plan() -> tuple[tuple[str, tuple[str, ...]], ...]:
    python = sys.executable
    return (
        ("01_full_unittest", (python, "-m", "unittest",
                              "discover", "-s", "tests", "-v")),
        ("02_repository_layout", (python, "scripts/check_repository.py")),
        ("03_w5_abrupt_seed2026",
         (python, "benchmarks/w5_memory.py", "--agents", "100",
          "--days", "60", "--seed", "2026", "--scenario", "abrupt")),
        ("04_w5_stable_seed2027",
         (python, "benchmarks/w5_memory.py", "--agents", "100",
          "--days", "60", "--seed", "2027", "--scenario", "stable")),
        ("05_w5_noise_seed2028",
         (python, "benchmarks/w5_memory.py", "--agents", "100",
          "--days", "60", "--seed", "2028", "--scenario", "noise")),
        ("06_w5_holdout_gradual_seed91101",
         (python, "benchmarks/w5_memory.py", "--agents", "100",
          "--days", "60", "--seed", "91101", "--scenario", "gradual")),
        ("07_w5_holdout_alternating_seed91102",
         (python, "benchmarks/w5_memory.py", "--agents", "100",
          "--days", "60", "--seed", "91102", "--scenario", "alternating")),
        ("08_protected_five_agent_replay",
         (python, "-m", "unittest", "discover", "-s", "tests",
          "-p", "test_sec001_hypermemory_integration.py", "-v")),
        ("09_owner_namespace_and_legacy",
         (python, "-m", "unittest", "discover", "-s", "tests",
          "-p", "test_hyper_memory_owner_namespace.py", "-v")),
        ("10_r0_integrated_agent", (python, "examples/r0_agent_cycle.py")),
    )


def _git(*args: str) -> str:
    result = subprocess.run(
        ("git",) + args, cwd=ROOT, capture_output=True, text=True,
        timeout=15, check=True,
    )
    return result.stdout.strip()


def verify_clean_pinned_main(expected_sha: str) -> dict:
    if not isinstance(expected_sha, str) or not re.fullmatch(
            r"[0-9a-f]{40}", expected_sha):
        raise ValueError("expected SHA must be an exact lowercase 40-hex commit")
    # A local main branch at an old SHA could otherwise incorrectly pass.
    # This checks the FETCHED origin/main ref, not the live GitHub network.
    # An independent reviewer MUST first fetch origin/main and compare its
    # SHA with GitHub before claiming the review targets current merged main.
    try:
        branch = _git("symbolic-ref", "--quiet", "--short", "HEAD")
        head = _git("rev-parse", "HEAD")
        main = _git("rev-parse", "refs/heads/main")
        remote_main = _git("rev-parse", "--verify", "refs/remotes/origin/main")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "refuse detached checkout or missing local/origin main reference"
        ) from exc
    if (branch != "main" or head != expected_sha or
            main != expected_sha or remote_main != expected_sha):
        raise RuntimeError(
            "refuse detached, outdated or unpinned tree: "
            "local main, origin/main and HEAD must match --expected-sha")
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("working tree is dirty; reproduce on a clean clone")
    return {
        "head_sha": head,
        "main_sha": main,
        "origin_main_sha": remote_main,
        "checked_out_branch": branch,
        "git_status": "clean",
        "commit_subject": _git("show", "-s", "--format=%s", "HEAD"),
    }


def _resources() -> dict:
    try:
        import resource
    except ImportError:
        return {"child_cpu_user_s": None, "child_cpu_system_s": None,
                "child_peak_rss_native": None}
    v = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "child_cpu_user_s": v.ru_utime,
        "child_cpu_system_s": v.ru_stime,
        "child_peak_rss_native": v.ru_maxrss,
    }


def run_bundle(*, expected_sha: str, out_dir: Path) -> dict:
    metadata = verify_clean_pinned_main(expected_sha)
    out_dir = Path(out_dir).resolve()
    # Store outside the source tree to preserve its clean checkout.
    if out_dir == ROOT or ROOT in out_dir.parents:
        raise ValueError("evidence output must be outside the repository")
    if not out_dir.parent.is_dir():
        raise ValueError("output parent must already exist")
    out_dir.mkdir(exist_ok=False)
    rows = []
    for label, command in command_plan():
        started = datetime.now(timezone.utc).isoformat()
        start = time.perf_counter()
        cpu_before = _resources()
        status = "completed"
        try:
            completed = subprocess.run(
                command, cwd=ROOT, env={**os.environ, "OPENWORLD_SLOW_TESTS": "1"},
                capture_output=True, timeout=360, check=False,
            )
            stdout, stderr = completed.stdout, completed.stderr
            exit_code = completed.returncode
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout or b""
            stderr = error.stderr or b""
            status = "timeout"
            exit_code = None
        stdout_file = f"{label}.stdout.txt"
        stderr_file = f"{label}.stderr.txt"
        (out_dir / stdout_file).write_bytes(stdout)
        (out_dir / stderr_file).write_bytes(stderr)
        cpu_after = _resources()
        rows.append({
            "label": label,
            "command_argv": list(command),
            "utc_started": started,
            "status": status,
            "exit_code": exit_code,
            "wall_seconds": time.perf_counter() - start,
            "child_cpu_user_delta_s": (
                cpu_after["child_cpu_user_s"] - cpu_before["child_cpu_user_s"]
                if cpu_after["child_cpu_user_s"] is not None else None),
            "child_cpu_system_delta_s": (
                cpu_after["child_cpu_system_s"] - cpu_before["child_cpu_system_s"]
                if cpu_after["child_cpu_system_s"] is not None else None),
            "child_peak_rss_native": cpu_after["child_peak_rss_native"],
            "stdout_file": stdout_file,
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_file": stderr_file,
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            "stdout_bytes": len(stdout),
            "stderr_bytes": len(stderr),
        })
    successful = all(r["exit_code"] == 0 and
                     r["status"] == "completed" for r in rows)
    result = {
        "schema": SCHEMA,
        "status": "RUN_COMMANDS_PASS" if successful else "RUN_COMMANDS_FAIL",
        "claim_limit": "Self-reported local execution; second-contributor review NOT established",
        "source": metadata,
        "environment": {
            "python": sys.version.split()[0],
            "sqlite": sqlite3.sqlite_version,
            "os": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "working_directory": str(ROOT),
            "output_directory": str(out_dir),
        },
        "steps": rows,
        "manual_checks_remaining": [
            "W0 RFC-006 schema reviewed and approved by authorized reviewer",
            "Verify that protected exact history and compact state are NOT equivalent",
            "Verify raw output digest, owner scope, retention and negative cases",
            "Check filesystem, SQLite WAL/SHM and CPU/RSS cost on reviewer hardware",
            "Inspect real authorization, external anchor custody and power-loss gaps",
            "Independent second-contributor attribution and signature required",
            "Scientific and production adoption NOT implied by tests passing",
        ],
    }
    with (out_dir / "manifest.json").open("x", encoding="utf-8") as file:
        file.write(json.dumps(result, indent=2, sort_keys=True,
                              allow_nan=False) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-only", action="store_true",
                        help="print commands; run nothing")
    parser.add_argument("--expected-sha",
                        help="exact lowercase 40-hex SHA of clean merged main")
    parser.add_argument("--out-dir", type=Path,
                        help="nonexistent evidence directory outside repository")
    args = parser.parse_args()
    if args.list_only:
        print(json.dumps(
            {"schema": SCHEMA, "plan": [
                {"label": label, "argv": cmd}
                for label, cmd in command_plan()
            ], "executed": False}, indent=2))
        return
    if not args.expected_sha or args.out_dir is None:
        parser.error("--expected-sha and --out-dir are required to execute")
    result = run_bundle(expected_sha=args.expected_sha, out_dir=args.out_dir)
    print(json.dumps(
        {"status": result["status"],
         "source_sha": result["source"]["head_sha"],
         "step_exit_codes": [
             (s["label"], s["exit_code"]) for s in result["steps"]],
         "manifest": str(args.out_dir / "manifest.json"),
         "gate11_closed": False},
        indent=2, sort_keys=True))
    if result["status"] != "RUN_COMMANDS_PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
