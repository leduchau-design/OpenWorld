# W2-P0 — Executable Mathematical Foundation

**Status:** Experimental reference implementation, not a production agent system.
**Related:** RFC-007, RFC-006, GitHub Issues #3, #11, #15.

## Implemented in this PR

- `ControlledKernel`: an action-indexed finite kernel family with common ordered supports and strict rejection of unknown actions.
- `FiniteKernel`: finite, row-stochastic Markov kernels with ordered, explicit source/target supports. `first.compose(after)` applies the first kernel followed by the second. Validation rejects negative, NaN, infinite, non-normalized and incompatible rows. Matrix multiplication and identity are exercised in unit tests.
- `predict_belief`, `condition_on_observation`, and `bayes_filter`: finite-state POMDP-style filtering. The observation likelihood is an emission probability conditional on state, not a distribution over states. Impossible observations raise an explicit error.
- `two_sign_process`: a closed-form example where q=0.9 and q=0.1 give the same one-time marginal characteristic function `cos(u)` but distinct lag-one correlations (+0.8 versus -0.8). Neither a marginal nor a random seed is sufficient to replay actual missing external observations.
- `total_variation` and `task_relative_equivalence`: compare *specified, aligned* finite query-outcome distributions. These do not prove sufficient state for all future actions or histories.
- `exact_outcome_from_counts`: toy counterexample proving that `(n, successes)` cannot generally determine an indexed Bernoulli outcome; returns `UNAVAILABLE` unless the summary logically determines every bit. It does not replace an exact evidence ledger.
- `ExponentialWeights`: a bounded-size (K expert weights) online Bernoulli forecast mixture. The caller predicts before calling `observe`, which updates the weights using Brier loss. No historical outcomes are stored by this learner.

## Mathematical guarantees and scope

For `K` fixed experts with their probabilities chosen before each outcome and squared losses in [0,1], the standard Hedge potential argument and the convexity of square loss give:

`sum_t (p_mix,t - y_t)^2 - min_k sum_t (p_k,t - y_t)^2 <= ln(K)/eta + eta*T/8`.

This statement compares to the **best fixed expert** in the declared pool. It neither implies that the mixture beats the strongest expert on every segment nor bounds errors caused by a misspecified environment. `eta`, expert family, and evaluation horizon are research choices, not universal constants. The implementation protects the log-weight softmax against numerical underflow using max subtraction.

## Boundaries and deliberate omissions

The pure module does not own authentication, permissions, evidence retention, source verification, user data or agent actions. Historical reality is governed by the exact-event ledger and RFC-006. The toy exact-history query is designed to expose insufficient compression, not synthesize evidence.

The ensemble is **not integrated into HM-P1e SQLite**; that integration needs a separate W1 migration, atomicity, replay and benchmark PR. Existing HM-P1e uses a heuristic winner-take-all gate. A mathematical regret statement here does not establish a production throughput improvement. Category theory packages, graph dynamics, agent society and model APIs remain deferred.

## Local verification

Run from the repository root (Python 3.11+):

```bash
python -m unittest discover -s tests -v
python scripts/check_repository.py
```

Independent evaluation must report all tests including existing W1/W5 suites on the same SHA, environment versions, stable/shift/noise negative results, WAL+SHM bytes, checkpoint recovery, p95 latency, and unavailable exact-history queries. Do not merge solely on the basis of this document.
