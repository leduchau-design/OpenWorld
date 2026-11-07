# W2 MathKernel — P0 Implementation and Verification Gates

**Related:** [RFC-007](RFC-007-OPENWORLD-MATHEMATICAL-FOUNDATIONS.md) · [Issue #3](https://github.com/CocAgent/OpenWorld/issues/3) · [Gate #11](https://github.com/CocAgent/OpenWorld/issues/11)

## Scope: an executable mathematical reference, not an agent platform

Phase 1 implements pure finite-state, CPU-only, dependency-light reference functions. All new code and tests must use English. Do not connect to model APIs, personal user data, live servers, AHappy or paid CI.

### Deliverable A: finite controlled stochastic kernels

- Define a finite typed support and an explicitly declared transition matrix for each controlled action.
- Reject NaN, negative, non-normalized probabilities, unknown actions or mismatched source/target supports.
- Verify identity, composition, normalization and associativity under documented float tolerance.
- Include deterministic as well as non-degenerate stochastic examples.

### Deliverable B: finite POMDP filter

- Implement prediction and observation-conditioning as separate inspectable operations.
- Test a hand-computed two-state posterior and its normalization.
- Return an error on zero-evidence likelihood, never invent a replacement posterior.
- Document that observed state is *not* a claim of authenticated external-world evidence.

### Deliverable C: temporal dependence counterexample

- Simulate or calculate a two-sign Markov chain with `q=0.9` vs `q=0.1`.
- Show that both have symmetric one-time distributions while their lag-one correlation differs by `1.6`.
- Demonstrate that a characteristic function of one marginal is insufficient for replay.
- Pin PRNG version/seed only for simulation; never synthesize a missing observation as recorded fact.

### Deliverable D: predictive-memory distortion protocol

- Specify a toy task family, forecast horizon, loss and observation model.
- Compare full history, static sufficient counts, discounted counts and HM-P1e adaptive gate.
- Include an exact-history query for which the compact representation MUST return `UNAVAILABLE`.
- Measure online DB+WAL+SHM, CPU, p95 and cold-recovery cost, and distinguish conceptual information from physical bytes.
- Include a noise/shift negative case in which a method loses to a simpler baseline.

### Gate to move to W3/W4

- [ ] W0 RFC-006 schema assumptions reviewed; no silent interface drift.
- [ ] Pure MathKernel tests run and pass on the exact integrated commit.
- [ ] Existing W1/W5 tests independently run under Gate #11, or failures disclosed.
- [ ] No protected event or trust boundary is bypassed.
- [ ] At least one counterexample and one deliberate failing-fidelity query documented.
- [ ] Research outputs reproducible without GPU or paid services.

## Suggested PR sequence

1. `feat/math-kernel-finite` — kernels + Bayes filter and tests.
2. `test/math-kernel-temporal` — temporal marginals counterexample + reproducible fixture.
3. `docs/math-predictive-sufficiency` — task-relative decision memory experiment and ablation methodology.

**Do not introduce category-theory packages, differentiable programming, RL frameworks, causal libraries or distributed execution before a concrete measurement requires them.**
