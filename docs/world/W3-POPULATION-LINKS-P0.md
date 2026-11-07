# Population Links P0 — Connecting Agent Groups in One Local World

**Status:** Experimental local reference, not a federation protocol, security product, autonomous society, or cross-owner consent implementation.  
**Date:** 2026-10-29. **Review:** W0/W3/W4/W5. **Related:** [Issue #51](https://github.com/CocAgent/OpenWorld/issues/51), [population research](../research/POPULATION-REPRESENTATION-AND-AGENT-DNA.md), [W3 fixture](W3-EXPERIMENTAL-FIXTURE.md), [security gateway](W3-SCOPED-GATEWAY-RESEARCH.md).

## 1. Distillation of the owner-supplied conversation extracts

The six supplied text files comprise five distinct excerpts; files numbered (3) and (4) are duplicates. They are owner-provided design material, not verified full conversation exports. Their provenance is recorded in the [source register](../project/SESSION-SOURCE-REGISTER.md); raw uploads are not republished.

| Source ideas | Retained | Explicit boundary |
|---|---|---|
| OpenWorld independent from other projects; local-first and community-compatible | One local, CPU-only, owner-controlled World | No public federation, network API or mod execution |
| Fictional strategy world with POSG, graph and social decisions | Sparse W3 neighbor graph and bounded group interactions | No proof of an equilibrium, strategic intelligence or MARL |
| SuperKernel v2, institutions, agent/world/society co-evolution, World Genome and event chronicle | Explicit group memberships, directed interaction contracts and simulated event history | No institution generation, causal inference, world-genome mutation or evolution engine |
| OCP category-theoretic composition and stochastic semantics | Independently testable typed connections, W3 reducer and replay | No OCP project rename, category-theory runtime dependency or external standard |
| Agent Genome, population features and learning | Optional group boundaries compatible with existing research modules | No ECF-derived grants, predictive sufficiency claim, private-information release or genotype-to-fitness proof |

## 2. Concrete connection model

The added [population link adapter](../../src/openworld_superkernel/population_links.py) reuses the existing [GuardedWorldGateway](../../src/openworld_superkernel/world_guard.py). It changes no core event contracts, runtime exports, memory, database schema, or security rules.

A population is a **registered group of agent IDs**, not a new owner or authority. This local fixture requires each agent to belong to exactly one group, and all agents to be assigned to a group. A directional link states which source group may send a signal or bounded integer resource transfer to which destination group; it also sets a maximum transfer amount and per-tick action count.

Before passing any batch to W3, the adapter verifies the following: (a) current tick and unique request ID; (b) actor and target membership; (c) group contract type, quota and amount; (d) existing W3 sparse-neighbor edge; (e) both agents share exactly **the same owner**; and (f) source and target resource-scoped signed capabilities validated against a **trusted-host principal**. All adapter prechecks must succeed before any W3 action executes.

The two grants may be issued by the same experimental owner. **They are not bilateral consent from independently authenticated owners.** The target grant is a local extra policy check, not a new legal/privacy or cryptographic consent protocol. Cross-owner requests remain denied in W3, including apparently harmless signals.

Once W3 is called, an otherwise permitted transfer can still be rejected for insufficient resources. That is a W3 **simulated world outcome**, not a gateway permission failure. W3 returns its accepted/rejected requests, state and SIMULATED event slice. Exact event history and replay remain with W3; capability proofs are not stored by the W3 journal.

## 3. Small mathematical model

Let V be the finite set of agents, E its existing W3 adjacency relation, and G_1,...,G_k a partition of V. For a cross-group local action from a to b, we require:

```math
(a,b)\in E,\quad a\in G_i,\ b\in G_j,\ i\neq j,\quad (G_i,G_j)\in L.
```

Here L is the trusted host's finite **directed population contract list**, not a federation peer list. For a W3 transfer of integer q between authorized same-owner neighbors, the resource-conservation invariant is:

```math
B_a'=B_a-q,\quad B_b'=B_b+q,\qquad \sum_{v\in V} B_v'=\sum_{v\in V} B_v.
```

No predictive sufficiency, social emergence, causal discovery, permission authenticity or optimization theorem follows from these equations.

## 4. Reproduce the integration

~~~sh
python -m unittest discover -s tests -p 'test_population_links.py' -v
python examples/populations/local_three_groups.py
python -m unittest discover -s tests -v
python scripts/check_repository.py
~~~

The demonstration uses 30 synthetic agents, three groups of ten, one owner, a connected chain graph, two cross-group boundaries and two simulated ticks. It submits source/target capability-checked signals and small transfers; it checks total resource conservation, exact replay and SIMULATED provenance. It is **scripted interaction**, not evidence of agents learning to cooperate or spontaneously creating institutions.

The negative test suite covers wrong owners, missing/incorrect or revoked source/target grants, missing group contracts, non-neighbor actions, quota, duplicate/stale request IDs, invalid transfer amounts, incomplete group membership, precheck atomicity and exact replay. All test results must be read from an actual check on the PR commit.

## 5. What remains unimplemented and why

- No cross-owner exchange or permission escalation, independent receiver acceptance, immutable security decision audit, token consumption, untrusted Python sandbox, or public server.
- No two-world federation, shared asset authority, economic treaty lifecycle, distributed consensus or external skill transfer.
- No agent-policy training in this integration, no automatic genotype evolution, institutional charter generation, World Genome interpreter or causal world graph.
- No scalability claim for large active agent populations; tiny fixture benchmarks cannot establish that.
- No privacy guarantee from population counts, mean, histograms or ECF: group estimates may reveal small-group properties.
- Same-host W3 raw reducer is importable; it is not an unbypassable security boundary for malicious plugin code.

## 6. Next staged gates

**P1: stateful cooperation experiment.** Test whether a bounded learned agent policy adds value over scripted rules when its actions really change the future W3 world. Use held-out seeds, the same resource budgets and explicit rare-event failure metrics; see [Issue #51](https://github.com/CocAgent/OpenWorld/issues/51).

**P2: institutions as reviewed contracts.** Add organization proposals and explicit charters only when they can be compared with the simpler fixed group graph. Never give an agent rights merely because it belongs to a group.

**P3: world configuration research.** A World Genome, if needed, is a versioned, finite scenario configuration, not a mechanism for modifying core accounting/security invariants.

**P4: possible federation.** Study content discovery and versioned artifact portability first; require independently authorized origin and receiver, replay protection, fault recovery and W0 contract review before cross-world action execution. See [two-party consent design](../protocols/ISSUE-035-BILATERAL-CONSENT-DESIGN.md).

**Admission rule:** any new complexity must produce a measurable, task-relevant benefit on held-out worlds **without** breaking provenance, replay, privacy, grants or cost budgets.

**Rollback:** Remove the optional source, tests, demonstration and this note/README pointer. No production state, runtime schema, deployment or paid service was changed.
