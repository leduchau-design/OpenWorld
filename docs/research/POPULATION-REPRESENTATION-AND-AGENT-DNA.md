# Population Representation and Agent Genome — Practical Research Design v0.2

**Status:** Evidence-based research guidance, not a production architecture, public data contract, proven scaling method, or implementation of an evolving society.  
**Updated:** 2026-10-29. **Workstreams:** W2 (mathematics/learning), W3 (world state), W5 (independent evaluation); W0 owns changes to shared contracts.

## 1. Current decision

OpenWorld should **not commit to a universal population embedding or artificial "DNA" theory**. Use the simplest representation that improves an explicitly measured agent decision while respecting runtime cost and access controls.

Priority for bounded CPU experiments:

1. **No population summary:** essential control.
2. **Group count and mean:** first choice if a task depends on an average or simple frequency.
3. **Small histogram:** add only where an average hides multimodality or tail behavior.
4. **Empirical characteristic function (ECF):** optional comparator for a task where its frequency features offer additional predictive value **after** costs are counted.
5. **Exact local event/graph state:** keep whenever individual relationships, temporal order or rare critical events determine the outcome. No aggregate replaces authoritative state.

This is a **manual, task-specific evaluation rule**, not a deployed automatic selection engine. There is **no current evidence** that mean-field MARL, learned distribution embeddings, QID/FQID distributions, quantum computation or an evolutionary search algorithm improves OpenWorld's actual world play.

## 2. Implemented code versus demonstrated behavior

| Artifact | Implemented or measured | Not demonstrated |
|---|---|---|
| [Research population module](../../src/openworld_superkernel/population_repr.py) | Typed immutable genome records, deterministic one-trait mutation, ECF for bounded vectors, grouped role/region sketches | Fitness, natural selection, actual genotype-to-behavior mapping, private aggregate release or policy optimization |
| [W5 representation baseline](../../benchmarks/w5_population_repr.py) | Synthetic supervised prediction using no summary, global/group mean, histogram, ECF and RFF | Reinforcement learning or social interaction |
| [P1 bandit experiment](../../benchmarks/p1_population_learning.py) | Online chosen-action reward updates for a **role-shared two-arm contextual bandit**, 30 synthetic agents by default | Agent decisions changing future world state; genuine MARL or co-evolution |
| [Pinned P1 report](../evaluation/P1-THREE-SEED-CI-REPORT.md) and [raw JSON](../evaluation/P1-THREE-SEED-CI-RESULTS.json) | Three measured world seeds; two deliberately constructed toy tasks; frozen-policy holdout | General performance outside these tasks, 1,000+ active agents or an independent safety audit |

P1's synthetic agents each have an `agent.trait` used by the bandit. Their `genome_id` is generated separately; **P1 does not decode the genome or prove that genome traits cause learned behavior**. Sharing a role policy is a computational design choice, not proof of population-level coordination.

### Actual measured P1 results

GitHub Actions evaluated **30 synthetic agents**, world seeds **4103–4105**, **100 training ticks** and **40 holdout ticks** per case, with **1,200 holdout actions per method, seed and task**. Numbers below are averages of those three seeds:

| Summary | Mean task accuracy | Spectral task accuracy | Mean-task p95 feature encoding | Spectral-task p95 encoding |
|---|---:|---:|---:|---:|
| None | 45.8% | 45.9% | 0.019 ms | 0.020 ms |
| Role-group mean | 100.0% | 46.2% | 0.026 ms | 0.027 ms |
| Eight-bin histogram | 100.0% | 100.0% | 0.151 ms | 0.153 ms |
| ECF at π | 100.0% | 100.0% | 0.396 ms | 0.396 ms |

**Interpretation:** Group mean was sufficient for the constructed mean task. Histogram **matched ECF** on the constructed spectral task with lower measured feature-encoding cost. ECF **did not outperform histogram** on these tasks. The environment's reward rule is deliberately aligned with the selected statistics; these 100% accuracies are **positive controls**, not evidence of realistic learning or a generic advantage. The timing comparison is specific to the present Python implementations, feature widths and runner—not a general algorithmic performance theorem.

**Resulting choice:** neither ECF nor mean-field MARL is a default. Retain no-summary, mean and histogram as initial reference baselines, and include ECF only when a new task supplies a defensible reason to test it.

## 3. Minimal, bounded mathematical representation

For a permitted group $G$ of $n_G$ agents, let $x_i$ denote a task-defined **non-sensitive, bounded numeric feature**, not the complete private agent state. The group count and mean are:

```math
n_G = |G|,\qquad
\bar{x}_G = \frac{1}{n_G}\sum_{i\in G}x_i,\qquad n_G>0.
```

For predefined, disjoint bins $B_1,\ldots,B_b$, a compact histogram is:

