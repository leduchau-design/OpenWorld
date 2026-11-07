# OpenWorld Session Synthesis — Game, Protocols, SuperKernel, Civilization

**Status:** Owner-supplied conversation material synthesized as **proposals and hypotheses**; not a ratified ADR, full historical transcript, or measured result.  
**Date:** 2026-10-28. **Repository:** `CocAgent/OpenWorld`.  
**Input:** Six text attachments supplied in the current task, comprising **five distinct files** (one byte-identical duplicate). See [source register](SESSION-SOURCE-REGISTER.md) and [research map](../research/RELATED-RESEARCH-AND-PROJECTS.md).

## 1. How the design evolved (do not mistake iterations for merged decisions)

| Stage from supplied material | Core proposal | Retained | Superseded, deferred or contested |
|---|---|---|---|
| Initial world-war concept | POSG, graph/game theory, agent roles, tactical world, user command | Partial observability, strategic multiagent tasks, game appeal | **AHappy World War** branding; concrete vehicle/weapon-control simulation; any implication that the game exists |
| Community-built open game | Open source, local-first, World Packs, Python agents, authoritative state | No central-service dependency; executable agent adapter; self-host and modding vision | AHappy SSO/infrastructure; proposal to license new server code AGPL is **not accepted** (current repository is Apache-2.0) |
| Standalone OpenWorld | Name **OpenWorld**, independent identity, GitHub, CPU-first prototyping | Canonical name and clean monorepo; offline-first design | Price quotes and future hosting providers are historical estimates, **not commitments** |
| SuperKernel and living civilization | Kernel boundaries, identity/capabilities, verified events, genome, history, social organizations, trust | Guarded action intents, evidence/provenance separation, quota checks | Full autonomous civilization, federation and self-evolution not implemented |
| Open-ended evolution | World genomes, quality-diversity archive, POET/PAIRED-like challenges, institutions, discovery | Offline evaluation and admission gates; controlled design grammar as research proposal | Unbounded live self-modifying rules, million-LLM claims, arbitrary agent spawning |
| Mathematical protocol vision | Applied category theory, Markov categories, POSG, dynamics, typed interfaces, OCP | Composition **as a research method**, not a P0 dependency; shared interfaces need tests | Rename project to **Open Civilization Protocol** or freeze OCP/OWP as existing standards |

These source sections are **historical recommendations in the attachments**. The repository's [decision ledger](DECISION-LEDGER.md) and [ADRs](../DECISIONS.md) determine the current recorded state, not the newest rhetorical proposal.

## 2. Current boundaries anchored in the repository

