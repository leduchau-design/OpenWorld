# Gate #11 — Integrated CI and W5 evidence (2026-10-28)

**Status:** Partial gate verification. Operational and scientific acceptance remain **OPEN**.  
**Project:** [OpenWorld](https://github.com/CocAgent/OpenWorld) · [Gate #11](https://github.com/CocAgent/OpenWorld/issues/11) · [W1/W5 #20](https://github.com/CocAgent/OpenWorld/issues/20)

## 1. Verified integrated-main run

| Evidence | Result |
|---|---|
| Main SHA | `9c5265c341bfa9cca61faa776b1d0474c5f57bc1` |
| GitHub Actions run | [40726994438](https://github.com/CocAgent/OpenWorld/actions/runs/40726994438) |
| Workflow | `Python validation`, single supported Python 3.11 job |
| Syntax check | PASS |
| Complete repository test discovery | **108 tests PASS** |
| Repository layout | PASS |
| Job/workflow conclusion | **SUCCESS** |
| Deployment | None |

This is a GitHub-hosted test execution of **the actual integrated `main` tree**, not a test count inferred from isolated workstream runs.

**Previous CI false failure:** [run 40724407378](https://github.com/CocAgent/OpenWorld/actions/runs/40724407378) recorded **108 pytest PASS on Python 3.11**, but failed overall when obsolete Python 3.9 failed during interpreter setup. [PR #28](https://github.com/CocAgent/OpenWorld/pull/28) removed unsupported Python versions, unnecessary package installation and duplicated jobs. Its PR workflow and the resulting `main` workflow both succeeded.

## 2. Independent W5 synthetic rerun

The committed W5 runner `benchmarks/w5_ensemble_comparison.py` was rerun in a local reconstruction of the W1/W5 source using:

```bash
python benchmarks/w5_ensemble_comparison.py \
  --agents 30 --days 40 --seeds 5 --seed-start 3101 \
  --out local-w5-rerun.json
```

Environment: Python 3.13.5 · SQLite 3.46.1 · Linux x86-64, glibc 2.41. 25 seed/scenario runs, **30,000 synthetic agent updates per estimator**. No real observations, paid APIs or GPU were used. The per-scenario **Brier averages match exactly** the existing checked-in synthetic [raw report](W5-ENSEMBLE-LOCAL-RESULTS.json).

| Scenario | Static | Fast | Slow | HM-P1e gate | Ensemble |
|---|---:|---:|---:|---:|---:|
| Stable | **0.178968** | 0.195394 | 0.179392 | 0.183880 | 0.181345 |
| Abrupt drift | 0.263382 | **0.201832** | 0.239141 | 0.209089 | 0.220871 |
| Gradual drift | 0.263591 | **0.244962** | 0.253160 | 0.251834 | 0.248671 |
| Alternating | 0.264552 | **0.225273** | 0.257584 | 0.234071 | 0.241189 |
| Noise | 0.263540 | 0.269828 | **0.263057** | 0.268278 | 0.263116 |

Lower Brier is better. Ensemble is **not** the best method in any of these five scenario averages. Its performance is weaker than the fast predictor on abrupt drift. **Keep the ensemble opt-in.**

### Resource warning

For the **stable** scenario on this rerun, mean measured write seconds were full-history **0.095**, HM-P1e gate **0.128**, ensemble **0.234**. Original run timings were lower; timings vary with filesystem and runtime load. Observed peak SQLite online bytes (main DB + WAL + SHM) remained about **366 KiB**, **563 KiB**, and **1,077 KiB**, respectively. These figures are a small synthetic workload, not an agent-scale capacity estimate.

A full-history log answers exact-history queries that compact synthetic predictors cannot. Do **not** interpret smaller prediction-state vectors as equivalent lossless memory.

## 3. Why Gate #11 remains open

The main test suite confirms implementation behavior covered by its tests, not real-world authenticity or broad safety. Remaining requirements:

- [ ] Independent authenticated provenance and trust anchors; an in-DB SHA256 digest alone is not an external witness.
- [ ] Security tests under malicious tool input, cross-process access and owner-spoofing.
- [ ] Multi-process concurrency, backup restore, long-lived SQLite WAL readers and power-loss recovery.
- [ ] Peak process RSS, attribution of CPU cost per system, and p50/p95 latency over repeated runs.
- [ ] Explicit human consent, deletion/retention, and operator incident handling before real-user data.
- [ ] A task-relative information-loss study including exact-history `UNAVAILABLE` responses.

**Decision:** This checkpoint passes **integrated code unit tests and benchmark reproducibility**; it does **not** authorize production deployment, default ensemble migration or any million/billion-agent scaling claim.