```math
h_{G,j}=\frac{1}{n_G}\sum_{i\in G}\mathbf{1}[x_i\in B_j],
\qquad j=1,\ldots,b.
```

The task determines the bins, feature units, time window and what to do when $n_G=0$. **Never fill a missing group with an invented mean or silently treat low sample counts as statistically reliable.** Group counts are useful for interpreting estimation variance; releasing them or means to untrusted parties may leak sensitive information.

An optional ECF for a **fixed, bounded frequency** $\omega$ is:

```math
\widehat{\varphi}_{G}(\omega)
 = \frac{1}{n_G}\sum_{i\in G}\exp(\mathrm{i}\omega^\mathsf{T} x_i).
```

The implementation stores its real and imaginary components, not an actual quantum state. A characteristic function known at all frequencies determines a probability distribution, but **a finite set of sampled frequencies generally does not**; two different populations can have identical finite sketches. ECF is insensitive to the ordering of samples and cannot reconstruct identity, causal influence, private memory or exact events.

The P1 learner uses only the observation available to the synthetic agent, a fixed individual scalar trait and an optional role-group summary:

```math
z_i(t) = [\,1,\ o_i(t),\ \tau_i,\ s_{\mathrm{role}(i)}(t)\,].
```

The learner predicts chosen-action reward and adjusts role-shared parameters from observed feedback. **This is a contextual bandit, not a Markov-game learning equation**; it makes no claim that $s_G$ is sufficient for optimal decisions in a real dynamic world.

**Implementation scope matters:** the research sketch module supports role-and-region grouping and up to 16-dimensional numeric vectors, but the measured P1 task uses one-dimensional role summaries. Neither implementation proves scalable computation on arbitrary agent populations.

## 4. "DNA" means a versioned configuration blueprint, not biological heredity

The word **genome** in this repository is a convenient label for an immutable, content-addressed configuration. Its present fields are:

| Field | Concrete current meaning |
|---|---|
| `role` | Enumerated research role; not an occupational skill or permission |
| `policy_family` | String describing an allowed research policy family; not a model runner |
| `policy_digest` | Syntactically checked `sha256:` identifier; not proof that a model exists, is safe, reviewed or licensed |
| `traits` | Sorted named integer parameters in the interval 0–100; their semantics and effect on real behavior are **unvalidated** |
| `parent_genome_id`, `generation` | Recorded configuration derivation chain; not a biological pedigree or audited evolutionary process |
| `genome_id` | Deterministic hash of canonical record content; not an agent identity, signature, ownership claim or capability |

The only existing mutation operator changes one bounded trait using a deterministic seed and points to its parent. It **does not** optimize fitness, cross over policies, breed populations, alter a running policy, or admit generated code. An agent may reuse a genome blueprint while retaining independent identity and experience.

**Do not combine** genome, agent identifier, credential, policy weights, exact memory, world balance and security grants into one field or hash. Model parameters can be shared by multiple agents while each agent's identity, event history and permissions remain separate. A policy artifact reference must be independently resolved, reviewed and authorized before execution; hashing alone never provides that approval.

There is no empirical basis today for assigning specific psychological interpretations to traits such as `curiosity` or `risk`, or claiming their mutation improves an agent. Keep these labels as **experimental knobs** until observed behavior and repeatable evaluation justify them. The current genome schema is **research.v0**, not a production contract.

## 5. What the learning experiment does not yet establish

P1 trains from individual, chosen-action reward, but its exogenous scene generator resamples a group signal every tick. Agents' actions do **not** change the subsequent scene, and other agents' learned policies do not constitute strategic opponents. Therefore:

- It is reasonable to call P1 **online contextual-bandit learning with many simulated actors**.
- It is **not** evidence of mean-field MARL, an evolving economy, institutions, cooperation, or autonomous civilizations.
- Training steps, active inference calls and registered/stored agents are different resource counts. Do not use one as a proxy for another.
- There is no demonstrated advantage from a new genome over a simple fixed configuration, and no policy evolution or selective reproduction in the measured trials.

Applied category theory, Markov categories and controlled stochastic kernels may clarify *interfaces* in other OpenWorld documents, but their mathematical elegance does not validate predictive sufficiency, safety or performance of these particular population summaries. Keep those claims out of this implementation recommendation.

## 6. A feasible next experiment — conditional, not promised

