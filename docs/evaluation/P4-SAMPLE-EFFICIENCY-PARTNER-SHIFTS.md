# P4 — Learning Efficiency and Partner-Shift Evaluation (W5)

**Status:** P4 is a bounded offline experiment under the trusted single-owner W3 fixture. It is **not** general MARL, a deployed policy, federation, authentic bilateral consent or a guaranteed learning improvement.  
**Research question:** Can simple *role-shared* policies or reduced observation state improve sample efficiency relative to one tabular model per agent, particularly when the recipient's policy or resource distribution changes unexpectedly?

## Background and falsifiable hypotheses

The [P3 measured negative result](P3-THREE-SEED-RESULTS-REPORT.md) found that an always-offer-and-reciprocate *fixed rule* achieved **0.5750 mean joint reward**, while the best short-trained independent policy reached only **0.1984**; group mean/histogram/ECF were worse. This task's reward was **designed** to favor reciprocity. The result does not establish why independent policies underperformed.

P4 tests two hypotheses separately:

- **Sample coverage:** pooling experience across donors and across recipients might reduce the proportion of scarcely visited state-action contexts. An explicitly separate donor and recipient policy is shared across *role*, never across ownership or permission. This does **not** make all agents share an identity or W1 memory.
- **Observation complexity:** coarsening **only permitted local observations** may reduce unseen context keys for the same training budget. A quantized group histogram/ECF is a separately benchmarked extra feature, not automatically preferred.

Neither hypothesis presupposes that an improved learned policy beats the strong fixed cooperative baseline.

## Experiment boundaries

- **30 registered synthetic agents** in three W3 groups; **20** are decision makers (10 donors + 10 receivers). The remaining 10 are fixed passive context members.
- A W3 episode lasts **four rounds, eight committed W3 ticks**. Each donor decides about one authorized resource transfer; after its actual W3 outcome, the recipient independently decides whether to return. Updates use **only that agent's observed, designed reward after the second tick**.
- Compare **eight configurations:** fixed hold, fixed cooperation, independent full local context, independent binary/coarsened local context, role-shared full local context, role-shared binary context, role-shared destination histogram4, and role-shared destination ECF. The last two are exploratory, not preferred defaults.
- Train on the same initial worlds and **same update opportunities** per learned method (20 decisions per round). Use three nested budgets, **8 / 32 / 128 episodes**; restart policies for each budget, using the same training world seed sequence. Frozen holdout weights are verified by a before/after content digest. Fixed controls have no training updates, as appropriate.
- Evaluate on **five distinct holdout world seeds** (8101–8105 train and +1,000,003 for holdout), three episodes/seed, under **four recipient settings:** native learned behavior, always hold, always return if offered, and fixed seeded 50% mixed return. The latter three are explicit *partner-policy interventions* only during evaluation; they are not cryptographically authenticated external users.
- Run each partner intervention in both the original initial world and a **resource-reassignment shift** that shuffles integer resources *within each of the three groups*, preserving each group's total and the world's conservation invariant. This tests a distribution shift without inventing or deleting resources.
- Every learned model gets the **same W3 starting world fingerprints** for each seed/budget/partner/regime combination. Policies may cause different **later** world states. Every W3 episode is checked for **exact replay and conservation** using the existing trusted PopulationRouter and GuardedWorldGateway.
- **No real credentials, untrusted code, cross-owner actions or external observation** are accepted or created.

## Implementation metrics and limitations

Per method/seed/budget, P4 records total training updates; number of distinct policy tables (**20 independent vs 2 shared**); total state context keys; proportion with fewer than two updates; median visits per key; frozen holdout reward per donor, recipient and overall; accepted/returned transfers; rejected W3 commands; replay-checked start fingerprints; and a p50/p95 **W3 router call time**. The latter is only the trusted gateway/reducer call duration, **not end-to-end inference latency**. It also records p95 **entire episode** duration, process CPU and wall time, and process peak RSS on supported OS; Linux returns KiB and macOS uses bytes. Timings are not deterministic and cannot establish 10,000 active-agent capacity.

For the primary result, compare **joint holdout reward across five world seeds and partner shifts**, not only average train reward. Do not hide failures under favorable partner cases. The more restrictive partner-returns scenario may make the fixed cooperative policy a poor choice, which is a meaningful *negative control*.

**Important caveat:** role sharing uses two **in-memory mutable Python policy tables** within one trusted host, with sequential per-action updates at the end of each round. This is a test of experience pooling, not a concurrent update transaction, independently authenticated cooperation, or safe model/weight sharing across owners. The dense script-defined W3 opportunities remain fixed. The environment's incentives remain synthetic and potentially biased toward giving and returning.

## Exact commands

```bash
python -m unittest discover -s tests -p 'test_p4_sample_efficiency.py' -v
python -m unittest discover -s tests -v
python scripts/check_repository.py
python benchmarks/p4_sample_efficiency.py --seeds 5 --seed-start 8101 --budgets 8 32 128 --holdout-episodes 3 --rounds 4 --out p4-evidence.json
```

The full W5 unit test launches the five-seed matrix on GitHub Actions and writes a **complete structured case per log line**. Acceptance and scientific interpretation require the exact commit SHA and actual CI output; **no numerical winner is asserted in advance**. A later evidence-only commit may save those machine-readable cases and a summary, preserving negative results.

## Actual five-seed measurement checkpoint

The [CI-backed P4 evaluation report](P4-FIVE-SEED-RESULTS-REPORT.md) and its [complete raw case JSON](P4-FIVE-SEED-RESULTS.json) are preserved on this branch. The measured test ran five seeds, **120 training configurations** across three budgets, and eight partner/world conditions per configuration. **406 repository tests passed** on the pre-report source commit `e9906b230c48ff85240c1f8ae528caf82ca9881e` (one skipped, two expected failures).

For the original-world/native-partner case at **8 training episodes**, role-shared/full and role-shared/compact both score **0.5750** (matching the engineered fixed cooperative baseline), versus independent/full **0.2239**. Under a partner who always refuses, however, the fixed cooperative rule and role-shared/compact both score **-0.2250**, worse than fixed hold at **0.0000**. At 128 episodes independent compact/full catch up to the fixed rule on native partners. **No method is justified as universally optimal or safe under partner shift**; additional sample efficiency does not demonstrate general MARL convergence.

## What this cannot establish

This is a short, reset-between-episodes repeated-game simulator. It does not demonstrate convergence in nonstationary MARL, open-ended learning, real-world cooperation, Agent Genome evolution, an approved social institution, real consent, cross-world transaction or independent security audit. Group mean/histogram/ECF may leak information about small groups; the host computes them only for one synthetic owner. Exact W3 SIMULATED replay does not prove event authenticity outside the local simulator.

A representation should only be considered after **measured task benefit net of CPU/memory cost** across held-out seeds, partners and worlds. If scripted cooperation or local no-summary observations win, keep the simpler solution. Do not close [Issue #65](https://github.com/CocAgent/OpenWorld/issues/65), [Issue #51](https://github.com/CocAgent/OpenWorld/issues/51) or independent [Gate #11](https://github.com/CocAgent/OpenWorld/issues/11) based solely on unit test status.

**Rollback:** revert this opt-in experiment, its test and its optional P3 experiment parameters. No W3/W4 runtime contract, public schema, database, service or deployment is changed.
