# OpenWorld Execution Handoff — Starting Point for Parallel Agent Work

**Snapshot date:** 2026-10-28  
**Main reference when inspected:** `2b97fead0847054fa2b777973f4a6d59af10990f`  
**Required owner review:** all production-facing actions and changes to common contracts.

## Current priority: complete the independent verification gate

The initial W0, W1 and W5 implementations have landed via PRs #8–#10, but the owner has **not been given independent benchmark and test evidence from the merged SHA** in this consolidation. The immediate gate is [Issue #11](https://github.com/CocAgent/OpenWorld/issues/11), not another feature expansion.

### Minimal local validation

```bash
git clone https://github.com/CocAgent/OpenWorld.git
cd OpenWorld
git rev-parse HEAD
python -m unittest discover -s tests -v
python scripts/check_repository.py
python benchmarks/w5_memory.py --agents 100 --days 60 --seed 2026 --scenario abrupt
python benchmarks/w5_memory.py --agents 100 --days 60 --seed 2027 --scenario stable
python benchmarks/w5_memory.py --agents 100 --days 60 --seed 2028 --scenario noise
```

Capture actual exit codes, Python and SQLite versions, OS/CPU and raw results; no fabricated PASS/FAIL claims. Run at least five previously unused holdout seeds before concluding which predictor performs best. Publish performance regressions and negative controls. Do not introduce paid services or live user data.

## Workstream contracts

| Stream | First bounded assignment | Gate before merge |
|---|---|---|
| W0 | Ratify or revise RFC-006 envelope and provenance semantics | Reviewed schema, adversarial cases, backward-compatibility plan |
| W1 | HM-P1e correctness and genuinely cost-aware adaptive selection | Cross-owner, rollback, retry, and exact-event preservation plus CPU/WAL/latency tests |
| W5 | Independent benchmark suites and honest reports | Holdout results, baselines and negative findings |
| W2 | Controlled stochastic processes and predictive sufficiency proofs/counterexamples | W0 interface alignment and mathematical assumptions |
| W3 | Reproducible sparse-event world fixture | W0 envelope, identity, event-order semantics |
| W4 | Zero-trust capability and A2A/MCP boundary | W0 contract and threat-model review |

W0/W1/W5 may review/fix in parallel using separate branches and PRs. W2/W3/W4 can research interfaces, but do not freeze shared schemas before W0 decisions.

## Merge safety and administration

- One branch per task; do not have multiple coding agents write to the same branch.
- Base new work on a fresh `main`; do not overwrite collaborator changes.
- Do not bypass repository rules or merge solely because a status is green.
- Treat GitHub Actions availability as an infrastructure issue, not permission to report unexecuted tests as passed.
- Do not silently reintroduce historical prototype ZIPs or private context into the public GitHub repository.
- Read [PROJECT-CONTINUITY.md](PROJECT-CONTINUITY.md) and [SESSION-SOURCE-REGISTER.md](SESSION-SOURCE-REGISTER.md) at the start of each new working session.

## Definition of independently validated work

A completed research change includes: commit SHA, input fixtures, deterministic seeds, environment and runtime metadata, clear baselines, quantitative and qualitative failure cases, data/privacy review, scope limitations, rollback instructions and independent review.

**The next integration goal is measured reliability, not headline agent population size.**
