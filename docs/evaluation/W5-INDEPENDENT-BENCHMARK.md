# W5 — Independent HyperMemory Evaluation Protocol

**Status:** Proposed experiment implementation; not an accepted performance result.  
**Tracks:** W5 evaluation and W1 HyperMemory · Issues #6 and #2

## Research question

For a fixed binary synthetic prediction task, when does a cost-gated predictor outperform long-horizon and discounted baselines, and at what measured runtime/disk cost?

The benchmark does **not** compare equivalent historical recall: a full event log can answer exact questions about every step; a compact predictive state cannot. No universal memory-compression claim may be drawn from the result.

## Predeclared scenarios and metrics

Scenarios: `stable`, `abrupt`, `gradual`, `alternating`, `noise`.

Use at least five held-out RNG seeds for final evaluation and report all per-seed results (including negative cases). Do not tune the gate penalty using holdout seeds.

Quality baselines: (1) full-history + static beta-smoothed estimator, (2) standalone fast discounted estimator, (3) HM-P1e cost-aware gated estimator. A slow standalone estimator, all-static no-ledger reference and historical HM-P1c/HM-P1d reproduction remain future work.

The runner measures: Brier score, gate selection counts, write time, p95 batch latency, SQLite main-file+WAL+SHM online bytes, peak observed end-of-day bytes, post-checkpoint bytes and combined CPU time. Memory RSS, per-method CPU attribution and fsync-level power-loss testing are not measured.

## Experiment execution

Requires Python 3.11+ and SQLite, no external libraries or API:

```bash
python -m unittest discover -s tests -v
python scripts/check_repository.py
python benchmarks/w5_memory.py --agents 100 --days 60 --seed 2026 --scenario abrupt
python benchmarks/w5_memory.py --agents 100 --days 60 --seed 2027 --scenario stable
```

To preserve comparability, both SQLite databases use `WAL` and `synchronous=FULL`, and both commit once per simulated day. Prediction is made **before** each observation. The compact system uses only synthetic `SIMULATED` reconstructable telemetry; real-world observations and protected events must not be silently compacted.

## Required interpretation

A lower Brier score on a regime-shift workload is not sufficient to claim global superiority. The gate may lose to the static estimator in stable or noisy environments; the benchmark intentionally exposes those cases.

Report machine CPU, memory, OS, Python/SQLite versions and commit SHA with results. Re-run locally on the exact merged SHA; passing unit tests in one branch does not prove all tests pass in another. Preserve failed runs and publish limitations.

## Independent safety gates

- Protected events remain byte-identical under local transaction/restart (W1 tests).
- Cross-owner reads/writes fail closed (W1 tests).
- Synthetic output is never labeled verified observation (W0 provenance contract).
- Workloads, seeds and baselines are auditable (W5 tests).
- WAL online size and checkpoint size are both reported; neither is silently substituted for the other.
- Before production or user data: add key/identity verification, backup restoration, consent/erasure policy, memory poisoning tests, and multi-writer concurrency tests.

**Do not mark HM-P1e scientifically or operationally accepted until the gates are independently executed and reviewed.**
