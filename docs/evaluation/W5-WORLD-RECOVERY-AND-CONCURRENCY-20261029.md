# W5 — World Recovery, Concurrency and Adversarial Evaluation

**Status:** Research gate proposal, not production acceptance.
**Date:** 2026-10-29. **Tracks:** W5 Issue #6 / Gate #11, W3 Issue #4, W0 Issue #1, W4 Issue #5.
**Baseline:** Merged W3 PR #30 / PR #31 and pre-existing SEC-001 and scoped W3 gateway.

## Falsifiable controls

| Probe | What is exercised | Expected result | Does NOT prove |
|---|---|---|---|
| Process restart | Another Python process loads committed SQLite checkpoint | Identical SIMULATED state digest | Hostile files, physical power-loss resilience |
| Interrupted SQL | Child exits abnormally after uncommitted mutation | Previous committed checkpoint survives | Disk/controller power-loss durability |
| Concurrent fork writers | Two processes prepare distinct branches, then race | One commit; other rejected as fork; replay matches | Fairness, network consensus |
| Backup | SQLite online backup and restore | Identical reconstructed state | Offsite custody, recovery time objective |
| Revocation restart | Recreate symmetric grant authority after revoke | **KNOWN GAP:** previously revoked nonce is accepted again | Durable revocation or production authorization |
| Sparse graph benchmark | Chain, hub, disconnected graphs under multiple seeds | All replay; record timing, disk, contact visits and memory | High scale or meaningful agent behavior |

**Caution:** The revocation test is intentionally a passing negative *demonstration of a security weakness*. A green test run cannot be presented as a durable security guarantee.

## Reproduce (CPU-only)

~~~sh
python -m unittest discover -s tests -p 'test_w5_world_recovery.py' -v
python -m unittest discover -s tests -v
python scripts/check_repository.py
python benchmarks/w5_world_recovery.py --agents 30 --ticks 20 --seeds 3 --seed-start 3101
~~~

Benchmark output is JSON (stdout or explicitly supplied --out), with Python/SQLite/platform, wall and process CPU, p95 world tick time, full-journal checkpoint and read-back time, WAL+SHM+DB bytes, tracemalloc peak and Linux peak process RSS. One short run does not support general throughput extrapolation.

## Limits and unresolved gates

1. Principal identity still depends on a trusted host callback. In-process Python policies can bypass the demonstration gateway and call the reducer directly. Do **not** run hostile user code in this runtime.
2. In-memory revocation is lost at authority restart. W0/W4 needs durable, versioned, auditable grant decision state, trusted clocks and appropriate token lifecycle policy. HMAC alone is insufficient.
3. The W3 replay journal includes inputs and action budgets but **not capability proofs or authorization decisions**. Replay is a proof of simulated state consistency, not a replay of independent authentication.
4. SQLite and local SHA checking do not authenticate externally observed events or defend against a fully compromised host that replaces whole files. SEC-001's HMAC anchor covers **HM exact-event streams**, not W3 checkpoints.
5. A child exit inside SQLite transaction tests normal rollback, **not** actual power loss. Further work includes WAL long reader, kill/restart under load, RPO/RTO, backup retention, multiple disks and offsite custody.
6. The raw reducer permits cross-owner signals in the toy benchmark; the signed W3 gateway currently denies those. This benchmark **does not** demonstrate secure social interaction between owners.
7. Agent learning, society emergence, practical gameplay and economically meaningful behavior remain unmeasured.

## Evidence rules and decision

CI on the exact PR head is required for an implementation-level test result. W5 independent benchmarking, owner authorization, a security review and W0/W4 contract signoff remain separate gates.

**No change** to the existing W0 event schema, W3 reducer, W1 memory, W2 math kernels, runtime exports, CI configuration, real user data or deployment settings. No third-party dependencies and no paid services.

Rollback: revert the three W5 additions; no migration or external side effects.
