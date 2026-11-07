# W5 — HM-P1e ensemble independent synthetic benchmark

**Status:** Exploratory measurement, not production acceptance.  
**Date:** 2026-10-28  
**Workstreams:** W5 Evaluation and W1 HyperMemory · Issues #6, #20, #11.

## Experimental design

The frozen prototype uses 30 agents, 40 simulated steps, five consecutive seeds (3101–3105), five scenarios and **30,000 total agent updates per estimator**. It compares predictions using the **same observations and prior state**: full-history static Beta(1,1); fast discounted; slow discounted; HM-P1e loss gate; and the opt-in ExponentialWeights ensemble. Predictions are collected **before** observing each outcome. Every SQLite store uses WAL and `synchronous=FULL`, with one transaction per simulated day; no external service or personal data is used.

This measures synthetic binary outcome forecasting, not general cognition or semantic memory. The full-history database retains exact historical observations, while compact predictors intentionally do not retain their synthetic per-step history, so these are **not equivalent query-capability systems**.

## Mean Brier across five seeds (lower is better)

| Scenario | Full-history static | Fast discounted | Slow discounted | HM-P1e gate | New ensemble |
|---|---:|---:|---:|---:|---:|
| stable | 0.178968 | 0.195394 | 0.179392 | 0.183880 | 0.181345 |
| abrupt | 0.263382 | 0.201832 | 0.239141 | 0.209089 | 0.220871 |
| gradual | 0.263591 | 0.244962 | 0.253160 | 0.251834 | 0.248671 |
| alternating | 0.264552 | 0.225273 | 0.257584 | 0.234071 | 0.241189 |
| noise | 0.263540 | 0.269828 | 0.263057 | 0.268278 | 0.263116 |

### Main findings

- New ensemble improves over the current HM-P1e gate on **stable**, **gradual** and **noise** scenarios under this synthetic setup, but loses on **abrupt** and **alternating** regimes.
- The **best method overall changes by scenario**. Static is strongest on stable; fast discounted is strongest on abrupt, gradual and alternating; slow discounted is strongest on noise (by a narrow margin).
- The ensemble must **not** replace HM-P1e by default. Opt-in experimentation is justified, production enablement is not.

## Operating cost: stable scenario (five runs, mean)

| Measure | Full history | HM-P1e gate | Ensemble |
|---|---:|---:|---:|
| Measured write time (s) | 0.039 | 0.081 | 0.156 |
| Observed online peak DB+WAL+SHM (KiB) | 366.0 | 563.1 | 1077.3 |
| After checkpoint DB+WAL+SHM (KiB) | 52.0 | 68.0 | 92.0 |

Physical on-disk footprint and write latency are not directly comparable to mathematical per-agent **O(K)** predictor state. W1's exact-event lane and SQLite indexes add real storage. These values are local-synthetic workload measurements, not per-agent production projections.

## Reproducibility

Run from the integrated W1+W5 worktree:

```bash
python -m unittest discover -s tests -v
python benchmarks/w5_ensemble_comparison.py --agents 30 --days 40 --seeds 5 --seed-start 3101 --out results.json
```

Machine at measurement: Python 3.13.5; SQLite 3.46.1; Linux-6.18.55-x86_64-with-glibc2.41. Exact raw per-seed observations, measured latency, storage and loss metrics are included in [W5-ENSEMBLE-LOCAL-RESULTS.json](W5-ENSEMBLE-LOCAL-RESULTS.json). Do not treat the raw JSON as official CI attestation.

## Unresolved gates

- Execute tests and benchmarks on the **exact merged main SHA** in an independent clean environment; current runs are local experimental evidence.
- Compare CPU attribution, RSS, true cold recovery, crash injection at power-loss boundaries, verified source identity and multi-writer access.
- Test policy changes, old-state migrations, backup and restore under tampering.
- Evaluate real task-relative memory fidelity, including refusal of unavailable exact queries.
- Get owner/second-contributor review before acceptance. W0/W1/W5 Gate #11 remains open.
