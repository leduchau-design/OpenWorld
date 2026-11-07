# Related Research and Open-Source Prior Art for OpenWorld

**Status:** Curated, source-linked research map (not a novelty, reproduction, production-readiness or license certification).  
**Reviewed:** 2026-10-28. **Scope:** compositional systems, stochastic multi-agent worlds, social agents, co-evolution and open game infrastructure.  
**Owner workstreams:** W2 mathematics; W3 world simulation; W4 interoperability; W5 evaluation. See [RFC-007](../math/RFC-007-OPENWORLD-MATHEMATICAL-FOUNDATIONS.md) and [session synthesis](../project/SESSION-SYNTHESIS-20261028.md).

The cited work is prior art by its respective authors, **not OpenWorld research results**. Each link below points to an identifiable paper, primary publisher page or author's paper record. Links were checked against public source records during preparation. Reproduction of any result in this repository requires a separate pinned-code, workload, hardware and negative-control record.

## Research papers: foundations and what OpenWorld could test

| ID | Paper (publication) | What the paper supports | OpenWorld use, test or limit |
|---|---|---|---|
| CT-01 | Ghani, Hedges, Winschel & Zahn, [*Compositional Game Theory*](https://doi.org/10.1145/3209108.3209165) (LICS 2018) | Open games with sequential and parallel composition | Model simple negotiation/trade as open games; **not** a ready-made high-throughput world engine |
| CT-02 | Fritz, [*A synthetic approach to Markov kernels, conditional independence and theorems on sufficient statistics*](https://doi.org/10.1016/j.aim.2020.107239) (*Advances in Mathematics*, 2020) | Abstract probability via Markov categories | Tie finite-kernel composition to testable probability laws; categorical semantics **do not** prove runtime security |
| CT-03 | Vagner, Spivak & Lerman, [*Algebras of Open Dynamical Systems on the Operad of Wiring Diagrams*](https://arxiv.org/abs/1408.1598) (2014 preprint) | Operads/wiring diagrams for interconnected dynamical systems | Investigate typed ecology-to-production ports; feedback and clocks need explicit semantics |
| CT-04 | Bakirtzis, Savvas & Topcu, [*Categorical Semantics of Compositional Reinforcement Learning*](https://jmlr.org/papers/v26/24-0197.html) (*JMLR*, 2025) | Category of MDP tasks and pushout-style task composition | Compare composed skills with monolithic baselines on held-out tasks; not automatic safe transfer |
| MA-01 | Schwartz et al., [*POSGGym: A library for decision-theoretic planning and learning in partially observable, multi-agent environments*](https://doi.org/10.1007/s10458-025-09716-6) (*Autonomous Agents and Multi-Agent Systems*, 2025) | POSG planning/RL benchmark; unknown co-player evaluation | Baseline for partial-observation experiments and modeling errors; distinguish game model from scheduler |
| MA-02 | Terry et al., [*PettingZoo: Gym for Multi-Agent Reinforcement Learning*](https://papers.neurips.cc/paper_files/paper/2021/hash/803f7c4c3ff61b71be53a0c803bfb57f-Abstract.html) (NeurIPS 2021) | Multi-agent environment API and AEC semantics | Implement an **adapter**, not claim AEC/Parallel API is an identity or world transaction protocol |
| MA-03 | Leibo et al., [*Scalable Evaluation of Multi-Agent Reinforcement Learning with Melting Pot*](https://proceedings.mlr.press/v139/leibo21a.html) (ICML 2021) | Generalization to unfamiliar social situations | Hold out partners and environments; report reciprocity and cooperation beyond self-play wins |
| MA-04 | Suarez et al., [*Neural MMO 2.0: A Massively Multi-task Addition to Massively Multi-agent Learning*](https://papers.neurips.cc/paper_files/paper/2023/hash/9ca22870ae0ba55ee50ce3e2d269e5de-Abstract-Datasets_and_Benchmarks.html) (NeurIPS 2023) | Procedural multi-task competitive environments; held-out maps, tasks and opponents | Compare procedural world tasks, difficulty, CPU budget. Paper's 1–1024-agent support is **its reported setting**, not OpenWorld capacity |
| SO-01 | Park et al., [*Generative Agents: Interactive Simulacra of Human Behavior*](https://doi.org/10.1145/3586183.3606763) (UIST 2023) | Memory, reflection and planning in a 25-agent social sandbox | Test persistent identity/social events with ablations; plausible dialogue ≠ verified history |
| SO-02 | Vezhnevets et al., [*Generative agent-based modeling with actions grounded in physical, social, or digital space using Concordia*](https://arxiv.org/abs/2312.03664) (2023 preprint) | Generative social simulations with situated actions | Compare narrative agents with rules-based agents under equal budgets |
| SO-03 | Zhang et al., [*A Parallelized Framework for Simulating Large-Scale LLM Agents with Realistic Environments and Interactions*](https://aclanthology.org/2025.acl-industry.94/) (ACL Industry Track 2025) | AgentSociety simulation architecture and large GPU experiment | Study batching, simulation clock and reported resource cost; **do not** map its GPU-scale claim onto a local PC |
| SO-04 | Yang et al., [*OASIS: Open Agent Social Interaction Simulations with One Million Agents*](https://arxiv.org/abs/2411.11581) (2024 preprint) | Very large social-media simulation design | Study inactive/active population distinction and social-network graph updates; one million modeled users ≠ one million concurrent LLM calls |
| EV-01 | Wang et al., [*Enhanced POET: Open-ended Reinforcement Learning through Unbounded Invention of Learning Challenges and their Solutions*](https://proceedings.mlr.press/v119/wang20l.html) (ICML 2020) | Co-evolving challenge/solution populations and transfer | Run generated challenge candidates in **offline lab**, not permit live-rule mutation |
| EV-02 | Dennis et al., [*Emergent Complexity and Zero-shot Transfer via Unsupervised Environment Design*](https://research.google/pubs/emergent-complexity-and-zero-shot-transfer-via-unsupervised-environment-design/) (NeurIPS 2020, PAIRED) | Regret-driven environment design with solvability pressure | Compare generated worlds against random maps and impossible maps |
| EV-03 | Mouret & Clune, [*Illuminating Search Spaces by Mapping Elites*](https://arxiv.org/abs/1504.04909) (2015 preprint, MAP-Elites) | Quality-diversity archives instead of a single champion | Preserve behavioral niches; report diversity descriptors and archive coverage |
| EV-04 | Dharna, Togelius & Soros, [*Co-Generation of Game Levels and Game-Playing Agents*](https://doi.org/10.1609/aiide.v16i1.7431) (AIIDE 2020; PINSKY) | Co-generating game levels and playing agents, with limitations | Prototype restricted game challenges before persistent worlds |

### How to read the evidence

- **Published primary literature** supports the *specific* mathematical model or experiment described above; it does not verify OpenWorld's code, model quality, social realism or emergent civilizations.
- **Preprints** (CT-03, SO-02, SO-04, EV-03 in the versions linked) should be cited with that status unless a reviewed publication has been verified separately.
- **Scalability** is workload-dependent: agent population, simultaneously active policies, inference throughput, environment step rate, wall clock, and infrastructure cost are distinct measurements.
- **Causality** is not established by a chronological event graph or by observing correlations. Controlled simulations can compare counterfactual *model runs*, not prove causal effects in the external world.
- **Agent creativity** does not authorize self-modifying trusted code, uncontrolled reproduction or imported executable mods.

## Open-source reference implementations (evaluate; do not silently copy)

| Software | Closest OpenWorld question | Practical integration decision |
|---|---|---|
| [AlgebraicJulia / Catlab / AlgebraicPetri / AlgebraicDynamics](https://www.algebraicjulia.org/) | Typed wiring diagrams, compositional resource systems | Optional W2 research tooling; no Julia runtime dependency in P0 |
| [POSGGym](https://github.com/RDLLab/posggym) | Benchmark of partially observable multi-agent policies | Evaluate as a benchmark adapter |
| [PettingZoo](https://pettingzoo.farama.org/main/api/parallel/) | Standard multi-agent training environment boundary | Parallel/AEC adapter only after W3 action ordering |
| [Neural MMO](https://github.com/NeuralMMO/environment) | Procedural population-game environment | Independent baseline; not a kernel fork by default |
| [Concordia](https://github.com/google-deepmind/concordia) | Situated generative social-agent simulation | Social-policy comparison; model calls are opt-in and budgeted |
| [AgentSociety](https://github.com/tsinghua-fib-lab/agentsociety) | Distributed social-agent simulation | Study scheduler/compute architecture without assuming similar scale |
| [OASIS](https://github.com/camel-ai/oasis) | Social-network-scale agent interactions | Study social graph/activation assumptions |
| [Godot](https://godotengine.org/) | 2D/3D interactive human client | Candidate UI after W3 local world fixture; client never owns authoritative state |
| [OpenRA](https://github.com/OpenRA/OpenRA) | RTS interaction and modding | Inspiration or standalone comparison; third-party license review before reuse |
| [Luanti](https://github.com/luanti-org/luanti) | Local-first world hosting and community content | Benchmark content/mod workflow; no engine commitment |
| [A2A](https://a2a-protocol.org/) and [MCP](https://modelcontextprotocol.io/) | Agent-to-agent tasks and agent-to-tool access | Optional W4 gateways; neither replaces world simulation action/observation semantics |

**Licensing:** Links are for literature review or adapter feasibility. Check the exact revision, source/assets rights, copyleft/attribution, network, data and dependency licenses **before** importing any code/assets. No third-party code or assets are introduced by this research inventory.

## Priorities and falsifiable research questions

| Order | Experiment | Baseline / negative control | Observable outcome | Existing gate |
|---|---|---|---|---|
| 1 | Finite controlled kernels and partial-observation belief update | Identity kernel, impossible observation, incompatible ports | Valid normalization, explicit failures, deterministic tests | W2 / Issue #15 |
| 2 | One authoritative local world with agent intents and resource ledger | Unauthorized, duplicate, stale, conflicting actions | Replay equality, accounting invariant, no spoofed evidence | W3 / Issue #4 and W0 |
| 3 | Behavioral emergence in a small world (e.g. **30 toy agents**; proposal only) | Rules-only population and memory-off ablation | New organizations/strategies operationally defined, CPU cost, seed variance | W3 + W5 |
| 4 | Held-out unknown partners and transfer between toy worlds | Same-partner training, random-policy baseline | Task success/regret, cooperation, calibration, compute | W5 / W2 |
| 5 | Offline co-evolution of world genomes and policies | Random-map curriculum, invalid/impossible challenges | Archive coverage, novelty, solvability, generalization | Future issue, not adopted runtime |
| 6 | External SDK/world-pack admission | Invalid schema, malicious/noisy code, license mismatch | Fail-closed conformance, budget/capability bounds | W4 + W0 review |

Do **not** conflate the early tactical game proposal (two teams, eight commanders, forty units) with the separate small *living-world research* proposal (one world, three regions, thirty agents, five roles). They measure different capabilities and are neither implemented nor benchmarked by this document.

## Explicit hypotheses not established

1. Category-theoretic composition measurably reduces integration bugs compared with a simple typed protocol.
2. Agent memory, institutional rules and persistent consequences jointly yield engaging emergent game behavior.
3. Agent policies improve by co-evolution or transfer rather than exploiting benchmark reward shortcuts.
4. Federated worlds safely exchange knowledge/blueprints without sharing privileged state or arbitrary resources.
5. OpenWorld reaches large populations, real-world social realism, human-level intelligence, or profitable gameplay.

For each, require baselines, holdout seeds, negative results and resource accounting before announcing success.

## Additional primary papers: population representations, quasi-infinite divisibility and quantum scope (2026-10-29)

These additions answer a **new owner-proposed mathematical route**; they do not revise the scope or authorship of the 16 previously catalogued sources.

| ID | Verified original source | Relationship to OpenWorld | Boundary |
|---|---|---|---|
| POP-01 | [Yang et al., *Mean Field Multi-Agent Reinforcement Learning*](https://proceedings.mlr.press/v80/yang18d.html), ICML 2018 | Approximate agent–agent interaction with mean or neighboring population effect | Approximation assumptions; large-N scalability must be measured |
| POP-02 | [Makkar et al., *Towards Scaling Reinforcement Learning to Massive Populations: Learning Mean-Field Representations*](https://arxiv.org/abs/2609.02928), Aug 2026 preprint | Learn low-dimensional statistics sufficient for a specified offline mean-field task | Its guarantees require its assumptions; not proof all worlds admit a small summary |
| POP-03 | [Muandet et al., *Kernel Mean Embedding of Distributions: A Review and Beyond*](https://doi.org/10.1561/2200000060), 2017 | Distribution embeddings and characteristic kernel theory | Finite empirical embeddings are approximate; no exact history recovered |
| POP-04 | [Rahimi & Recht, *Random Features for Large-Scale Kernel Machines*](https://papers.nips.cc/paper_files/paper/2007/hash/013a006f03dbc5392effeb8f18fda755-Abstract.html), 2007 | Approximate shift-invariant kernels with finite randomized features | May be less useful than histograms or moments on discrete world states |
| PROB-01 | [Lindner, Pan & Sato, *On quasi-infinitely divisible distributions*](https://arxiv.org/abs/1701.02400), 2017 | Characteristic-function QID representations with signed quasi-Lévy measure | Not a default general multi-agent training framework |
| PROB-02 | [Berger, Kutlu & Lindner, *On multivariate quasi-infinitely divisible distributions*](https://arxiv.org/abs/2101.02544), 2021 | Multivariate QID support, weak convergence and moment properties | Does not establish a scalable agent genotype |
| PROB-03 | [Hotta et al., *On freely quasi-infinitely divisible distributions*](https://alea.impa.br/articles/v20/20-34.pdf), ALEA 2023 | Free-probability / freely QID theory, Voiculescu transform | "Free" means noncommutative free probability, not agents' freedom |
| QML-01 | [Gundlach et al., *Quantum Deep Learning Still Needs a Quantum Leap*](https://arxiv.org/abs/2511.01253), 2025 preprint | Grounding for classical-first compute decision | Not a blanket assertion no quantum algorithm can ever help |
| NUM-01 | [Clay Mathematics Institute: *Riemann Hypothesis*](https://www.claymath.org/millennium/riemann-hypothesis/) | Explicitly document why RH is unrelated to current agent-learning problem | Unsolved mathematical conjecture, not an engineering prerequisite |

See the complete [population and agent-genome design](POPULATION-REPRESENTATION-AND-AGENT-DNA.md) for equations, evidence and tests.
