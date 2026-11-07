# P1 — Thirty-Agent Online Population Learning (Research)

**State:** PROPOSED experimental CPU-only learning benchmark, not a trained OpenWorld civilization or world-runtime policy.  
**Date:** 2026-10-29. **Related:** [population representations](../research/POPULATION-REPRESENTATION-AND-AGENT-DNA.md), [W5 baselines](W5-POPULATION-REPRESENTATION-BASELINES.md), [Issue #44](https://github.com/CocAgent/OpenWorld/issues/44), W0/W3/W4 and [Gate #11](https://github.com/CocAgent/OpenWorld/issues/11).

## Why P1 is necessary

PR #47 measured representation quality on frozen synthetic distribution labels with supervised ridge readouts. It **did not** test whether acting agents can *learn from rewards*. P1 advances by giving persistent (within one run) toy agents with typed content-addressed genome blueprints shared *role policies*, letting them choose binary actions, observe **only chosen-action reward** and update online. Policies are frozen on previously unseen world seeds. This tests a basic learning loop, **not** joint Markov-game RL or strategic co-evolution.

The agent population is simulated offline, independent of W3's protected state and W4's authorization gateway. The genome is **not** an owner ID or privilege and is not mutated by training.

## Explicit environment and estimand

- Default 30 toy agents with 3 roles (builder/explorer/trader), one private uninformative sensor and a fixed bounded genome trait each. 10 agents per role in balanced mode; *rare* mode has only two traders (an explicit privacy/variance negative control).
- Each synthetic tick samples fresh, unobservable mode for each role and a role-dependent field $x_j(t)$. The mode generates a **mean task** (role-group mean is informative) or a **spectral task** (two nearly mean-zero but differing $E[\cos(\pi X)]$ groups).
- Each toy agent chooses one action $a_i\in\{0,1\}$. A hidden environment rule selects the better action by group signal plus a small fixed trait contribution. A correct action has expected reward 0.85, incorrect 0.15. These are *designed simulation probabilities*, not learned truths. The agent receives a **single Bernoulli reward for the chosen action**.
- Train with a deterministic role-shared, two-arm **logistic contextual bandit** using epsilon-greedy exploration and stochastic-gradient updates to the chosen action's predicted reward. **All actions for a tick are selected before any update**; no within-tick reward leakage.
- On holdout, the model is frozen; evaluate accuracy against the simulated hidden better action, realized reward, and **expected regret per action** relative to the simulated optimum. All methods receive identical train/holdout scenes and deterministic potential outcomes, and comparable update budgets.

A P1 agent's context is:

```math
z_i(t) = \big[1,\, o_i(t),\, \tau_i,\, s_{r(i)}(t)\big]
```

Here $o_i$ is local synthetic noise (a deliberate negative control), $\tau_i$ is an immutable trait, and $s_r$ is an optional role-stratified summary of group state. The learner fits two reward predictions $q_\theta(r,z,a)$ and chooses the higher value except during training exploration.

The **mean task** and **spectral task** are deliberately chosen positive controls. In particular, the ECF at frequency $\pi$ contains the spectral target; this does **not** establish ECF superiority in general or mean-field sufficiency for real games. The histogram is retained as a simple stronger nonparametric baseline.

### Arm comparisons and metrics

| Baseline | Context beyond private observation/trait | Feature width | Expected strength |
|---|---|---|---|
| no_summary | None | 0 | Should have little information about hidden group mode |
| group_mean | Mean within actor's role | 1 | Mean task positive control |
| histogram8 | Eight equal bins over role's first coordinate | 8 | Multimodal/tail negative or positive benchmark |
| ecf | Real/imaginary CF at frequency pi | 2 | Spectral task positive control |

**Scientific caution:** Features have different widths, model capacities and computation costs. This is a useful comparison of practical fixed choices, **not a matched-parameter statistical efficiency theorem**. There is no globally optimal representation implied by one task.

## Reproduce

~~~sh
python -m unittest discover -s tests -p 'test_p1_population_learning.py' -v
python -m unittest discover -s tests -v
python scripts/check_repository.py
python benchmarks/p1_population_learning.py --agents 30 --train-ticks 160 --holdout-ticks 60 --seeds 3 --seed-start 3101
~~~

The standalone script prints JSON or writes it to \`--out\`. It includes distinct world/holdout seeds, a SHA-256 digest of synthetic scenes, role/action budget and achieved rewards, regret, accuracy, representation encoding p50/p95, Python/OS/CPU and tracemalloc peak. **Do not publish invented numerical improvements**: quantitative comparisons require actual benchmark logs pinned to code SHA, CPU, seed configuration and environment.

The script limits N to 9–300, training to 10–500 ticks and held-out evaluation to 5–200 ticks. These are *bounded CPU test limits*, not scalability claims. The current code generates fresh exogenous scene data each tick; it does not maintain a jointly affected W3 world state.

## Testable negative controls and reproducibility requirements

1. Each fixed seed creates identical agents, genome references, world fields, private observations and realized chosen-action rewards; different world seeds give different fields.
2. An agent's policy context includes no oracle action, true hidden mode, other agent identity, per-owner history, secrets, capabilities or counterfactual reward. The full host state and oracle are used **only in scoring**, not in learner updates.
3. All methods use the same scenes, same action reward tables and same exploratory RNG seed. Actions can diverge once policies learn, so *realized sampled rewards* are not guaranteed equally distributed across actions.
4. A no-summary policy cannot reconstruct a role-mode from a single context in this synthetic design. A global mean is already known to hide opposed roles; P1 tests stratified alternatives.
5. Holdout uses a separate world seed, **no weight updates**, and oracle regret is calculated from hidden simulated state. No scientific claim that performance generalizes to other economies, opponent strategies or regime shifts.
6. A two-agent group exists in rare mode. Its released mean/ECF can reveal information; **none of these aggregates are privacy guarantees** and none may be exposed to untrusted owners.
7. No improvement may be declared without reporting both tasks, all baselines, multiple seeds, negative results and per-method compute cost.

## Measured three-seed CI checkpoint

After initial CI, [this pinned synthetic benchmark report](P1-THREE-SEED-CI-REPORT.md) and its [raw machine-readable evidence](P1-THREE-SEED-CI-RESULTS.json) were extracted from GitHub Actions on commit `cc011d6c63d79a3512fe4540a483592e1cac19d3`: **30 agents, 100 train ticks, 40 holdout ticks, three seeds, two tasks**. No-summary was near chance; group mean, histogram and ECF passed the mean positive control; histogram and ECF both passed the spectral positive control. **ECF had no accuracy gain over histogram and was more expensive in this implementation.** These bounded positive controls cannot justify making ECF the default.

## Next design decisions — not implemented

A meaningful **P2 Living World** needs W3-authoritative sparse interactions, longer-lived agent state, genuine action-to-state consequences, social incentives and delayed/partial rewards. Validate a *multi-agent* task with held-out partner policies and replayed exogenous inputs; retain typed individual memory and scoped consent at W0/W4. Measure robustness, fairness between roles, population effects, task reward and cost. ECF should only be promoted where it beats the simpler grouping methods **under the relevant real task**.

The separate W5 Issue #44 remains open: P1 is **an action-learning positive-control experiment**, not the entire requested 1,000/10,000-agent training/scaling benchmark. Do not claim self-evolution, independently verified world history or civilization emergence.

**Rollback:** Remove this benchmark, its tests and this note. No W2/W3/W4 service code, model weights, production databases, world rules, identity or GitHub Actions configuration change.
