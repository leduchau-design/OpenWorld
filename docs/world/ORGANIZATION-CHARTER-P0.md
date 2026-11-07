# Organization Charter P0 — Eligibility without Authority

**Status:** Pure research reference for the single-owner W3 fixture. No organization has actually been created, no charter is approved, and no runtime permission changes.  
**Scope:** [P0 population links](../world/W3-POPULATION-LINKS-P0.md), [P2 cooperation](../evaluation/P2-STATEFUL-COOPERATION-EXPERIMENT.md), W0 and W4 trust review.

## Smallest feasible interpretation of an institution

In this phase an organization is only a **proposed configuration**: a canonical group of existing member agent IDs, an owner claim, a written purpose, a small proposed set of directional PopulationLink constraints, a maximum total action budget, and an expected W3 tick with expiry. It is **not** a sovereign entity, business, autonomous government, smart contract or capability issuer.

The evaluator in [institution_proposals.py](../../src/openworld_superkernel/institution_proposals.py) checks that the requested member IDs exist and belong to one same owner, the caller's trusted-host owner claim matches, and every proposed link is a **subset** of the existing W3 PopulationRouter link rules. It rejects quota escalation, missing group representation, stale proposals and conflicting membership. The output is only ELIGIBLE_FOR_OWNER_REVIEW or REJECTED with a deterministic proposal content hash and exact reasons.

**A positive review neither creates an organization nor writes to W3, executes an action, grants consent, creates a token, expands access rights, or changes an owner.** A digest is not an attestation/signature and says nothing about whether the proposer is authentic. All real approvals and durable authorization are deliberately out of scope.

## No privilege inheritance

Being a charter member does not authorize reading another member's W1 memory, spending their resources, impersonating their owner, modifying a World Genome, or bypassing PopulationRouter. A later implementation must design independent consent and revocation before creating any binding governance outcome.

A proposed budget is only an upper bound for **review**, not a separate scheduler. Every actual agent-to-agent action must continue through the trusted W3 gateway, existing resource constraints and independently verified owner-scoped grants.

## Negative cases to verify

- A member belongs to another owner or is unknown to the current world.
- The proposal points to a missing or newly invented link, adds action types, raises transfer amounts or increases per-tick quotas.
- Requested aggregate quota exceeds its own charter budget.
- Membership is duplicate, unsorted or does not represent both ends of a proposed link.
- Owner claim mismatches the caller's trusted-host identity or the W3 world tick changed.
- Review must be pure: same world fingerprint and router link configuration before and after.
- A syntactically content-addressed proposal does not claim a valid signature, verified provenance or user authorization.

## Reproduction

Run the single-file unittest suite: tests/test_institution_proposals.py, then run the entire repo Python suite and repository layout check. The tests construct only synthetic local W3 agents and do not import or run any untrusted model code.

## Admission gates before any real institution exists

1. W0 must specify owner, membership, charter version, actual approval and revocation semantics.
2. W4 must supply externally authenticated principals and enforce durable, auditable, atomic permissions at action commit. The current pure evaluator has none of these.
3. W3 must define governed state transitions, event provenance and replay for a **ratified** charter lifecycle. The current module does not modify W3.
4. W5 must test negative coalition/privilege, long-running state, crash recovery and whether organizations outperform simpler fixed groups in a predeclared task.

**No federation or cross-owner institution is proposed for execution.** The design research on inter-world discovery remains separate until explicit two-party consent and trustworthy evidence transport are accepted.

**Rollback:** delete the optional source, tests and note. There is no database, migration, live agent or deployment to undo.
