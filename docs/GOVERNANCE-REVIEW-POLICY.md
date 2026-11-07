# Open criticism, evidence-based decisions

**Status:** Owner-approved research working policy, 2026-10-31. This process does not supersede security invariants, normative ADRs or independent gate #11.

## Philosophy

Welcome critical comments, including attempts to falsify our preferred hypotheses. Neither agreement, popularity nor a successful PR is scientific validation. Record what could change our mind. Never misrepresent synthetic evidence as observed events or treat a code review as an experimental replication.

## Four dispositions

| Disposition | Use when | Required record |
|---|---|---|
| **ACCEPT** | Supported, in scope, actionable now | Evidence, impact, owner, verification gate |
| **EXPERIMENT** | Plausible but uncertain | Falsifiable hypothesis, baseline, metrics, stop condition, cost cap |
| **DEFER** | Valid but not the current bottleneck | Dependency, revisit trigger; no committed deadline |
| **REJECT** | Contradicted, unsafe or out of scope | Specific rationale and evidence; reconsideration condition |

A security defect requires an immediate safety response, not a routine `DEFER`. No decision may bypass consent, owner isolation, protected provenance or budget constraints.

## Lightweight review record

For substantial feedback, record: **claim**, **source + date**, **observed vs inferred**, **disposition**, **reason**, **measurable next step**, **owner**, **review trigger**. One PR comment or existing issue is sufficient; do not automatically create a new RFC or issue for each comment. Link to the existing gate where possible.

For algorithmic suggestions, compare the simplest feasible baseline under matched seeds, task, compute/storage budgets and held-out data. Report negative outcomes and uncertainty. Define the threshold for admission *before* seeing holdout results. Separate **implemented**, **tested on pinned commit**, **independently reproduced** and **production validated**.

## Scope control: R0 first

Until R0 has one independently reproducible end-to-end agent cycle, prefer fixes that directly improve usability, authorization correctness, replay integrity, or fair evaluation. New mathematical frameworks, federation, GPU/cloud scaling, model adapters and speculative agent evolution are **DEFER** by default unless a concrete blocker is demonstrated.

## Multilingual content

English is canonical for code, comments, schema, RFCs, issues, PRs and technical source-of-truth documentation. Selected explanatory onboarding documents may be in `docs/vi/` under ADR-006; they must identify their canonical English counterpart and review date. English takes precedence when translations diverge. Do not translate every RFC or reproduce a second normative protocol.
