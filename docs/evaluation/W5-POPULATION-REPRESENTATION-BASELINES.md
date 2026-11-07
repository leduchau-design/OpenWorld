# W5 — Population Representation Baseline Study (Issue #44)

**Status:** Proposed synthetic measurement; **not** a trained MARL policy or an approved production representation.  
**Research inputs:** merged [PR #43](https://github.com/CocAgent/OpenWorld/pull/43), [population mathematics](../research/POPULATION-REPRESENTATION-AND-AGENT-DNA.md), [Issue #44](https://github.com/CocAgent/OpenWorld/issues/44).  
**Owned scope:** W5 benchmark, tests and evidence. No W2/W3/W4 runtime changes, no new dependencies.

## Study objective

Compare **six frozen population descriptors** under the SAME synthetic population episodes, target labels, role/region structure, train/holdout seeds, readout class and regularization. The intent is to disprove premature claims that empirical characteristic functions (ECFs) are universally necessary for many-agent decision-making.

| Name | Feature definition | Width (d dimensions, K ECF frequencies) | Important limitation |
|---|---|---|---|
| no_summary | Intercept-only readout; no aggregate features | 0 | Does not use state or neighbors |
| global_mean | Mean of each feature over ALL agents | d | Can hide minority/role signal |
| group_mean | Mean of each feature in trader/north stratum | d | Cannot recover nonlinear tails or multimodality |
| histogram8 | Eight equal-width bins on trader/north first coordinate | 8 | Ignores other dimensions and within-bin distinctions |
| ecf | Real and imaginary empirical CF at K fixed vectors | 2K | Finite frequencies are lossy; cost grows with K,d |
| rff | 2K random-phase cosine projections at frozen frequencies | 2K | Different basis/phase distribution; not a universal learned embedding |

ECF's **first frequency is deliberately** `(pi,0,...)`: this is a known spectral **positive control**. The RFF design has equal feature width (2K), but is not a proof of fair universal statistical efficiency. The ridge penalty is identical across models, although representation dimension and effective capacity differ.

## Synthetic target tasks (not RL reward)

Every simulated episode contains N agents in 3 roles and 2 regions; trader/north is the target stratum. The benchmark simulates balanced, skewed or rare (exactly 2 target agents) role composition, with a latent per-episode shift and non-target counter-shifts. Each task returns a scalar in [0,1]:

- **mean** — normalized mean of target first coordinate; group mean has an exact sufficient feature.
- **tail** — proportion of target first coordinates at least 0.5; histogram bin boundaries encode this exactly.
- **spectral** — normalized mean cos(pi times target first coordinate); the first ECF cosine feature encodes this exactly.

Readouts are **frozen ridge linear regressions fitted on synthetic labeled training episodes**, then evaluated on **disjoint holdout seeds**. This is ordinary supervised surrogate modeling, not online RL, training millions of agents, causal explanation or prediction of actual human behavior. Encoding a task label in a preselected sufficient statistic is a **positive control**, not a claim that ECF learns better than a simpler sufficient statistic.

## Test commands and provenance

~~~sh
python -m unittest discover -s tests -p 'test_w5_population_repr.py' -v
python -m unittest discover -s tests -v
python scripts/check_repository.py
python benchmarks/w5_population_repr.py --agents 100 --dim 4 --frequencies 8 --train-episodes 32 --test-episodes 16 --seed-start 3101
# Wider cost probe, only if local CPU and time budgets allow:
python benchmarks/w5_population_repr.py --agents 1000 --dim 16 --frequencies 32 --train-episodes 32 --test-episodes 16 --regimes balanced
~~~

JSON output contains exact input SHA-256 for each synthetic case, explicit training/holdout seed lists, n/d/K, target-group size, squared error by method/task, encoder p50/p95, process CPU per candidate and peak Python traced allocation for the complete benchmark. Timing values are nondeterministic and must not be used in cross-hardware comparisons without pinned CPU/OS/runtime conditions. The script caps N at 1000 (not the Issue #44 aspirational 10,000), d at 16, K at 32, and 128 training/64 test episodes to avoid unbounded CPU jobs. High-dimensional K=32 ridge may take significant CPU time in pure Python.

**Raw results must be saved from actual execution.** No results are pre-filled or inferred from a mathematical identity. Actual GitHub Actions results and measured benchmark outputs are distinct forms of evidence.

## Built-in negative controls

- **Global-collapse counterexample:** populations with identical global means but opposite trader-group means yield the same global summary, differing task labels.
- **Time-order counterexample:** rearranging events/agent sample order leaves an empirical distribution/ECF unchanged; it is not exact chronology.
- **Finite-frequency aliasing:** already tested in the merged PR #43; the sampled CF is not injective.
- **Rare role scenario:** target group has two agents, exposing possible variance and revealing that a group estimate is NOT privacy-safe just because the public vector contains no IDs.
- **No policy-quality claim:** there are no task actions, local graph updates, opponent policies, cross-owner grants, individualized rewards or true learning dynamics in this benchmark.

## Remaining acceptance criteria on Issue #44

- Actual population MARL/decision tasks with opponent changes, relevant reward or regret, calibration/Brier for binary outcomes and holdout world/partner dynamics.
- Compare histograms with role-wise and region-wise means under equal inference costs; add nontrivial random-feature and learned-encoder ablations.
- Independent W3 graph topology tests (chain/hub/sparse/disconnected) and rare-event monitoring **without** assuming aggregation preserves edges.
- Report CPU, process RSS and p50/p95 over repeated runs across N=30/100/1000, possibly 10,000 under review. The current benchmark records tracemalloc allocation but **not** per-case process RSS.
- Model privacy, consent and aggregate inference risk; no public exposure of per-agent private data, no artificial claim of differential privacy from group suppression.
- W0/W2/W3/W5 design review before changing any shared protocol or runtime defaults.

**Decision:** PR-level unit checks can accept this as a bounded offline *representation benchmark*, but cannot select ECF/RFF as the default OpenWorld multi-agent policy representation or close Issue #11.

**Rollback:** Remove benchmark, tests and this document. No world data or policy training state are written; no deployment or data migration.