- **Accepted:** OpenWorld name, independence from AHappy, English-first, single monorepo, Apache-2.0 for new repository-authored content and local-first validation.
- **Implemented research fixtures:** HyperMemory P1e and memory contracts; finite MathKernel experiments and standalone pure composition/resource-transfer example. Presence in `src/`, `examples/` or `tests/` is **not** a production acceptance claim.
- **Proposed:** Exact evidence vs predictive memory, controlled stochastic agent semantics, OWP/OCP-style world/agent interface family, world genome, civilization institutions, federation, quality-diversity and discovery grammar.
- **Deferred:** Publicly frozen cross-world protocol, untrusted mod execution, distributed world transactions, complete game client and autonomous agent evolution. A2A/MCP are optional adapters, not authoritative game-state protocols.
- **Outstanding:** Independent merged-main verification in [Issue #11](https://github.com/CocAgent/OpenWorld/issues/11). Other W0/W1/W2/W3/W4/W5 gates are individually tracked.

**Important correction:** An earlier session argued OCP should be the *main project name* and category theory the immediate mathematical core. That conflicts with the confirmed OpenWorld repository and accepted P0 staging. Preserve OCP solely as a **working name for a future protocol/civilization profile**, pending W0 review; applied category theory should be an optional compositional formalization, not a reason to replace the existing MathKernel.

## 3. A coherent target architecture, explicitly future-facing

```text
Human / self-hosted game clients / optional external agents
           |              |
    Human intent     Agent policy (rules / Python / RL / opt-in LLM)
           \              /
            [Proposed typed Observation / ActionIntent gateway]
                              |
             W0: identity, capabilities and admission
                              |
             W3: authoritative world transition / event order
                     |                     |
                World modules          Exact event ledger
              (ecology, economy,       + predictive state
               society, scenarios)      (W1 + W2)
                     |
              Reproducible local world
                     |
             W5: independent benchmark / replay / safety
        ---------------------------------------------------
         Off-line evolution lab       W4 optional federation
         (candidates -> tests)        (A2A/MCP adapters)
```

This diagram is **a target separation of concerns**, not a deployed architecture. No raw model output or community worker may directly commit authoritative state. A simulation hash is not externally authenticated evidence.

### Mathematical strata

1. **Executable P0:** finite controlled stochastic kernels, Bayes updates, predictive-state limitations, resource accounting, deterministic replay semantics.
2. **Composable extension:** typed processes, category laws for pure arrows, open dynamical systems and Markov-kernel composition; explicit clock/effects for feedback and shared writes.
3. **Multiagent evaluation:** POSG, unknown-partner generalization, heterogeneous policy/goal models, graph interaction and institution dynamics.
4. **Offline evolution:** POET/PAIRED-inspired world challenges, MAP-Elites-style diversity and policy admission. Must have solver feasibility and avoid reward gaming.
5. **Federation:** explicitly consented identity/blueprint/content exchange; never presume asset ownership, wealth, ranking or provenance transfer between worlds.

## 4. Reconcile four practical conflicts

| Conflict in supplied sessions | Repository-aligned resolution |
|---|---|
| Project named AHappy World War, AHappy OpenWorld, OpenWorld, or Open Civilization Protocol | **OpenWorld** is the single confirmed project name. Game theme and OCP are separate *working* proposals; no rename, no automatic AHappy integration |
| 'Category Theory is the core' vs 'POSG is the core' vs current RFC-007's stochastic P0 | **Different layers**: category theory composes modules; stochastic kernels model transitions; POSG models strategic interaction; trusted execution enforces state/permissions |
| Fully open mods, decentralized volunteers vs authoritative state | Local and federation may be open, while each live world chooses an authoritative state owner; untrusted code needs isolation; volunteer compute cannot grant itself capabilities |
| Agent 'memory' and stories vs event-ledger truth | Preserve evidence provenance: observed claims require source; simulated narratives are labeled `SIMULATED`; inferences are not promoted to `VERIFIED` |
| 'Millions of agents' and broad civilization vs CPU-first validated baseline | Start with bounded toy fixtures and measured scaling. Stored identity count is not active inference throughput |
| Competing first experiments: 40-unit tactical arena vs 30-agent social world | Treat as **two independent optional experiments**, each requiring a declared success gate; neither defines the production kernel |

## 5. Proposed next sequence (not a delivery commitment)

| Track | Proposed next action | Gate |
|---|---|---|
| W5 | Independently run full merged-main test and resource measurement | Issue #11, pinned SHA, environment, negative findings |
| W0 | Decide owner identity, observation visibility, action provenance, versioned event contract | Review RFC-006 and compatibility; no public freeze yet |
| W2 | Keep P0 stochastic executable semantics; later compare categorical diagram tool against simple typed pipeline | Fewer integration errors **measured** under same workload |
| W3 | Create one offline authoritative world with resource conservation, action conflicts and replay | No unauthorized writes; same pinned inputs -> same state |
| W4 | Sketch OWP observation/action adapter and optional MCP/A2A tools | Fail closed on missing rights; no code execution in live kernel |
| Product research | Test 30-agent living-world fixture **or** small tactical arena, not both as a single requirement | Human usability, narrative interest, CPU/budget measured |
| Future evolution | Run candidate policies/world genomes in sandbox/offline lab | Holdouts, archive diversity, solvability, admission review |
| Future federation | Exchange versioned blueprint and content only at first | Explicit consent, dependency/license and trust tests |

**Scientific caution:** No evidence from these attachments establishes a safe, fully formed self-evolving civilization, human-like cognition, or a general theorem of emergent behavior. Those are explicit hypotheses to test.

## 6. Source integrity and terminology

The uploads are owner-provided extracts of previous ChatGPT-style discussions, not independently fetched complete platform transcripts. Two uploads are byte-for-byte identical; only one source concept is counted. Earlier shared chat URLs remain `PENDING_ACCESS` in the [register](SESSION-SOURCE-REGISTER.md). This synthesis does not import entire raw discussions, embedded unrelated images, marketing quotes or suggested third-party code into the public repository.

Public repository prose is intentionally English (ADR-001). The original Vietnamese texts remain the owner's source material and are not copied verbatim into this public document.

## 7. October 29, 2026 — population learning and mathematical representation refinement

This addendum records the owner's **new research question** about scaling agent training and encoding agent "DNA", rather than pretending it was fully specified in earlier sessions. Its [mathematical design](../research/POPULATION-REPRESENTATION-AND-AGENT-DNA.md) is **proposed**, not an accepted public protocol or demonstrated trained society.

**Retained from earlier sessions:**

1. Keep **OpenWorld** independent, local-first, game-capable and openly extensible. An autonomous civilization is a falsifiable long-term goal, not a shipped feature.
2. Keep the **trusted world state** and replay contract separate from AI policy inference and evolving genome candidates. The identity, owner, grants and exact history are never reconstructed from a predictive vector.
3. Allow **heterogeneous roles, private histories and multiobjective strategies**; neither a single universal agent policy nor a single maximizing winner is an architectural requirement.
4. Use **applied category theory for typed composition**, W2 controlled stochastic kernels for transitions, **POSG and mean-field MARL** for decisions, and **sparse graphs** for local events and relationships.
5. Use offline evolutionary candidate generation/quality-diversity, tests and human/W0-approved admission. Never auto-execute new agent code or mutate production rules.

**New choices to evaluate (not frozen):**

- A *stratified empirical population measure* per role/region, represented by an optional bounded empirical characteristic-function sketch, **alongside** local graph, individual observation and protected memory.
- *Typed, content-addressed AgentGenome* with bounded trait parameters, role, policy artifact reference and lineage. Genome is not model weights, identity, owner permissions or proof of intelligence.
- Shared role policies conditioned on individual traits and local context, with independent benchmark baselines. Count training steps, active policy calls and cost separately from number of stored agents.
- Explicit counterexamples: finite-frequency aliasing, time-order information loss, rare-strategy flattening and privacy leakage from small aggregates. Quasi-infinite divisibility and free probability are **not** default game-state representations.
- Riemann hypothesis and quantum computation are **out of P0 scope**, with reasons and primary sources documented in the design.

**Operational status at this synthesis:** W3, W4, W5 and SEC-002 contain research code on the checked repository `main`. Their existence/green tests do not close independent Gate #11, establish actual two-party consent, or authorize untrusted multi-owner deployment. Earlier "W3 next" action descriptions in sections 2/5 were **time-specific proposals** and must not override the current GitHub tree.

**Proposed next evaluation:** compare role-wise mean, role-wise histogram, ECF and learned embeddings under identical holdout seeds, while preserving exact critical interactions. The new Python source is a research fixture with 0 learning loops and 0 policy training runs.

## 8. October 29, 2026 — group composition as a practical integration gate

The source excerpts about independent community worlds, fictional strategy games, organization genesis, world genomes and compositional mathematics are **not** separate adopted runtime specifications. Their first integration experiment is the [W3 Population Links P0](../world/W3-POPULATION-LINKS-P0.md): an owner-controlled local simulation with typed population rosters, directed link quotas and grants checked before the existing W3 reducer. It preserves the **OpenWorld** project identity, the default **cross-owner denial** and all exact/simulated provenance distinctions.

Organization generation, world-genome mutation, federation, OCP/OWP protocol standardization, learned cooperative behavior and independently authenticated bilateral consent are **not implemented by this adapter**. They require distinct tasks, gates, security contracts and actual evidence; do not claim they emerge from a scripted three-group demonstration.
