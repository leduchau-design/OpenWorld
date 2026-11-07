"""W5 synthetic representation benchmark: frozen linear readouts, NO MARL training.

Compares no-summary, global mean, stratified mean, histogram, ECF and
phase-random Fourier features on identical train/holdout population episodes.
The spectral task is deliberately aligned with one ECF frequency: a positive
control, not evidence that ECF is universally superior.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import sys
from time import perf_counter, process_time
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openworld_superkernel.population_repr import PopulationPoint, empirical_cf

METHODS = ("no_summary", "global_mean", "group_mean", "histogram8", "ecf", "rff")
TASKS = ("mean", "tail", "spectral")
ROLES = ("trader", "builder", "explorer")
REGIONS = ("north", "south")
TARGET = ("trader", "north")
VERSION = "openworld.w5.population-representation.v0"


def _clip(x: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, x))


def make_episode(n: int, d: int, seed: int, regime: str) -> tuple[PopulationPoint, ...]:
    """Same synthetic episode for every method; no identity, owner or memory fields."""
    if n < 6 or not 1 <= d <= 16 or regime not in ("balanced", "skewed", "rare"):
        raise ValueError("unsupported synthetic episode")
    rng = random.Random(seed)
    shift = rng.uniform(-0.78, 0.78)
    guaranteed = 2 if regime == "rare" else max(2, n // 6)
    points = []
    for i in range(n):
        if i < guaranteed:
            role, region = TARGET
        elif regime == "rare":
            role, region = rng.choice(("builder", "explorer")), rng.choice(REGIONS)
        elif regime == "skewed":
            role = "builder" if rng.random() < 0.85 else rng.choice(ROLES)
            region = "south" if rng.random() < 0.8 else "north"
        else:
            role, region = rng.choice(ROLES), rng.choice(REGIONS)
        target = (role, region) == TARGET
        x0 = _clip(rng.gauss(shift if target else -0.5 * shift, 0.30 if target else 0.48))
        coordinates = (x0,) + tuple(_clip(rng.gauss(0, 0.6)) for _ in range(d - 1))
        points.append(PopulationPoint(role, region, coordinates))
    return tuple(points)


def frequencies(d: int, k: int, *, seed: int = 91):
    if not 1 <= d <= 16 or not 1 <= k <= 32:
        raise ValueError("invalid frequency configuration")
    rng = random.Random(seed + 100 * d)
    # Pre-declared spectral target is a POSITIVE CONTROL: ECF contains this value.
    ecf = [(math.pi,) + (0.0,) * (d - 1)]
    ecf.extend(tuple(rng.uniform(-math.pi, math.pi) for _ in range(d))
               for _ in range(k - 1))
    # 2K independent one-phase cosine RFFs (same output dimension as K complex ECFs).
    rff = tuple((tuple(rng.uniform(-math.pi, math.pi) for _ in range(d)),
                 rng.uniform(0.0, 2 * math.pi)) for _ in range(2 * k))
    return tuple(ecf), rff


def labels(points: tuple[PopulationPoint, ...]) -> dict[str, float]:
    target = [p.features[0] for p in points if (p.role, p.region) == TARGET]
    if not target:
        raise ValueError("missing target stratum")
    return {
        "mean": (1.0 + statistics.fmean(target)) / 2.0,
        "tail": sum(x >= 0.5 for x in target) / len(target),
        "spectral": (1.0 + statistics.fmean(math.cos(math.pi * x) for x in target)) / 2.0,
    }


def features(points: tuple[PopulationPoint, ...], method: str, d: int,
             ecf_w, rff_w) -> tuple[float, ...]:
    """The feature function has no event IDs, roles-by-agent or secret data."""
    if method not in METHODS:
        raise ValueError("unknown method")
    if method == "no_summary":
        return ()
    selected = [p.features for p in points if (p.role, p.region) == TARGET]
    if not selected:
        raise ValueError("empty target group")
    if method == "global_mean":
        return tuple(statistics.fmean(p.features[j] for p in points) for j in range(d))
    if method == "group_mean":
        return tuple(statistics.fmean(x[j] for x in selected) for j in range(d))
    if method == "histogram8":
        bins = [0] * 8
        for x in selected:
            bins[min(7, max(0, int((x[0] + 1) * 4)))] += 1
        return tuple(v / len(selected) for v in bins)
    if method == "ecf":
        return tuple(component for omega in ecf_w
                     for component in empirical_cf(selected, omega))
    return tuple(statistics.fmean(
        math.cos(math.fsum(wj*xj for wj, xj in zip(w, x)) + phase)
        for x in selected) for w, phase in rff_w)


def solve_ridge(rows: list[tuple[float, ...]], targets: list[float],
                lam: float = 0.05) -> list[float]:
    """Deterministic intercept + ridge, pivoted Gauss-Jordan; no optimizer noise."""
    if not rows or len(rows) != len(targets) or len({len(r) for r in rows}) != 1:
        raise ValueError("invalid supervised design")
    p = len(rows[0]) + 1
    gram = [[0.0] * (p + 1) for _ in range(p)]
    for row, value in zip(rows, targets):
        x = (1.0,) + row
        for j in range(p):
            gram[j][p] += x[j] * value
            for q in range(p):
                gram[j][q] += x[j] * x[q]
    for j in range(1, p):
        gram[j][j] += lam * len(rows)
    for j in range(p):
        pivot = max(range(j, p), key=lambda r: abs(gram[r][j]))
        if abs(gram[pivot][j]) < 1e-12:
            raise ValueError("singular regression design")
        gram[j], gram[pivot] = gram[pivot], gram[j]
        factor = gram[j][j]
        gram[j] = [v / factor for v in gram[j]]
        for other in range(p):
            if other != j:
                factor = gram[other][j]
                gram[other] = [a - factor * b
                               for a, b in zip(gram[other], gram[j])]
    return [gram[j][p] for j in range(p)]


def _predict(coefs: list[float], x: tuple[float, ...]) -> float:
    return _clip(coefs[0] + math.fsum(a * b for a, b in zip(coefs[1:], x)),
                 0.0, 1.0)


def _percentile(samples: list[float], percent: float) -> float:
    values = sorted(samples)
    return values[math.ceil(len(values) * percent) - 1]


def run_case(*, n: int, d: int, k: int, regime: str, train_seeds: tuple[int, ...],
             test_seeds: tuple[int, ...]) -> dict:
    if set(train_seeds) & set(test_seeds):
        raise ValueError("train/test seeds overlap")
    if not train_seeds or not test_seeds:
        raise ValueError("empty train/test split")
    ecf_w, rff_w = frequencies(d, k)
    train = [make_episode(n, d, s, regime) for s in train_seeds]
    holdout = [make_episode(n, d, s, regime) for s in test_seeds]
    all_points = train + holdout
    truth = [labels(p) for p in all_points]
    # Full synthetic input fingerprint: role, region and exact float coordinate bits.
    digest = sha256()
    for episode in all_points:
        for point in episode:
            digest.update((point.role + "/" + point.region + ":" +
                           ",".join(v.hex() for v in point.features) + ";").encode())
        digest.update(b"\n")
    results = {}
    for method in METHODS:
        encode_wall = []
        cpu_start = process_time()
        encodings = []
        for episode in all_points:
            before = perf_counter()
            encodings.append(features(episode, method, d, ecf_w, rff_w))
            encode_wall.append(perf_counter() - before)
        train_x = encodings[:len(train)]
        test_x = encodings[len(train):]
        task_errors = {}
        for task in TASKS:
            coefs = solve_ridge(train_x, [row[task] for row in truth[:len(train)]])
            hold_labels = [row[task] for row in truth[len(train):]]
            predicted = [_predict(coefs, row) for row in test_x]
            errors = [(actual - pred)**2 for actual, pred in zip(hold_labels, predicted)]
            task_errors[task] = math.fsum(errors) / len(errors)
        results[method] = {
            "feature_width": len(encodings[0]),
            "holdout_mse": task_errors,
            "encoding_p50_seconds": statistics.median(encode_wall),
            "encoding_p95_seconds": _percentile(encode_wall, 0.95),
            "elapsed_process_cpu_seconds": process_time() - cpu_start,
        }
    return {
        "n": n, "d": d, "k": k, "regime": regime,
        "train_seeds": list(train_seeds), "holdout_seeds": list(test_seeds),
        "input_sha256": digest.hexdigest(),
        "target_group_mean_size": statistics.fmean(
            sum((p.role, p.region) == TARGET for p in ep) for ep in all_points),
        "models": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", type=int, default=100)
    parser.add_argument("--dim", type=int, default=4)
    parser.add_argument("--frequencies", type=int, default=8)
    parser.add_argument("--train-episodes", type=int, default=32)
    parser.add_argument("--test-episodes", type=int, default=16)
    parser.add_argument("--seed-start", type=int, default=3101)
    parser.add_argument("--regimes", nargs="+", choices=("balanced", "skewed", "rare"),
                        default=("balanced", "skewed", "rare"))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not (6 <= args.agents <= 1000 and 1 <= args.dim <= 16
            and 1 <= args.frequencies <= 32 and 4 <= args.train_episodes <= 128
            and 2 <= args.test_episodes <= 64
            and 0 <= args.seed_start < 2**31 - args.train_episodes - args.test_episodes):
        parser.error("bounded CPU-only study: N 6..1000, d 1..16, K 1..32")
    train_seeds = tuple(range(args.seed_start, args.seed_start + args.train_episodes))
    test_seeds = tuple(range(args.seed_start + 100000,
                            args.seed_start + 100000 + args.test_episodes))
    tracemalloc.start()
    started = perf_counter()
    results = [run_case(n=args.agents, d=args.dim, k=args.frequencies,
                        regime=regime, train_seeds=train_seeds, test_seeds=test_seeds)
               for regime in args.regimes]
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    report = {
        "schema": VERSION,
        "scope": "synthetic supervised readout; no reinforcement learning, no generalization proof",
        "environment": {"python": sys.version.split()[0], "os": platform.platform(),
                        "cpu_count": os.cpu_count(), "tracemalloc_peak_bytes": peak},
        "wall_seconds": perf_counter() - started,
        "cases": results,
        "caveats": [
            "Spectral target is aligned to ECF's first frequency (positive control).",
            "MSE on synthetic moment labels is not game reward or multi-agent learning.",
            "RFF/ECF feature budgets and fixed ridge readouts are experimental choices.",
            "No event-history, identity, owner or capability reconstruction.",
        ],
    }
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
