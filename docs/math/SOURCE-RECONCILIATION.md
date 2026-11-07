# OpenWorld MathKernel — Source Reconciliation

**Date:** 2026-10-28  
**External source requested by owner:** https://chatgpt.com/share/6ae21436-a858-83ec-b90e-c55e0f507b06

## Access outcome

The external share URL could not be retrieved by the available page reader (fetch disabled). Its complete transcript, chronology and exact authorship **have not been verified**, and it must not be described as ingested. This is separate from the two earlier chat-share URLs already recorded in the [project source register](../project/SESSION-SOURCE-REGISTER.md).

## Inputs actually inspected

1. The owner's selected excerpt provided verbatim in the current task: seven mathematical pillars and the proposed central role of controlled stochastic processes, predictive state, information theory, verifiable exact-event memory, categorical composition, digital genome and characteristic functions.
2. Local `RFC-004-MATHEMATICAL-CORE.md` research artifact from the previous OpenWorld work, consulted for formulas, scientific limitations and references; its implementation/benchmark claims were not newly validated.
3. GitHub `docs/ARCHITECTURE.md`, `docs/rfcs/RFC-006-MEMORY-AND-AGENT-CONTRACTS.md`, `docs/project/PROJECT-CONTINUITY.md`, `docs/DECISIONS.md`, and Issue #3 as accessed through the connected repository.
4. No content was inferred from the unreadable share URL.

## Filter applied

| Item | Decision | Reason |
| --- | --- | --- |
| Controlled Markov kernels, kernel composition | Include as P0 | Foundational, executable and contract-relevant |
| POMDP and task-bounded predictive state | Include as P0 | Distinguishes true memory utility from arbitrary compression |
| Information bottleneck, resource-aware decision loss | Include as P0 objective | Makes memory tradeoffs measurable; no automatic physical compression |
| Exact protected evidence and provenance | Cross-reference RFC-006 | Critical invariant, already specified; avoid duplicating policy as a new implementation |
| Characteristic functions, digital genome | Include with strict caveats | Distribution does not imply path; no external-observation recovery |
| Prequential Bayesian/discounted/ensemble learning | Include at research level | HM-P1e exists, but superiority not established |
| Sparse graph and population dynamics | Defer to W3 | Requires measured agent interaction workload |
| Category theory and Markov categories | Defer formal proofs to later phase | Composition language is useful, not P0 runtime dependency |
| Full chat transcript, speculative social/economic layers | Do not import | Not verified, and not needed for P0 |
| Previous prototype size/speed claims | Do not reuse as test evidence | Require independent merged-main verification (#11) |

## What remains blocked

To attribute additional decisions to the shared session, obtain an authorized transcript/export, screen private/proprietary content, map claims to original evidence, and update this register through another reviewed PR. Nothing here asserts that the inaccessible source contained exactly the same material as the selected excerpt.

**Current status:** PARTIAL, VERIFIED-EXCERPT-ONLY / LOCAL-RFC-004; EXTERNAL-TRANSCRIPT-PENDING.
