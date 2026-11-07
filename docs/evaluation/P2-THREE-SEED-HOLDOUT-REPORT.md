# P2 Three-Seed Stateful Cooperation — Measured GitHub CI Evidence

**Experimental, SIMULATED, one trusted owner.** Not an independent audit, not general multi-agent reinforcement learning, not bilateral consent and not an emergent civilization.  
**Source commit:** `a3e3c03a583689fe83b2b784fae401d7241228e4`, tested in [Python 3.11 GitHub Actions run 40813009511](https://github.com/CocAgent/OpenWorld/actions/runs/40813009511/job/123247500695) (**367/367 repository tests PASS**).  
**Raw results:** [P2-THREE-SEED-HOLDOUT.json](P2-THREE-SEED-HOLDOUT.json).

## Actual experiment

- 30 W3 agents registered: **10 donor decision makers**, 10 recipients following fixed rules, 10 passive group-context actors; all under one synthetic owner.
- Three independent train/holdout world seeds 5101, 5102 and 5103; **25 training episodes and 12 holdout episodes per seed/method**, two W3 ticks per episode.
- An accepted resource transfer at tick 0 changes whether a recipient can acknowledge at tick 1. Reward is computed only after that actual SIMULATED event: one for acknowledgment, minus 0.25 per accepted transfer.
- Each trained method sees 250 chosen-action feedback updates per seed; evaluated on 120 decisions per seed (**360 decisions per method across three seeds**).
- Every held-out W3 episode verifies replay and resource conservation. Methods share the same world mode hash within each seed.

## Observed average holdout reward per decision

| Policy or population feature | Actual result |
|---|---:|
| Fixed always hold | 0.4861 |
| Fixed always transfer | 0.7500 |
| No population summary | 0.7500 |
| Role-group mean | 0.7500 |
| ECF at one fixed frequency | 0.8056 |
| Four-bin histogram | **0.8715** |
| Full-information task oracle (not trained) | **0.8715** |

The conditional oracle is computed analytically from each synthetic scenario's initial need mode. It is **used in the test assertion and this report, not as an input to the learner**.

## Scientific interpretation

The need/funded population states are deliberately constructed with **equal group totals and different balance histograms**. This is an informative negative control for the group mean, not proof that all mean-field approaches fail. The four-bin histogram reveals the task-relevant balance mode and reaches the analytical best policy for these selected seeds. The ECF sketch is based on **one chosen frequency and quantized components**, and gets less reward than histogram in this implementation. There is no principled evidence here for an ECF default or a learned population encoder.

**What has improved over P1:** The chosen donor action really changes the W3 state and can cause a different event in the following tick; the reward is obtained *after* that event, not directly from a synthetic per-tick oracle label. This is action-dependent delayed contextual learning embedded in W3.

**What remains unproven:** Recipients do not learn, action/reward horizons are only two ticks, worlds reset each episode, there is no W1 private episodic memory, no institution creation, no adversarial partner transfer, no endogenous market dynamics and no independent W0/W4 security verification. The feature bins were selected for this synthetic task. A 3-seed, 360-decision sample is not evidence of 1,000 active learners, federation, stable game-theoretic cooperation or human-level autonomous societies.

## Admission

A subsequent, distinct benchmark must evaluate **multiple interacting learned partner policies**, longer action-to-state consequences, rare damaging events, world/partner distribution shifts and wall/CPU/RSS/latency costs. Compare against simple rules under matched action opportunities, and protect private group statistics. Do not close [Issue #51](https://github.com/CocAgent/OpenWorld/issues/51) or [Gate #11](https://github.com/CocAgent/OpenWorld/issues/11) on this positive control alone.

**Provenance:** Numbers were parsed from the CI log of exact source commit `a3e3c03a583689fe83b2b784fae401d7241228e4`, not fabricated or estimated. The documentation commit that embeds this report is a distinct SHA and requires its own checks.
