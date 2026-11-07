# RFC-007 — Mathematical Foundations of OpenWorld Adaptive Agents

**Status:** PROPOSED — formal research architecture, not a verified theorem about an implemented system.  
**Date:** 2026-10-28  
**Owner workstream:** W2 MathKernel · [Issue #3](https://github.com/CocAgent/OpenWorld/issues/3)  
**Related:** [RFC-006](../rfcs/RFC-006-MEMORY-AND-AGENT-CONTRACTS.md), [Architecture](../ARCHITECTURE.md), [Research history](../project/PROJECT-CONTINUITY.md)

## Executive choice

Use **controlled stochastic processes + predictive-state memory + decision-focused information compression + protected exact evidence** as the minimal mathematical core. Bayesian filtering, prequential online learning and constrained optimization supply practical update/decision methods. Graph processes and compositional category-theoretic formalism extend the core later; they are not prerequisites for the first implementable MathKernel.

This is an **architectural synthesis of known mathematical frameworks**, not a claim to have invented Markov kernels, stochastic-process theory, characteristic functions, predictive state representations, or information bottleneck.

## 1. Seven foundations, prioritized

| Foundation | Mathematical purpose | Implementation priority |
| --- | --- | --- |
| Measure-theoretic probability and probability kernels | Well-defined stochastic transitions and conditioning | P0: required |
| Controlled stochastic processes / POMDP | Environment-action-observation dynamics | P0: required |
| Bayesian filtering and predictive sufficient state | Update task-relevant beliefs without re-reading every event | P0: required |
| Information theory / rate-distortion | Quantify which information loss is acceptable for which queries | P0: required |
| Decision theory, online prediction and constrained optimization | Allocate memory, inference and actions under cost/risk budgets | P0: required |
| Sparse graphs, interacting agents and population processes | Bounded collaboration and emergent behavior | P1: after basic gates |
| Category theory / Markov categories, formal methods | Compositional interfaces and proof obligations | P2: formalization, optional at P0 |

**Non-substitution rule:** A compact posterior or model-generated trace is not proof that a specific real-world event happened. Event storage, retention, authenticity, and authorization are separate concerns.

## 2. A minimal stochastic agent model

Define measurable spaces for environment/world states $\mathcal X$, observations $\mathcal O$, actions $\mathcal A$, goals $\mathcal G$ and exogenous inputs $\mathcal E$. A controlled transition kernel is

```math
K_\theta(B\mid x,a,e)=\Pr(X_{t+1}\in B\mid X_t=x,A_t=a,E_t=e).
```

For every fixed $x,a,e$, $K_\theta(\cdot\mid x,a,e)$ is a probability measure; for each measurable $B$, $K_\theta(B\mid\cdot)$ is measurable. The observation kernel is $Q_\theta(o\mid x',a)$ (density or mass where appropriate).

A full proposed agent loop is

```math
\begin{aligned}
X_{t+1}&\sim K_\theta(\cdot\mid X_t,A_t,E_t),\\
O_{t+1}&\sim Q_\theta(\cdot\mid X_{t+1},A_t),\\
Z_{t+1}&=F_\phi(Z_t,A_t,O_{t+1}),\\
A_t&\sim\pi_\psi(\cdot\mid Z_t,G_t,C_t).
\end{aligned}
```

The prediction $\hat p_t$ for an observed outcome MUST be recorded **before** receiving that outcome when evaluating prequential loss; otherwise results have leakage.

### Kernel composition

For compatible kernels $K: X\rightsquigarrow Y$ and $L:Y\rightsquigarrow Z$,

```math
(L\circ K)(x,C)=\int_Y L(y,C)K(x,dy).
```

This composition is associative when the kernels and measurable spaces are appropriately defined. For finite state spaces the integral becomes a sum; P0 should implement that finite case with strict probability validation. Composition does **not** by itself provide causal identification, trust boundaries, or efficient inference.

## 3. Bayesian belief state and task-relative predictive state

For a finite POMDP with known kernels, the filtering update is

```math
b_{t+1}(x')=
\frac{Q(o_{t+1}\mid x',a_t)\sum_x K(x'\mid x,a_t)b_t(x)}
{\sum_{u}Q(o_{t+1}\mid u,a_t)\sum_x K(u\mid x,a_t)b_t(x)}.
```

Zero-likelihood evidence MUST raise an explicit impossible-observation condition; no silent uniform fallback. A full belief state may be exponentially large and is not generally cheap in open-ended worlds.

A predictive-state representation keeps a vector of prescribed future-test probabilities,

```math
Z_t=(\Pr(\tau_1\mid H_t),\ldots,\Pr(\tau_m\mid H_t)),
```

where tests specify future action/observation sequences, $H_t$ is past history, and $m$ is a *chosen* test family rather than a universal bound.

A compressed memory $f(H)$ is **task-sufficient** for a declared query/action family $\mathcal Q$, horizon $h$, loss and environment only when future decision-relevant conditional distributions are equal for histories sharing $f(H)$, or approximately equal under a specified metric. For example, an $\epsilon$-TV condition is:

```math
\sup_{q\in\mathcal Q}\;
\left\|P(q\mid H=h_1)-P(q\mid H=h_2)\right\|_{TV}
\leq\epsilon
\quad\text{if }f(h_1)=f(h_2).
```

For any bounded single-outcome reward in $[0,R]$, the difference in its expected value is then bounded by $R\epsilon$ **provided the TV bound applies to that outcome law**. This is not a generic guarantee for all actions, rewards or histories.

**Acceptance requirement:** Each claimed compact memory must publish the task family, horizon, observed information, distortion/loss metric, and negative controls. Never call a fixed number of bytes universally sufficient.

## 4. Digital genome, epigenome and characteristic functions

The **genome** $\Gamma_i$ selects a *versioned stochastic model family*, initial prior/archetype, simulation parameters, and (where authorized) lineage metadata. It does NOT carry arbitrary external observations or encode a person's protected traits. The **epigenome** $\Omega_i(t)$ contains acquired estimators, policy settings and drift state.

A marginal characteristic function

```math
\varphi_t(u)=\mathbb E[e^{iuX_t}]
```

identifies the law of a single random variable under standard assumptions, **not the temporal dependence of a process**. Full finite-dimensional distributions require joint functions such as

```math
\Phi_{t_1,\ldots,t_n}(u_1,\ldots,u_n)
=\mathbb E\left[e^{i\sum_j u_jX_{t_j}}\right].
```

### Mandatory counterexample

Let $X_0\in\{-1,+1\}$ be uniform. At each step keep its sign with probability $q$ and flip it otherwise. **For every** $q\in[0,1]$, each $X_t$ is uniform on $\{-1,+1\}$ with marginal characteristic function $\cos(u)$. Yet

```math
\mathbb E[X_tX_{t+1}]=2q-1.
```

Thus $q=0.9$ and $q=0.1$ have identical one-time marginals but different temporal dependencies. A seed plus marginal distribution cannot reconstruct the process. Replay requires versioned dynamics, a pinned PRNG algorithm/seed/counter, checkpoint and all exogenous inputs. Real-world unrecorded observations remain unavailable.

## 5. Decision-focused compression and hard evidence constraints

A conceptual information-bottleneck objective is

```math
\min_{f} I(H;Z)-\beta I(Z;Y^{A}),
```

where $Y^A$ is the future task outcome under specified actions. Information-theoretic mutual information is not directly equal to SQLite disk bytes, and an estimated low-dimensional vector does not imply a storage guarantee.

An operational objective is

```math
\min_{M,\pi}\;
B(M)+\lambda L_{\mathcal Q}(M,\pi)
+\mu C_{\mathrm{CPU}}(M,\pi)
+\nu T_{p95}(M,\pi)
```

**subject to** exact retention for designated protected events, authorization, deletion/retention rules, memory and latency budgets, and explicit error tolerance. $L_{\mathcal Q}$ measures task-specific prediction/decision loss or regret relative to a declared baseline; $B$ counts total online bytes including WAL/SHM/indexing, not just compacted DB size.

No fixed-size lossless encoding exists for arbitrary unbounded histories. Do not compare a full-history store with a predictive estimator as if both answered the same exact-history queries.

## 6. Adaptation under nonstationarity

A practical Bernoulli P0 baseline uses: long-horizon beta-smoothed counts; a fast discounted estimate; a slow discounted estimate. Predict before updating. HM-P1e currently chooses by a **heuristic gate** on decayed Brier loss; it has not established a principled compute-cost optimum.

A proposed future alternative is exponential-weighted mixtures:

```math
\hat p_t=\sum_k w_{k,t}p_{k,t},\quad
w_{k,t+1}=
\frac{w_{k,t}e^{-\eta(p_{k,t}-y_t)^2}}
{\sum_j w_{j,t}e^{-\eta(p_{j,t}-y_t)^2}}.
```

For bounded Brier losses in $[0,1]$, classical exponential weights yields a regret bound against the **best fixed predictor in the supplied pool** of order $\log K/\eta+\eta T/8$; it does not ensure superiority on every scenario, and does not prove adaptation of the agent's whole behavior.

Consider BOCPD only with bounded runtime and documented approximation error; full run-length tracking can grow with observation count.

## 7. Multi-agent and compositional mathematics: deferred layers

For a graph $G=(V,E)$, interaction scheduling should scale with **active nodes and active edges**, rather than all-pairs interactions, when the workload permits. Graph dynamics require tests for sparse vs hub-heavy vs adversarial topologies. Mean-field approximations need explicit exchangeability/interaction assumptions and empirical error checks.

Markov categories can give a compositional language for stochastic processes and conditional independence. They should be introduced at a formal-contract stage if they clarify proofs and interfaces, not as a dependency that delays P0.

Causal hypotheses must be labeled **INFERRED** unless interventions/identification assumptions justify stronger language; correlation or a simulated counterfactual is not real-world proof.

## 8. Minimal implementable MathKernel contracts

P0 research APIs (proposed names; not currently implemented by this RFC):

- `FiniteKernel.validate()`: finite nonnegative row-stochastic probabilities, declared support and tolerance.
- `FiniteKernel.compose(other)`: compatible stochastic kernel composition, with identity/associativity tests.
- `belief_update(prior, transition, likelihood)`: normalized finite Bayes filter, impossible-evidence error.
- `predictive_equivalence(h1,h2,tests,horizon,epsilon)`: *experiment-specific* sufficiency diagnostic, not a general oracle.
- `memory_loss_report(task_family, baseline, retention_policy)`: declared evidence and fidelity boundaries.
- `stationary_marginal_counterexample()`: equal marginals, unequal two-time law test.
- `replay_spec`: process version, PRNG ID, seed, counter, checkpoint and externally provided input record references.

Interfaces MUST be reconciled with RFC-006's proposed envelope before freezing schema.

## 9. Falsifiable gates before advancing to social agents

1. Finite-kernel rows validate and compose; identity and associativity hold within declared numeric tolerance.
2. A two-state hidden Markov model produces the expected posterior under an informative observation; zero likelihood fails explicitly.
3. A counterexample proves that marginal characteristic functions do not determine temporal laws.
4. A lossy predictive summary must fail on an exact-history query that cannot be recovered, and disclose `UNAVAILABLE`.
5. Prequential scores record predictions *before* observations and show stationary, drift and noise cases, including losses to simpler baselines.
6. Protected event bytes remain exact and owner-scoped through crash recovery; MathKernel never upgrades provenance.
7. Benchmarks report online SQLite bytes, WAL/SHM, CPU, p95 latency, peak memory and query equivalence limitations.
8. No one-billion-agent extrapolation, formal theorem or production safety claim without independent evidence.

## 10. Decisions and unresolved questions

**Proposed for acceptance:** the first five foundations are core P0; graph-process research follows; category-theoretic formalization is valuable but **not** a P0 dependency.

**Open:** how to choose predictive tests; what distortion is acceptable per use case; which cost is optimized per agent; how to calibrate uncertainty under drift; proof of protocol composition and revocation; retention/erasure guarantees across replicas.

## Related compositional and multi-agent research

A separately reviewed [research and prior-art catalogue](../research/RELATED-RESEARCH-AND-PROJECTS.md) links **16 primary studies** across category theory, Markov kernels, game semantics, POSG planning, agent-based social simulation, open-ended learning, and quality-diversity. It provides specific, falsifiable OpenWorld experiments, limits and reuse checks. This catalogue **does not** upgrade the categorical P2 extension to a P0 runtime dependency, claim originality of cited mathematics, or confer a formal correctness guarantee on OpenWorld.

See also the [session-design reconciliation](../project/SESSION-SYNTHESIS-20261028.md) for the distinction between historical OpenWorld/OCP proposals and the accepted repository architecture.

## Prior literature

- Littman, Sutton & Singh (2001), *Predictive Representations of State*: https://proceedings.neurips.cc/paper/2001/file/1e4d36177d71bbb3558e43af9577d70e-Paper.pdf
- Fritz (2020), *A synthetic approach to Markov kernels, conditional independence and theorems on sufficient statistics*: https://doi.org/10.1016/j.aim.2020.107239
- Tishby, Pereira & Bialek, *The Information Bottleneck Method*: https://arxiv.org/abs/physics/0004057
- Adams & MacKay, *Bayesian Online Changepoint Detection*: https://arxiv.org/abs/0710.3742
- Cesa-Bianchi & Lugosi, *Prediction, Learning, and Games* (2006).
- SQLite WAL documentation: https://www.sqlite.org/wal.html

## Source and evidence status

This RFC selectively formalizes the **owner-provided mathematical excerpt in the current conversation** and research already documented in local RFC-004 / current GitHub continuity files. The separate ChatGPT share URL was **not retrievable in this session**; no unseen content is attributed to it. See [source reconciliation](SOURCE-RECONCILIATION.md). It is a design document; no new MathKernel test pass or deployed implementation is claimed.
