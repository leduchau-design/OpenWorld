# HM-W5 — New holdout family (2026-11-03)

**Status:** Proposed synthetic validation protocol; not a production or independent
human replication claim. The owner-approved [HM-R0 study](HM-R0-PREDICTIVE-REPRESENTATION-STUDY.md)
is already merged in PR #74. This follow-up records a **previously unused seed
family** to test model fragility without changing default HyperMemory weights,
backend, authorization or evidence retention.

## Prespecified environment

- Seven existing scenarios: `stable`, `collapse`, `recovery`, `periodic`,
  `markov_persist`, `markov_flip`, `noise`.
- Five seeds: `73101,73102,73103,73104,73105`, `120` steps each.
- Five existing predictors: `full_history, beta_counts, discounted, markov,
  markov_fourier`, plus `fixed_hold` and `fixed_offer` decision baselines.
- Evaluate period `12`, and an **identical fresh seed family** on the periodic
  scenario with intentionally wrong period `7`.
- Full-feedback forecast and censored-feedback decisions remain separately labeled.
  No prediction may use the current outcome; no learner may observe a held action
  outcome. All utility is toy, action-independent synthetic reward.
- Do **not** promote a model or alter tuning based on these holdout results.
  No threshold for declaring a winner has been established; document losing
  cases, intervals/uncertainty and budget limitations before a decision.

## How to run and find evidence

On a local environment with Python 3.11+, from repository root:

```sh
OPENWORLD_SLOW_TESTS=1 python -m unittest discover -s tests -p 'test_hm_fresh_holdout_evidence.py' -v
```

CI runs this test because `OPENWORLD_SLOW_TESTS=1` is already enabled by
merged PR #76. In GitHub Actions output, find the lines
`OPENWORLD_HM_FRESH_HOLDOUT_SHA256` and
`OPENWORLD_HM_FRESH_HOLDOUT_JSON`. The JSON includes **all 35 cases**, tape
digests, forecasting and decision metrics, physical SQLite test measurements
for one case, and the five-case wrong-period control. Copy the raw log and record
the exact PR SHA before citing results. SHA256 checks the raw record's bytes;
it is **not** a signature or proof of external originality.

The test asserts only invariants and information fairness, not that any
candidate beats a baseline. Model selection remains blocked on independent
reproduction, holdout confidence, true storage cost including shared protected
exact ledger, owner authorization and task-relative reward.

## What this does not establish

This is **a fresh-seed execution of the same implementation in CI**, not a
second person reproducing the experiment, not a real-data or production
benchmark, and not a test of persistent multi-owner identity or exactly-once
World/HyperMemory execution. Retain negative results and keep independent
Gate #11 open.

**Rollback:** Remove this optional slow-test fixture and this note; no schema,
default tests, model code, billing or runtime change.
