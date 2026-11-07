# W3-H1 — Replay, Request-ID and SQLite Checkpoint Hardening

**Status:** Proposed research patch; **not** production security, persistence or W0 protocol ratification.  
**Scope:** W3 Issue #4 and W5 Gate #11. Follows merged [PR #30](https://github.com/CocAgent/OpenWorld/pull/30).  
**Code and tests:** `src/openworld_superkernel/world_fixture.py`, `src/openworld_superkernel/world_persistence.py`, `tests/test_world_hardening.py`.

## Defects discovered in the first W3 fixture

| Failure mode | Earlier behavior | W3-H1 remedy | Negative control |
|---|---|---|---|
| Replay action budget | A tick could accept over 256 proposals with an explicit higher host budget, while replay silently fell back to 256 and failed | Record the budget inside each canonical tick input and reuse it exactly during reconstruction | 257 actions with 300 budget replay |
| Conflicting request IDs | Two different commands sharing one ID led to one candidate winning by hash ordering, allowing request-content manipulation | Reject **all** variants of a conflicting request ID (identical retry remains idempotent) | Same ID and different transfer amounts yield no transfer |
| Restart recovery | All state and exogenous inputs were memory-only | Local SQLite transaction stores genesis + ordered tick inputs + expected fingerprint, then replays on load | Save, restart/load, multi-tick weather + transfers |
| Silent branch overwrite | No local checkpoint existed or could detect competing writers | Reject same-key checkpoint writes if existing journal is not a prefix | Conflicting fork refused; saved state preserved |
| Unnoticed mutation | Hash chain only existed in memory | Validate stored document digest and reconstructed state fingerprint | Tamper digest/payload and re-run replay |

## Exact boundaries and remaining gaps

- **Only SIMULATED world facts.** There are no externally verified observations or signed actor identities. A local process with database write access can replace the entire file and create a different genesis; digest checks do not authenticate anything.
- **Trusted caller requirement remains.** Agent `principal` is not a bearer token or proof of ownership. The caller must have authenticated its principal outside the fixture; until W0/W4 delivers trusted capabilities and an isolated agent runtime, do not connect untrusted network or Python agents.
- **Crash survival is not certified.** SQLite commits are atomic at the database level, but no actual kill-9, power-loss or cross-process backup/restore experiments have been performed here.
- **Checkpoint storage grows with history.** Writes serialize the complete historical journal, and reads replay all ticks; this is not scalable append-only event sourcing.
- **Identity of a request ID is global to this toy world** and the ordering is deterministic but not fair. Input quotas are trusted host policy, not enforceable security resource budgets.
- **Public contracts unchanged.** No modification to RFC-006 event envelope, HyperMemory schema, MathKernel APIs or the root package export surface.

## Reproducible checks

~~~sh
python -m unittest discover -s tests -p 'test_world_hardening.py' -v
python -m unittest discover -s tests -v
python scripts/check_repository.py
~~~

The W3-H1 test suite adds 11 targeted cases covering request conflicts, retry handling, replay budget pinning, SQLite roundtrips, history fork denial, mutations and unauthorized spending. **Test outcomes must be taken from the actual PR check run**; writing this document does not imply they have passed.

## Review decision

Keep as a separate code-review PR until GitHub CI is green and W0/W5 owners confirm the explicit risk boundaries. Even with green unit tests, do not close Gate #11 or authorize network-accessible world execution.

**Rollback:** Revert W3-H1 code/tests/docs; the previously merged W3 example remains intact. Databases written by W3-H1 are experimental and contain no real-user data.
