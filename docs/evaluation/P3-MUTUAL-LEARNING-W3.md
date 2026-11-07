# P3 — Twenty Independently Learning Agents in an Eight-Tick W3 World

**Status:** Experimental, CPU-only, synthetic **multi-learner local interaction**. Not production multi-agent RL, emergence, an institution, an agent-identity service, or federation.  
**Baseline:** [P2 two-tick evidence](P2-THREE-SEED-HOLDOUT-REPORT.md), [P0 group links](../world/W3-POPULATION-LINKS-P0.md), [Issue #51](https://github.com/CocAgent/OpenWorld/issues/51).

## Why this experiment is distinct from P2

P2 trained only **10 donor decision makers** and scripted the recipient's response over two W3 ticks. P3 trains **20 separate per-agent policies:** ten donors decide whether to give one resource, then ten recipients independently decide whether to return one. Each synthetic episode preserves its World for four consecutive two-tick rounds (**8 committed W3 ticks**); the outcome of an earlier round changes balances and the next round's available actions.

There are 30 registered agents in three same-owner groups. Ten other agents supply passive population context; do **not** call them learners. Each pair uses its existing sparse neighbor edge. The trusted host issues synthetic scoped W3 grants and makes the allowed group features; no untrusted code executes.

## Model and truthful reward boundary

Each donor's action is 0 (hold) or 1 (transfer one unit if available). The recipient's action is 0 (hold) or 1 (return one if available). W3 receives a single action batch for each phase, via **PopulationRouter + GuardedWorldGateway**, not direct calls to the reducer.

For accepted **simulated** W3 event outcomes, donors obtain +0.85 for a donation that is reciprocated, minus 0.25 if the donation was accepted. Recipients obtain +0.70 for successful reciprocity to an actual donation, minus 0.15 for any accepted return and minus 0.20 for receiving a donation without returning. These are **designed incentives for this controlled problem**, not an economic valuation. Both learners update only from their own observed designed reward **after** the recipient W3 tick has committed; all decisions in one phase are frozen before any update.

A recipient's context is its own W3 balance and whether its neighbor actually transferred to it in the preceding phase. A donor's context includes its own balance and its own previous return outcome, with an optional **host-aggregated same-owner** destination group statistic. No latent need mode, oracle action, counterfactual reward, cross-owner private memory or privileges are used by learning code.

There is **one policy table per agent** (not one shared global neural network). Each table learns a two-arm average reward from chosen-action feedback, with seeded epsilon exploration during training, then freezes during holdout. The policies survive episode resets during training; the World does not. This is a bounded **multi-learner delayed-feedback repeated game inside W3**, not proof of convergent MARL, long-run nonstationary strategic equilibrium or novel behavior in an uncontrolled world.

## Six predeclared comparisons

| Method | Donor/recipient choice | Distribution feature |
|---|---|---|
| hold | Neither transfers | None; fixed rule |
| always_reciprocate | Always offer if funded; recipient returns only if a donation arrived | None; fixed rule (strong cooperative control) |
| no_summary | Each of 20 agents learns from own feedback | None |
| group_mean | Independent learners | Destination-group average |
| histogram4 | Independent learners | Four-bin distribution of destination balances |
| ecf | Independent learners | Quantized real/imaginary empirical CF at a fixed frequency |

The **same synthetic world seed and episode index** generate initial states for every method. Decisions and downstream worlds diverge by method, so final state fingerprints need not be identical. The scripted always-reciprocate policy may be better than learned methods; this is a useful **negative result**, not a defect to conceal. Because reward is constructed to encourage reciprocity, the experiment cannot show emergent altruism or institution creation.

## Reproduction

Run the focused unittest suite through Python discovery selecting the filename `test_p3_mutual_learning_w3.py`, then the full repository tests and `python scripts/check_repository.py`. Bounded CLI:

```bash
python benchmarks/p3_mutual_learning_w3.py --train-episodes 20 --holdout-episodes 8 --rounds 4 --seeds 3 --seed-start 6101
```

This produces raw JSON for six methods and three seeds. Each episode asserts **exact W3 replay**, resource conservation and SIMULATED-only provenance. Output distinguishes 30 registered agents from 20 active decisions. The benchmark does not yet measure process RSS, multi-host network latency or crash recovery; GitHub CI timing cannot establish 1,000-agent capacity.

## Test and admission gates

- **Action causality:** the fixed hold and fixed offer+return policies yield different eight-tick world fingerprints; offers and returns change resource availability in subsequent rounds.
- **Two-sided learning:** all 20 agent policies must receive updates in training, none in frozen evaluation. No receiver policy is hardcoded as the agent's learned behavior.
- **Trust:** reject owner-mismatched transfer even with synthetic signed grants. No cross-owner actions, automatic organization charter approval, private memory export, genomic mutation or remote world integration.
- **Negative information control:** destination group means may be identical even when histograms differ. ECF is never automatically the default.
- **Holdout honesty:** no leaked oracle modes, same initial world family across methods, complete seed and per-method results, predeclared incentives and unchanged evaluation weights.
- **Generalization:** a real subsequent gate must include independently adapting opponents, unseen role composition, asymmetric resources, held-out partner shifts, failure-cost accounting and full CPU/RSS measurements. None is established by unit-test success alone.

**Admission/rollback:** Owner W0/W2/W3/W4/W5 review and pinned exact-head CI required. Keep [Issue #51](https://github.com/CocAgent/OpenWorld/issues/51) and independent [Gate #11](https://github.com/CocAgent/OpenWorld/issues/11) OPEN. Revert standalone benchmark, its tests and this note to remove P3; no production W3, gateway, database or public schema is modified.