[Issue #51](https://github.com/CocAgent/OpenWorld/issues/51) proposes a **single trusted, CPU-only, bounded, action-dependent world experiment**. Do not add a large distributed platform just to investigate population features. Proceed only after an explicit W0/W3 review confirms the permitted event and authorization boundaries.

A smallest useful study would:

1. Use **up to 30 synthetic agents**, one trusted host and a fixed small world, with bounded resources and a small set of permitted actions.
2. Require at least one action that changes a **later** world state; record each external input and preserve deterministic replay. Otherwise it is another contextual-bandit study.
3. Compare **rules/no learning**, no-summary, group mean, histogram and optional ECF on exactly the same action budget, training opportunity and held-out world seeds.
4. Report **action-dependent delayed reward, failure cases, per-role outcomes, replay equality, CPU time and process memory**. Treat rare harmful events separately instead of averaging them away.
5. Keep agent policies inside a trusted, controlled experiment; do not execute untrusted code or allow cross-owner interaction without an approved capability/consent pathway.

If these conditions are not met, **stop at P1** and improve the benchmark rather than claiming a "Living World." Do not commit to 1,000 or 10,000 active learners, GPU clusters, evolutionary societies, causal independence, a learned latent embedding or a new shared protocol before a smaller task demonstrates need.

## 7. Explicitly outside this design

These were considered in earlier discussions but **do not solve the immediate engineering problem**:

- **Quasi-infinitely divisible distributions (QID)**: [Lindner, Pan & Sato (2017)](https://arxiv.org/abs/1701.02400) and [Berger, Kutlu & Lindner (2021)](https://arxiv.org/abs/2101.02544) study mathematical properties of classical distributions and Lévy–Khintchine-type representations with signed quasi-Lévy measures. Those results do not supply a ready-made agent policy, genotype or population training algorithm.
- **Freely QID distributions**: [Hotta et al. (2023)](https://alea.impa.br/articles/v20/20-34.pdf) concerns *free probability*, not the freedom of software agents. No current OpenWorld experiment requires free convolution.
- **Riemann hypothesis**: [Clay Mathematics Institute](https://www.claymath.org/millennium/riemann-hypothesis/) describes a number-theoretic conjecture, not an agent-training prerequisite.
- **Quantum computing**: no current hardware, runtime, benchmark or workload demonstrates a quantum advantage for OpenWorld. Complex-valued ECF calculations do not imply quantum computation.
- **Learned mean-field representations**: [Makkar et al. (2026)](https://arxiv.org/abs/2609.02928) investigates a specific offline setting with an aggregate-statistic assumption; those assumptions have **not** been established for OpenWorld's world dynamics. [Yang et al. (2018)](https://proceedings.mlr.press/v80/yang18d.html) motivates mean-field MARL, not automatic applicability to this code.
- **RFF / kernel mean embeddings**: useful research comparators, but not justified as dependencies or runtime defaults by the existing P1 result. See [Muandet et al. (2017)](https://doi.org/10.1561/2200000060) and [Rahimi & Recht (2007)](https://papers.nips.cc/paper_files/paper/2007/hash/013a006f03dbc5392effeb8f18fda755-Abstract.html).

These references remain background sources, **not implementation requirements**.

## 8. Evidence and operational acceptance rules

Before adopting any population summary for an actual world policy, require all of the following:

- **Relevant task:** measured improvement in held-out *decisions*, reward or regret, not only reproduction of a statistic designed into the label.
- **Baseline first:** compare no-summary, mean and a small histogram; add ECF or learned embeddings only with a clear hypothesis and cost measurement.
- **Reproducibility:** commit SHA, complete configuration, world/holdout seeds, code version, actual test output and negative results.
- **Correctness:** explicit treatment of empty/small groups, finite inputs, aliasing, time-order loss, rare behaviors and action-to-state causality.
- **Resource accounting:** number of active decisions, policy updates, feature time, full tick latency and memory; do not extrapolate a toy runner to millions of agents.
- **Trust:** use the W0/W3/W4 authorization boundary. **Aggregate features are not automatically private**; even withholding groups with fewer than two members is not a differential-privacy or k-anonymity guarantee.
- **Admission:** review and a new decision record for any shared API or default representation change; no automatic promotion of evolutionary candidates.

### Reproduce today's code and evidence

```sh
python -m unittest discover -s tests -p 'test_population_repr.py' -v
python -m unittest discover -s tests -p 'test_p1_population_learning.py' -v
python -m unittest discover -s tests -v
python scripts/check_repository.py
python benchmarks/p1_population_learning.py --agents 30 --train-ticks 100 --holdout-ticks 40 --seeds 3 --seed-start 4103 --tasks mean spectral --regimes balanced
```

The saved [P1 report](../evaluation/P1-THREE-SEED-CI-REPORT.md) ties its results to the precise earlier GitHub Actions run; reruns can differ in wall-clock timings. This document does **not** assert that the command above was executed as part of this documentation edit.

**Change boundary:** This document changes recommendations and removes unverified assumptions. It changes **no code**, genome schema, math kernel, world rules, agent data or public security contract.
