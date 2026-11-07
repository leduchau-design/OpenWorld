# P2-A — Stateful Population Cooperation, Bounded W3 Experiment

**Status:** Research-only action-dependent W3 simulator, not a released MARL system, independent federation, institution engine, or security service.  
**Date:** 2026-10-29. **Tracks:** [Issue #51](https://github.com/CocAgent/OpenWorld/issues/51), [P0 population links](../world/W3-POPULATION-LINKS-P0.md), [population research](../research/POPULATION-REPRESENTATION-AND-AGENT-DNA.md).

## Testable question

Can a donor learn from delayed reward whether transferring resources helps an agent in another group, when the transfer and later recipient response are **actual W3 state transitions**? Test four representations against two fixed no-learning policies. Do not infer evolutionary intelligence or autonomous institutions.

## Precise environment

- **30 registered toy agents, but only 10 donor decision makers**, with 10 potential recipients and 10 passive context agents; one trusted synthetic owner and three groups.
- Ten inter-group adjacency edges connect two neighboring group boundaries. Donor chooses to transfer exactly two integer units or hold; source/recipient grants, directed contracts, transfer quotas and same-owner restrictions are enforced by the already merged PopulationRouter and GuardedWorldGateway.
- Each of the two destination groups has two synthetic balance distributions. Each group total stays unchanged, but in the needy mode recipients start with zero; in the funded mode they start with two. The **group mean cannot distinguish** these intentionally constructed cases, while a fixed histogram/ECF can.
- W3 tick 0 applies donor decisions. At tick 1, fixed-rule recipients send acknowledgment signals when their current W3 balance is at least two. The donor reward is one for the actual acknowledgment event minus 0.25 if its transfer was accepted. No hidden mode, oracle action or counterfactual reward is given to the learner.
- Learning uses a deterministic epsilon-greedy two-action tabular reward estimate. Updates are delayed until **after tick 1**; holdout is frozen, world episode resets but the training table persists. Both W3 ticks and their submitted inputs are replay-verified.

**Classification:** This is **delayed-feedback contextual learning embedded in a two-step stateful W3 simulator**. It is not independently adapting multi-agent reinforcement learning: recipient policies are fixed, the world resets between episodes, and only 10 donors choose learned actions.

## Recorded measured checkpoint

The [three-seed measured CI report](P2-THREE-SEED-HOLDOUT-REPORT.md) and [raw JSON](P2-THREE-SEED-HOLDOUT.json) provide actual replay-checked W3 action reward: the four-bin histogram achieved a mean holdout reward of **0.8715** versus **0.8056** for ECF and **0.7500** for role-group mean or always-transfer across the deliberately constructed test. This is a positive control, not evidence of generic multi-agent cooperation or a representation theorem.

## Baselines

| Method | Information available | Essential control |
|---|---|---|
| rule_hold | Always retain resources | No-learning lower-cost policy |
| rule_transfer | Always donate two | No-learning generous policy |
| no_summary | No destination distribution | Population information ablation |
| group_mean | Destination-group average | Intentionally non-informative about the hidden distribution |
| histogram4 | Four destination balance bins | Simple nonlinear distribution feature |
| ecf | Empirical characteristic function at pi/4 | Optional Fourier comparator; not necessarily better |

All methods receive the same deterministic held-out world seeds and underlying synthetic balance distributions. Do not claim statistical superiority from a single method's accuracy on a task constructed to favor its features.

## Reproduction

Run the P2 test module using Python unittest discovery with filename test_p2_stateful_cooperation.py, then run the complete repository suite and layout check. The standalone CPU-only benchmark is:

    python benchmarks/p2_stateful_cooperation.py --train-episodes 60 --holdout-episodes 30 --seeds 3

The JSON includes method, train updates, per-episode holdout rewards, world/holdout seeds, need-mode fingerprint, and registered-versus-decision actor counts. The integration tests check exact W3 replay, conservation, different action-dependent world fingerprints, frozen holdout policy, cross-owner denial, mean-equality/histogram-distinction and a tiny CLI smoke. **Only measured CI output may support quantitative claims.**

## Hard boundaries and blockers

The demo host controls principal and short-lived HMAC grants; this is **not** a durable independently authenticated access audit, legal bilateral consent or an unbypassable security perimeter against arbitrary Python code. Cross-owner interactions remain denied. The underlying exact world events have SIMULATED provenance, not verified external observations.

The fixed recipient rule, two-tick horizon and small reset episodes do not establish decentralized coordination, emergent institutions, persistent economy, co-evolution, billions of agents, privacy of group aggregates or useful human-level intelligence. There is no agent genome execution, model self-modification or transfer of identity/capabilities. W0/W2/W3/W4/W5 review and independent Gate #11 remain separate.

**Next experiment, conditional on results:** compare task reward under alternative recipient policies, longer delayed consequences, rare catastrophic resource shortages and a fixed compute budget. Keep ECF optional unless it outperforms group mean and histogram on a relevant held-out task.

**Rollback:** delete this benchmark, its tests and this note; no production code, W3 schema, database or permissions are modified.
