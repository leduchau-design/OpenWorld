# HM-R0 — Parametric, Markov and spectral memory representation study

**Status:** Executable **synthetic research experiment**, NOT an accepted HyperMemory architecture or independently validated performance result. **Scope:** W1/W2/W5 additive files only. HM-P1e, protected exact-event handling, capability guards, W3, public package exports and production defaults are unchanged. Related: [RFC-007](../math/RFC-007-OPENWORLD-MATHEMATICAL-FOUNDATIONS.md), [R0 gates](../R0-INTEGRATED-AGENT-VERTICAL-SLICE.md), [independent gate #11](https://github.com/CocAgent/OpenWorld/issues/11).

## Decision and falsifiable question

Is a small representation of a **specified synthetic Bernoulli partner-response process** sufficient to improve prequential forecasts **and** decisions under changing regimes, compared with simpler summary statistics, after measuring CPU, on-disk size and missing-feedback limitations?

**Hypothesis, not conclusion:** first-order transition counts help under genuine temporal dependence; discounted estimates help under regime shift; a spectral phase sketch *may* help only when its assumed period matches relevant structure. Simpler Beta counts may win on stationary or noisy data. No candidate is eligible to replace HM-P1e unless held-out decision utility net of actual cost improves and protected evidence is retained.

## Predeclared five candidates

| Name | Kept state | Important limit |
|---|---|---|
| `full_history` | Every **observed synthetic** tick/outcome pair | Exact synthetic-label queries possible; unbounded growth and reads |
| `beta_counts` | IID successes and observations, Beta(1,1) prior | IID forecast identical to full-history Beta; exact past tick `UNAVAILABLE` |
| `discounted` | Exponentially weighted success and observation mass (`0.85` per *observed update*) | Cannot reconstruct old labels; behavior depends on sample gaps |
| `markov` | 2x2 observed adjacent transition counts, marginal Beta fallback | Never treats a gap due to hold as a known transition |
| `markov_fourier` | Markov state plus three linear Fourier phase weights | Period 12 is **pre-specified knowledge**, not an inferred law; period 7 is a negative control |

The spectral candidate is an online phase-feature regression using sine/cosine of time, **not** an empirical characteristic function of the marginal Bernoulli distribution. The latter is fully determined by the Bernoulli probability and adds no new information. No Riemann zeta function is used: it is not justified by this task. A frequency sketch of arbitrary order does not retain temporal order, provenance or exact history.

## Two experiments, kept separate

1. **Fully observed prequential forecast**: every model predicts `y_t` **before** being shown the same synthetic `y_t`. Report per-seed Brier, log loss, five-bin ECE and serialized state. All receive equal information. This **does not** represent a censored real agent.
2. **Censored-feedback decision**: each model uses the same fixed offer threshold `0.4` and forced probe every seventh opportunity *only when it would otherwise hold*. A toy offer earns `+0.6` on success or loses `0.4` on failure; abstaining earns zero and yields **no observation/update**. Compare against `fixed_hold` (zero utility) and `fixed_offer`. Report offers, actual observed feedback, model updates, forced probes, gross failure exposure and total utility. Strategies share the exact same exogenous potential-outcome tape per seed, but models never receive unoffered outcomes. This is an **action-independent synthetic partner**, not game-theoretic MARL, W3 transfer, or true risk authorization.

Regimes: stable, abrupt collapse, recovery, known periodic phase, persistent two-state Markov, anti-persistent Markov and pure noise. The two Markov regimes have comparable long-run marginal frequencies but different temporal dependence. The periodic scenario is intentionally **favorable** to the disclosed period-12 Fourier candidate. No attempt is made to tune algorithms against benchmark output.

## Commands (local CPU, Python 3.11+, standard library)

```sh
python -m unittest discover -s tests -p 'test_memory_representation_study.py' -v
python -m unittest discover -s tests -v
python scripts/check_repository.py

# Full preregistered study: 7 regimes x 5 seeds, raw output never overwritten
python benchmarks/hm_representation_study.py --seed-start 41001 --seeds 5 --steps 120 --period 12 --out hm-r0-evidence.json

# Mandatory model-misspecification control, do NOT replace primary result
python benchmarks/hm_representation_study.py --scenario periodic --seed-start 41001 --seeds 5 --steps 120 --period 7 --out hm-r0-wrong-period.json

# Cheap smoke run (no disk profile); never cite as performance evidence
python benchmarks/hm_representation_study.py --scenario collapse --steps 24 --seeds 1 --no-disk-profile
```

Output contains all per-seed scores, seed/scenario/tape SHA256, preset knobs, host Python/SQLite/OS, and representative SQLite snapshot overhead. Save raw stdout/stderr, exact commit SHA, CPU and filesystem for independent replication; output JSON itself is not an external attestation. Use at least one **new disjoint seed family** in an independent run before claiming generalization. Decide primary baselines/acceptance thresholds before seeing those new results.

## Disk and measurement honesty

The physical profile writes each candidate's JSON state to a **separate SQLite WAL database with `synchronous=FULL`**, one transaction per tick; reports online peak/end and post-checkpoint file+WAL+SHM bytes plus p95 snapshot-write time for one representative collapse case. These are state-store costs, **not total compliant HyperMemory costs**: a protected exact-event ledger is required separately for any authorized real operation, irrespective of which predictive representation wins. A JSON snapshot of full synthetic labels is not equivalent to provenance-authenticated event storage. The benchmark does not establish power-loss recovery or multi-store atomicity. CPU timings isolate model predict/update but not process RSS, cold-start costs or real shared storage overhead.

## Acceptance / stop rules

- **A1 Correctness**: no look-ahead update; hold reveals no outcome; missing observations cannot be treated as adjacent Markov transitions; deterministic seeds; malformed values rejected.
- **A2 Information honesty**: `full_history` and `beta_counts` produce identical Beta(1,1) forecasts on a shared stream; `beta_counts` must return `UNAVAILABLE` for indexed history.
- **A3 Fairness**: fixed-hold and fixed-offer controls, common random numbers, identical probe/threshold schedules for learned candidates, raw negative cases and matched decision opportunities.
- **A4 Cost**: compare resource footprint including SQLite WAL/SHM and timing; do not equate JSON state length to actual disk size or CPU cost to wall time.
- **A5 Review**: document failure regimes, wrong-frequency ablation and independent replay on pinned commit; do **not** close Issue #11 or select a default from author-run data.

**Failure/stop:** observed future labels leak into predictions, exact provenance is rewritten as inferred/synthetic, a model learns after hold, the spectral method is claimed universally superior, or results are reported without raw provenance and independent review. Keep HM-P1e as the deployed baseline and preserve earlier P1–P6 negative results.

## Reversibility

Remove the two optional research code files, test file and this document. No schema migrations, default imports, CI billing, user data or existing runtime pathways are changed.
