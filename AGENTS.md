# Instructions for coding agents

You contribute to **OpenWorld**. Read `README.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` and `docs/WORKSTREAMS.md` first.

## Boundaries

- Use **English** for all normative public prose, issues, PRs, code comments and commit messages. Only `docs/vi/` explanatory onboarding is allowed in Vietnamese under ADR-006, with canonical English source links and review dates.
- Work only in this repository; never edit AHappy or unrelated projects.
- Prioritize R0 integrated agent validation before new theory/framework work; triage critique ACCEPT / EXPERIMENT / DEFER / REJECT based on measured relevance.
- Use feature branches and small pull requests. Do not merge to `main` without owner review.
- Treat historical benchmarks as synthetic research evidence, not production claims.
- Preserve exact event evidence and provenance; never invent real events from probabilistic replay.
- Explicitly authorize consequential tool actions and cross-owner memory sharing.
- No unapproved paid APIs, secret material, user records or background jobs.
- Local tests and a reproducible test log are required; unavailable CI is not equivalent to passing.
- Do not import historic archives without explicit review of license, secrets and research provenance.
- Stop and report unexplained security, permission, data-integrity or test failures.

## Parallel work

Use the workstream ownership policy in `docs/WORKSTREAMS.md`. Changes to shared contracts require an ADR and compatibility review. Every PR reports its commit SHA, tests, benchmark assumptions, limitations and rollback plan.

## Cross-session continuity

Before starting a new task, read `docs/project/PROJECT-CONTINUITY.md`, `docs/project/DECISION-LEDGER.md`, `docs/project/SESSION-SOURCE-REGISTER.md`, and `docs/project/EXECUTION-HANDOFF.md`. Never present an inaccessible chat share link as an imported source or a historical performance claim as an independently reproduced result. Keep normative repository-facing text in English; ADR-006 allows a narrow Vietnamese onboarding exception.
