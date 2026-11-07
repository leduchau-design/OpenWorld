# P3 Three-Seed Multi-Learner Holdout — Measured Negative Result

**Source:** [GitHub Actions Python 3.11 job](https://github.com/CocAgent/OpenWorld/actions/runs/40815028595/job/123253975518), exact source commit `284289b9f814cb3f19f42876db879b7a9170e6ec`: **394/394 repository unit tests PASS**, including the measured subprocess.  
**Raw machine-readable measurement:** [P3-THREE-SEED-RESULTS.json](P3-THREE-SEED-RESULTS.json).  
**Status:** Synthetic evidence only. **No claim** of convergent multi-agent RL or autonomous cooperation.

## Experiment actually run

- Seeds **7101–7103**, same initial W3 fingerprints across each of the **six** compared methods within a seed.
- **30 registered synthetic agents**, of which **20 each have independent two-arm policies** in learned variants (10 donors and 10 recipients). The remaining 10 are passive context actors.
- **8 training episodes + 4 frozen held-out episodes per seed/method**, each episode lasting **4 donor/receiver rounds = 8 W3 ticks**.
- Synthetic sender/receiver incentives defined in the P3 design, not an external economic objective.
- All transfers pass through the existing same-owner W3 PopulationRouter and GuardedWorldGateway. Every episode checks **deterministic replay and resource conservation**. Two fixed reference policies plus four separately learned methods.
- The benchmark test prints all seed-level cases, actual transfer counts, returns, donor/recipient reward, and initial-world hashes; values below are arithmetic means over **three held-out seeds**.

## Actual held-out reward per decision

| Method | Donor | Recipient | Joint |
|---|---:|---:|---:|
| `hold` | 0.0000 | 0.0000 | 0.0000 |
| `always_reciprocate` | 0.6000 | 0.5500 | 0.5750 |
| `no_summary` | 0.2070 | 0.1898 | 0.1984 |
| `group_mean` | 0.0870 | 0.0798 | 0.0834 |
| `histogram4` | 0.0700 | 0.0642 | 0.0671 |
| `ecf` | 0.0475 | 0.0435 | 0.0455 |

**Key negative:** The scripted always-offer-and-reciprocate control wins (**0.5750 joint**) over every independently learned method. The best learned method **without any population summary** obtains only **0.1984** joint reward. Adding group mean, histogram or ECF **reduces** results in this short training budget. ECF's joint result is **0.0455**. Do not select ECF, mean-field learning or complex representation as default based on this experiment.

## Interpretation and caveats

1. **Learning is implemented, but winning is not established.** Both donors and recipients update their own policy tables after each two-tick action/response sequence. Test success verifies controlled mechanics and recorded results, not a superior policy.
2. **Sparse tabular state is costly in samples.** Eight training episodes give each agent 32 action choices, while adding group features increases the number of possible contexts. The no-summary variant likely generalizes better across these limited repeated contexts. This is a plausible *hypothesis*, not an independently isolated causal conclusion.
3. **The scripted control is unusually favorable** because reward rules were explicitly designed for donation-plus-reciprocity. It is not a fair demonstration of learned altruism, realistic trade or sustainable economy.
4. **World resets between episodes**, though each episode persists eight ticks. Partner agents learn simultaneously during training, so the learning environment is nonstationary; no convergence result follows from three seed averages.
5. Group features are computed by a **single trusted synthetic owner**. Small-group means, histograms and ECFs have no privacy guarantee. No real-user data or cross-owner permission is involved.
6. No holdout partner-policy shift, sustained institutional lifecycle, independently authenticated remote identity, W1 personal memory, genome evolution, crash recovery proof or large active-agent throughput measurement is included.

## Next falsifiable decision

Keep [Issue #51](https://github.com/CocAgent/OpenWorld/issues/51) and independent [Gate #11](https://github.com/CocAgent/OpenWorld/issues/11) **open**. Before a new model family, try an **actionable sample-efficiency ablation** on the same W3 world: hold observation dimensions fixed, compare one role-shared tabular learner with independent learners, train for more episodes under equal total action/update budgets, and evaluate on **new seeds + adversarial partner policy shifts**. Record cooperation success and failures, CPU/RSS and policy-table size. If a simple fixed policy still wins, retain the fixed policy and report that result.

Do not optimize the test label to promote Fourier-based features. Keep existing W0/W4 authority and W3 exact-state boundaries unchanged.

**Evidence provenance:** JSON is extracted verbatim as structured fields from the CI output of exact source SHA `284289b9f814cb3f19f42876db879b7a9170e6ec`. This report's commit is distinct and requires its own validation. No new numerical result is invented by this documentation edit.
