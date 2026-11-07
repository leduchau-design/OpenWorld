# OpenWorld Decision and Hypothesis Ledger

This ledger is a **living summary**. It does not supersede normative ADRs in [docs/DECISIONS.md](../DECISIONS.md) or the proposed RFC-006. A prior chat recommendation is not an adopted interface, and a merged code change is not a production qualification.

| ID | Decision or hypothesis | State | Evidence / next action |
|---|---|---|---|
| OW-D01 | Project name and repository: **OpenWorld**, `CocAgent/OpenWorld` | **Confirmed** | Public GitHub repository |
| OW-D02 | The project is independent from AHappy | **Confirmed scope** | Owner's earlier explicit architecture choice; project documents |
| OW-D03 | English-first public artifacts and one monorepo | **Accepted; scoped Vietnamese docs exception** | ADR-001 amended by ADR-006; ADR-002 |
| OW-D04 | Separate agent identities from shared model weights and per-agent memory/state | **Design principle** | OpenWorld architecture, requires scaling evaluation |
| OW-D05 | Memory uses exact evidence + predictive state + replayable generative processes | **Design principle; partial prototype** | RFC-006 + HM-P1e; exact/predictive interfaces evolving |
| OW-D06 | A simulated or inferred memory must not masquerade as observed history | **Required safety invariant** | RFC-006 proposed; source checks exist but not production-enforced end to end |
| OW-D07 | Digital genome and epigenome can encode stable initial traits and adaptive parameters | **Research hypothesis** | Prior conceptual design; not a biological claim or general data compression theorem |
| OW-D08 | Characteristic functions support stochastic representation but not by themselves temporal dependence | **Mathematical clarification** | Needs family of finite-dimensional laws / controlled transition model |
| OW-D09 | Predictive sufficiency is scoped to tasks, horizon, observations, actions and evaluation loss | **Mathematical requirement** | W2 / RFC-006 |
| OW-D10 | Adaptive models (static, discounted fast/slow, ensembles) should be selected only when they add measured benefit | **Research hypothesis** | HM-P1e heuristic; W5 holdout/ablation required |
| OW-D11 | Retain exact events according to retention and user rights; do not deduce authenticity from a hash alone | **Required safety invariant** | RFC-006 proposed; operational security pending |
| OW-D12 | Implement CPU-only tests and independent benchmarks before GPUs/distributed runtime | **Accepted execution policy** | ADR-004 and Issue #11 |
| OW-D13 | W0/W1/W5 first, W2/W3/W4 after interface/quality review | **Accepted work order** | Issues #1–#6; W0/W1/W5 PRs merged but test gate remains open |
| OW-D14 | Apache-2.0 applies to new OpenWorld-authored content; historical prototypes need audit before release | **Accepted publication boundary** | ADR-005; repository LICENSE |
| OW-D15 | OpenWorld Companion and Civilization are possible future products, not current released features | **Product hypotheses** | Needs validated user value, consent, security and operational cost |
| OW-D16 | Billion-scale populations are aspirational research goals, not benchmark results | **Explicit non-claim** | Issue #11 / research status |
| OW-D17 | The first five mathematical pillars form the **proposed P0 MathKernel**; sparse graph processes follow, category-theoretic formalization is not a runtime P0 dependency | **Proposed staged architecture** | RFC-007 (PR #14), Issue #3, executable P0 Issue #15; owner/math review pending |

## Acceptance distinctions

- **Proposed:** design agreed for exploration but may lack owner signoff or implementation.
- **Implemented:** source committed to repository; not automatically tested or deployed.
- **Independently verified:** reproducible execution on a pinned SHA and documented environment.
- **Deployed:** actual operating system with measured monitoring and safety controls.
- **Rejected/superseded:** keep historical trail explaining what changed and why.

## Known negative results and open tradeoffs

Earlier dialogue reported that HM-P1d ensemble-style adaptation sometimes improved drift prediction yet lost to a simpler static estimator in stable/noisy conditions, while consuming more resources. Earlier HM-P1 and HM-P1c storage performance varied with SQLite WAL and checkpoint behavior. These historical results are **not independently verified here** and must be reproduced before becoming acceptance evidence.

The memory compiler is not an automatic truth detector. A compressed summary cannot, in general, answer every query that exact historical records could answer. A purported 'cost-aware' gate must measure total runtime cost, not only impose a threshold on predictive loss.

## What not to infer

The presence of RFCs, issue tickets, unit tests, or GitHub merges does not establish user consent enforcement, identity key management, globally distributed correctness, algorithm novelty, published research, or production reliability.

## October 2026 design synthesis — proposals, not new approved interfaces

| ID | Design decision or hypothesis | State | Evidence / gate |
|---|---|---|---|
| OW-D18 | Retain **OpenWorld** as the project and repository identity; OCP/OWP are working protocol ideas | **Confirmed name / proposed protocol** | [Naming](../PROJECT-NAMING.md); [session synthesis](SESSION-SYNTHESIS-20261028.md); W0 review needed |
| OW-D19 | Model composition through applied category theory where useful, *without* replacing stochastic P0 | **Research proposal** | RFC-007; [research map](../research/RELATED-RESEARCH-AND-PROJECTS.md); compare vs simple typed pipelines |
| OW-D20 | Plan an authoritative, offline living-world fixture with scoped agent intents and replay | **Future W3 hypothesis** | Issue #4; replay, unauthorized/stale/duplicate and accounting controls |
| OW-D21 | Separate online trusted execution from offline policy/world-genome evolution | **Proposed trust boundary** | Admission, benchmark, solvability and resource quotas; W0/W5 review |
| OW-D22 | Treat 30-agent social-world and 40-unit tactical arena as **separate** optional experiments | **Product/research hypotheses** | [Session synthesis](SESSION-SYNTHESIS-20261028.md); no current capacity or gameplay claim |
| OW-D23 | Build evidence-grounded, cross-world exchange only after scoped owner and federation contracts | **Deferred proposal** | W4 issue #5; no unilateral transfer of authority/resources/evidence |

## October 31 integration and accessibility decisions

| ID | Decision or hypothesis | State | Evidence / next action |
|---|---|---|---|
| OW-D24 | Prioritize R0 local integrated agent cycle, then R1 same-owner coordination, R2 measured adaptation, R3 authenticated cross-owner consent, R4 scaling | **Owner-approved planning order, not implemented** | [R0 scope/gates](../R0-INTEGRATED-AGENT-VERTICAL-SLICE.md), [roadmap](../ROADMAP.md), independent Gate #11 remains OPEN |
| OW-D25 | Welcome criticism but decide ACCEPT / EXPERIMENT / DEFER / REJECT with evidence and explicit revisit triggers | **Accepted process** | [Review policy](../GOVERNANCE-REVIEW-POLICY.md); no automatic issue/RFC inflation |
| OW-D26 | Add limited Vietnamese explanatory onboarding while retaining English normative artifacts | **Accepted scoped documentation exception** | ADR-006 and [docs/vi](../vi/README.md); source-link/review-date requirement |
