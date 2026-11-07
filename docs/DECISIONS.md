# Architecture Decision Records

## ADR-001 — English-first
**Status: Accepted; documentation scope amended by ADR-006.** English is canonical for code comments, normative documentation, issues, pull requests and RFCs. Historical studies may retain their original language only with reviewed English context.

## ADR-002 — One OpenWorld monorepo
**Status: Accepted.** SuperKernel, HyperMemory, MathKernel and world simulation share versioned contracts until extraction is justified.

## ADR-003 — Conservative memory provenance
**Status: Proposed.** Unknown cases must not be promoted from synthetic or inferred knowledge into historical observation. Critical event types route to an exact ledger.

## ADR-004 — Local-first validation
**Status: Accepted.** Do not require a paid GitHub Actions pipeline. Record independently reproducible local test evidence, and do not bypass repository protection.

## ADR-005 — Public artifact boundaries
**Status: Accepted for bootstrap.** Apache-2.0 applies to newly authored files. Older prototype archives require an independent rights, secrets, safety and reproducibility review before publication.

## ADR-006 — Vietnamese explanatory onboarding (2026-10-31)
**Status: Accepted by owner for a bounded documentation exception.** Only selected explanatory guides in `docs/vi/` may be Vietnamese. English remains the single normative source for protocols, public interfaces, schemas, RFCs, code, comments, issues and PRs. Translations must link their canonical source and review date, cannot create new promises, and must not be automatically generated for every RFC. When a translation disagrees with English, the English source controls. This amendment narrows ADR-001; it does not overturn English-first engineering.

## ADR-007 — Integration-first roadmap and evidence-based criticism (2026-10-31)
**Status: Accepted for research prioritization, not scientific certification.** Gate R0 on one reproducible same-owner cycle, then R1 coordination, R2 measured adaptation, R3 independently approved cross-owner transactions, R4 evidence-driven scale. Preserve the previous roadmap as history. Triage feedback ACCEPT / EXPERIMENT / DEFER / REJECT under [the review policy](GOVERNANCE-REVIEW-POLICY.md); no new framework becomes default without matched baselines and held-out evidence. No automatic merge or bypass of Issue #11.

## ADR-009 — Owner-scoped exact event IDs with explicit migration (2026-11-03)
**Status: Proposed; security remediation awaiting pinned-head review.** The former global `UNIQUE(event_id)` allows cross-owner ID collisions to deny writes and distinguishes foreign-event lookups from absent IDs. New stores use `UNIQUE(owner_id,event_id)`; `exact_event(event_id, requester_owner_id=owner)` scopes SQL lookup to the requester and returns `None` for both absent and foreign IDs. This is an intentional low-level API behavior change, not authentication. Authenticated access remains the caller/host facade responsibility.

**Legacy migration rule:** refuse implicit schema changes. Operator must explicitly set `migrate_legacy=True` with an unused `legacy_backup_path` on a controlled maintenance run; SQLite backup and a full-row digest are verified before one transaction rebuilds the table. Unknown indexes, triggers, dependent views/foreign keys, corrupt evidence or unexpected schema fail closed. The external backup must be retained and verified before deployment. A migrated DB with duplicate IDs across owners **cannot** be safely reverted by simply restoring old code and continuing writes. See [migration runbook](security/HM-EVENT-NAMESPACE-MIGRATION.md). No production migration is authorized by adopting this ADR.
