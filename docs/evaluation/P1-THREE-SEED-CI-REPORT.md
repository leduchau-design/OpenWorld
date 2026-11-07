# P1 — Three-Seed Measured CI Result (Synthetic Contextual Bandits)

**Evidence type:** GitHub Actions **actual execution** of six bounded holdout cases, not a manually predicted result or independent MARL benchmark.  
**Pinned SHA:** `cc011d6c63d79a3512fe4540a483592e1cac19d3` (before embedding this report)  
**Runner:** Python 3.11.17; Linux-7.0.0-1017-azure-x86_64-with-glibc2.43, 4 logical CPUs reported.  
**Job:** [Python 3.11, 298/298 tests PASS](https://github.com/CocAgent/OpenWorld/actions/runs/40800755089/job/123208032704).  
**Raw evidence:** [P1-THREE-SEED-CI-RESULTS.json](P1-THREE-SEED-CI-RESULTS.json)

## Experiment executed

Exactly 30 synthetic agents, three balanced roles (10 each), two independently evaluated tasks (`mean`, `spectral`), seeds **4103, 4104, 4105**, 100 training ticks, 40 holdout ticks; **3,000 chosen-action SGD updates and 1,200 frozen-policy holdout actions per seed/method/task**. No external model API, no W3 world dynamics, and no user data.

All four representations saw identical synthetic scenes and common deterministic potential outcomes. Results below are averages of the **three seeds**, measured with the same per-role online logistic bandit and exploration schedule. Accurate/incorrect actions receive expected probabilities 0.85/0.15; action regret is calculated relative to the simulated hidden oracle.

## Measured results

| Representation | Mean accuracy | Spectral accuracy | Mean regret/action | Spectral regret/action | Mean p95 sketch (ms) | Spectral p95 sketch (ms) |
|---|---:|---:|---:|---:|---:|---:|
| No summary | 45.8% | 45.9% | 0.379 | 0.379 | 0.019 | 0.020 |
| Group mean | 100.0% | 46.2% | 0.000 | 0.377 | 0.026 | 0.027 |
| Histogram 8 | 100.0% | 100.0% | 0.000 | 0.000 | 0.151 | 0.153 |
| ECF at π | 100.0% | 100.0% | 0.000 | 0.000 | 0.396 | 0.396 |

## Interpretation and design choice

- **Mean task:** group mean, histogram and ECF all reached **100%** holdout action accuracy. A much simpler 1-value group mean sufficed; ECF provided **no measured accuracy gain** and was slower to construct in this run.
- **Spectral task:** ECF and 8-bin histogram both reached **100%**; group mean and no-summary remained near chance. The histogram captured the synthetic bimodality without needing complex-valued ECF.
- **Comparative efficiency:** the observed ECF p95 sketch time was roughly **15.0×** group mean and **2.6×** histogram on this runner, *at different feature widths* (ECF=2, histogram=8, group mean=1). The current ECF implementation revalidates/allocates input sequences for each sketch, so this is **implementation-specific**, not a theoretical complexity advantage.
- **Positive-control bias:** the mean label is generated directly from a group mean; the spectral label directly from the ECF's cosine component at π. Perfect accuracy therefore establishes the learning loop is capable of using deliberately informative features, **not** that either representation solves realistic strategic learning.
- **Conclusion:** **do not promote ECF as a default**. Prefer an adaptive representation-selection experiment, starting with group mean/histogram, and require a clearly documented task where ECF wins on *held-out behavior or policy regret after including CPU/inference cost*.

## Important negative findings and open gates

1. The environment regenerates exogenous synthetic fields each tick; actions do not change future world states or the behavior of other agents. This is **contextual-bandit learning**, not MARL, an evolving ecosystem, a persistent economy or a demonstration of civilization emergence.
2. 30 agents and 1,200 holdout actions per case do not establish performance at 1,000 or 10,000 simultaneously active models; shared role policy does not eliminate inference cost.
3. All results are one GitHub runner and three development-selected seeds. There is **no independent external review**, no uncertainty intervals, no held-out partner agents and no adversarial regime-shift training.
4. The `rare` regime, two-member groups, graph topology ablations and privacy leakage have tests but **were not part of this six-case measured CI benchmark**. Never claim rare-group privacy or tested social-network resilience from it.
5. Sketch p95 is over 140 scene-encoding samples per method/seed, not W3 server tick p95 or end-to-end response latency. `tracemalloc_peak_bytes` is not RSS.
6. The genome records only typed traits, policy artifact content digest and lineage. It conveys neither identity, exact history, owner rights nor independently authenticated agent actions.

**Admission recommendation:** accept only as a bounded P1 experimental evidence artifact subject to owner review. Keep [Issue #44](https://github.com/CocAgent/OpenWorld/issues/44) and independent [Gate #11](https://github.com/CocAgent/OpenWorld/issues/11) OPEN. Next: P2 bounded sparse-world multi-agent dynamics with action-dependent outcomes, plus histogram/mean/ECF ablations and risk/compute accounting.

**Rollback:** remove this report and JSON and revert the P1 prototype PR; no production/world schema migration.
