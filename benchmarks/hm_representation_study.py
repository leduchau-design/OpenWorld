"""W5 representation study: synthetic full-feedback forecast + censored decisions.

Two separate lanes deliberately prevent a deceptive result:
- Forecast lane: all models receive the SAME synthetic labels AFTER predicting.
- Decision lane: each policy only updates after its own accepted toy offer;
  abstention reveals no counterfactual partner outcome. All strategies share a
  fixed exogenous response tape, but that tape is private to the evaluator.

No W3 transfer, real user, authentication, model API, external action, or
production HyperMemory migration is performed by this benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import sqlite3
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from openworld_superkernel.memory_representation_study import MODELS, make_model

SCENARIOS = (
    "stable", "collapse", "recovery", "periodic",
    "markov_persist", "markov_flip", "noise",
)
POLICIES = ("fixed_hold", "fixed_offer") + MODELS
SCHEMA = "openworld.hm.representation-study.v0"
PROBE_INTERVAL = 7
REWARD_SUCCESS = 0.6
REWARD_FAILURE = -0.4
# E[R|offer] = 0.6p - 0.4(1-p) = p-0.4; abstain reward=0.
OFFER_THRESHOLD = 0.4


def response_tape(scenario: str, seed: int, steps: int) -> tuple[int, ...]:
    """Fixed synthetic potential outcomes; never handed to the predictors."""
    if (scenario not in SCENARIOS or type(seed) is not int or seed < 0
            or type(steps) is not int or not 8 <= steps <= 512):
        raise ValueError("invalid bounded synthetic workload")
    rng = random.Random(seed)
    out = []
    for tick in range(steps):
        if scenario in ("markov_persist", "markov_flip"):
            keep_probability = 0.9 if scenario == "markov_persist" else 0.1
            if tick == 0:
                y = rng.randrange(2)
            else:
                y = out[-1] if rng.random() < keep_probability else 1 - out[-1]
        else:
            p = {
                "stable": 0.75,
                "collapse": 0.85 if tick < steps // 2 else 0.15,
                "recovery": 0.15 if tick < steps // 2 else 0.85,
                "periodic": 0.8 if tick % 12 < 6 else 0.2,
                "noise": 0.5,
            }[scenario]
            y = int(rng.random() < p)
        out.append(y)
    return tuple(out)


def _calibration(pairs: list[tuple[float, int]]) -> float:
    # Diagnostic ECE, FIVE FIXED bins; small bins are noisy, not calibration proof.
    bins = [[] for _ in range(5)]
    for p, y in pairs:
        bins[min(4, int(p * 5))].append((p, y))
    return sum(
        len(b) / len(pairs) *
        abs(statistics.mean(y for _, y in b) -
            statistics.mean(p for p, _ in b))
        for b in bins if b
    )


def forecast(tape: tuple[int, ...], *, period: int = 12) -> dict:
    """Prequential full-observation forecast, NOT a partially observed agent."""
    models = {name: make_model(name, period=period) for name in MODELS}
    outcomes = {name: [] for name in MODELS}
    cpu_ns = {name: 0 for name in MODELS}
    for tick, y in enumerate(tape):
        # Predict all methods before any observes this outcome.
        predictions = {}
        for name, model in models.items():
            start = time.process_time_ns()
            predictions[name] = model.predict(tick)
            cpu_ns[name] += time.process_time_ns() - start
        for name, model in models.items():
            p = predictions[name]
            outcomes[name].append((p, y))
            start = time.process_time_ns()
            model.observe(tick, y)
            cpu_ns[name] += time.process_time_ns() - start
    result = {}
    for name, pairs in outcomes.items():
        brier = statistics.mean((p - y) ** 2 for p, y in pairs)
        log_loss = statistics.mean(
            -y * math.log(max(1e-9, min(1 - 1e-9, p)))
            -(1 - y) * math.log(max(1e-9, min(1 - 1e-9, 1 - p)))
            for p, y in pairs
        )
        result[name] = {
            "brier": brier,
            "log_loss": log_loss,
            "calibration_ece5": _calibration(pairs),
            "serialized_state_bytes": len(json.dumps(
                models[name].snapshot(), separators=(",", ":")).encode()),
            "model_cpu_ns": cpu_ns[name],
        }
    return result


def decisions(tape: tuple[int, ...], *, period: int = 12) -> dict:
    """Policy lane: learned encoders see feedback ONLY for actual toy offers.

    The experiment is NOT a W3 resource transfer: decisions use an exogenous
    synthetic response and toy utility, with no claim of actual authorization
    or observed real partner reciprocity.
    """
    result = {}
    for name in POLICIES:
        model = None if name.startswith("fixed_") else make_model(name, period=period)
        model_updates = offers = successes = failures = probes = 0
        total_reward = 0.0
        peak_loss = 0.0
        for tick, y in enumerate(tape):
            if name == "fixed_hold":
                offered, forced = False, False
            elif name == "fixed_offer":
                offered, forced = True, False
            else:
                p = model.predict(tick)
                forced = tick % PROBE_INTERVAL == 0 and p < OFFER_THRESHOLD
                offered = p >= OFFER_THRESHOLD or forced
            if offered:
                # y is accessible only *after* the action; no hold update.
                offers += 1
                successes += y
                failures += 1 - y
                total_reward += REWARD_SUCCESS if y else REWARD_FAILURE
                peak_loss = max(peak_loss, failures * (-REWARD_FAILURE))
                if forced:
                    probes += 1
                if model is not None:
                    model.observe(tick, y)
                    model_updates += 1
        result[name] = {
            "offers": offers, "observed_feedback": offers,
            "model_updates": model_updates,
            "successes": successes, "failures": failures, "forced_probes": probes,
            "utility": round(total_reward, 10),
            "gross_failure_exposure": round(peak_loss, 10),
        }
    return result


def _disk_bytes(path: Path) -> int:
    return sum(
        f.stat().st_size for suffix in ("", "-wal", "-shm")
        if (f := Path(str(path) + suffix)).exists()
    )


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)]


def storage_profile(tape: tuple[int, ...], *, period: int = 12) -> dict:
    """Independent SQLite stores, identical upsert schema and durability knobs.

    The FULL_HISTORY state contains the complete toy label sequence; compact
    states CANNOT answer exact past-label queries. A real protected exact ledger
    must be retained separately for ALL candidates according to retention.
    """
    results = {}
    with tempfile.TemporaryDirectory(prefix="openworld-hm-repr-") as directory:
        for name in MODELS:
            db_path = Path(directory) / (name + ".sqlite3")
            model = make_model(name, period=period)
            connection = sqlite3.connect(db_path, isolation_level=None)
            try:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute(
                    "CREATE TABLE snapshot(id INTEGER PRIMARY KEY CHECK(id=1), "
                    "state_json TEXT NOT NULL)"
                )
                times = []
                peak = _disk_bytes(db_path)
                for tick, y in enumerate(tape):
                    model.observe(tick, y)
                    record = json.dumps(
                        model.snapshot(), sort_keys=True, separators=(",", ":"),
                    )
                    start = time.perf_counter()
                    connection.execute("BEGIN IMMEDIATE")
                    try:
                        connection.execute(
                            "INSERT INTO snapshot(id,state_json) VALUES(1,?) "
                            "ON CONFLICT(id) DO UPDATE SET state_json=excluded.state_json",
                            (record,),
                        )
                        connection.execute("COMMIT")
                    except BaseException:
                        connection.execute("ROLLBACK")
                        raise
                    times.append((time.perf_counter() - start) * 1000)
                    peak = max(peak, _disk_bytes(db_path))
                online = _disk_bytes(db_path)
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                post_checkpoint = _disk_bytes(db_path)
                results[name] = {
                    "peak_online_bytes_incl_wal_shm": peak,
                    "end_online_bytes_incl_wal_shm": online,
                    "post_checkpoint_bytes_incl_wal_shm": post_checkpoint,
                    "p95_snapshot_write_ms": _p95(times),
                    "writes": len(tape),
                }
            finally:
                connection.close()
    return results


def run(*, seed_start: int = 41001, seed_count: int = 5,
        steps: int = 120, period: int = 12,
        scenarios: tuple[str, ...] = SCENARIOS,
        profile_disk: bool = True) -> dict:
    if (type(seed_start) is not int or seed_start < 0
            or type(seed_count) is not int or not 1 <= seed_count <= 12
            or type(steps) is not int or not 8 <= steps <= 512
            or type(period) is not int or not 3 <= period <= 64
            or not scenarios or any(s not in SCENARIOS for s in scenarios)
            or len(set(scenarios)) != len(scenarios)
            or type(profile_disk) is not bool):
        raise ValueError("invalid bounded benchmark configuration")
    cases = []
    for scenario in scenarios:
        for seed in range(seed_start, seed_start + seed_count):
            tape = response_tape(scenario, seed, steps)
            cases.append({
                "scenario": scenario, "seed": seed, "steps": steps,
                "synthetic_tape_sha256": hashlib.sha256(bytes(tape)).hexdigest(),
                "forecast_fully_observed": forecast(tape, period=period),
                "decisions_censored": decisions(tape, period=period),
            })
    summary = {}
    for scenario in scenarios:
        rows = [c for c in cases if c["scenario"] == scenario]
        summary[scenario] = {
            "forecast_mean_brier": {
                m: statistics.mean(
                    c["forecast_fully_observed"][m]["brier"] for c in rows
                ) for m in MODELS
            },
            "decision_mean_utility": {
                m: statistics.mean(
                    c["decisions_censored"][m]["utility"] for c in rows
                ) for m in POLICIES
            },
        }
    result = {
        "schema": SCHEMA,
        "source_task": "synthetic Bernoulli partner responses, action-independent tape",
        "parameters": {
            "seed_start": seed_start, "seed_count": seed_count,
            "steps": steps, "scenarios": scenarios, "fourier_period": period,
            "predeclared_probe_interval": PROBE_INTERVAL,
            "offer_threshold": OFFER_THRESHOLD,
            "reward_success": REWARD_SUCCESS, "reward_failure": REWARD_FAILURE,
        },
        "environment": {
            "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
            "platform": platform.platform(), "processor": platform.processor(),
        },
        "summary": summary,
        "cases": cases,
        "storage_single_representative_case": (
            {
                "scenario": "collapse",
                "seed": seed_start,
                "results": storage_profile(
                    response_tape("collapse", seed_start, steps), period=period,
                ),
            } if profile_disk else None
        ),
        "limitations": [
            "Forecast receives complete synthetic labels; it is a distinct supervised lane, NOT partial-feedback agent evidence",
            "Policy observes only outcomes of its own offers; outcomes after hold are NOT used for learning",
            "Full history and Beta counts have mathematically identical IID Bernoulli forecasts, but only full history answers exact-label queries",
            "Markov estimates adjacent OBSERVED transitions only; missing feedback is not hallucinated",
            "Fourier period is a fixed privileged task assumption (period=12); use --period 7 as a misspecification negative control",
            "Five-bin calibration is descriptive with small samples and not a calibration guarantee",
            "Forecast model CPU timings are noisy; storage timings include SQLite FULL sync but not cold start, CPU/RSS or filesystem blocks",
            "Storage profile does not include mandatory shared protected exact ledger; compact-only totals are NOT total compliant memory",
            "All trials are simulated and no W3 transaction, real consent, authentication, production safety or scientific superiority is shown",
            "Predeclared models/knobs are NOT tuned on these evaluation seeds; independent second review and new holdout remain outstanding",
        ],
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=41001)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--steps", type=int, default=120)
    parser.add_argument("--period", type=int, default=12)
    parser.add_argument("--scenario", choices=SCENARIOS, default=None)
    parser.add_argument("--no-disk-profile", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report = run(
        seed_start=args.seed_start, seed_count=args.seeds,
        steps=args.steps, period=args.period,
        scenarios=(args.scenario,) if args.scenario else SCENARIOS,
        profile_disk=not args.no_disk_profile,
    )
    data = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
    if args.out is not None:
        # Never clobber a prior evidence file.
        with args.out.open("x", encoding="utf-8") as handle:
            handle.write(data + "\n")
    print(data)


if __name__ == "__main__":
    main()
