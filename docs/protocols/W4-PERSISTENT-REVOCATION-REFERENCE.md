# W4-D1 — Persistent Capability Revocation (Research Reference)

**Status:** EXPERIMENTAL — not a stable OpenWorld/OCP/OWP standard, production identity provider, or distributed authorization service.
**Scope:** [W4 Issue #5](https://github.com/CocAgent/OpenWorld/issues/5), [W0 Issue #1](https://github.com/CocAgent/OpenWorld/issues/1), [W5 Gate #11](https://github.com/CocAgent/OpenWorld/issues/11).
**Motivation:** W5 process tests in [Draft PR #36](https://github.com/CocAgent/OpenWorld/pull/36) demonstrated that the original HMAC authority loses in-memory revoked nonces across process reconstruction.

## What the optional adapter implements

- An explicit, local, SQLite-backed `SQLiteRevocationStore` keyed by issuer, audience and nonce. Revocations are monotone (no reset or delete API).
- `PersistedCapabilityAuthority` subclasses the existing research `CapabilityAuthority` without changing its public implementation. HMAC signed token structure, exact principal/owner/resource/action scope and validity window remain the same.
- Each authorization checks the registry via a fresh read-only SQLite connection; absent or corrupted registry fails closed rather than silently reinitializing during verification.
- New authorities and separate OS processes sharing the same protected database can observe a committed revocation.
- SQLite WAL + synchronous FULL used for writes, and one row per revoked (issuer, audience, nonce), with idempotent repeated revoke.

The default `CapabilityAuthority` remains a **separate in-memory demo issuer**. Real host integrations must make an explicit design decision to expose only the persisted adapter and must not let untrusted code import the base authority or any raw world reducer.

## Reproduce

~~~sh
python -m unittest discover -s tests -p 'test_protocol_revocation.py' -v
python -m unittest discover -s tests -v
python scripts/check_repository.py
~~~

9 focused tests cover valid/rejected scope, revocation across process recreation, simultaneous authority instances, separate Python process, missing registry, missing table, idempotent and issuer-isolated revocation, validity windows and invalid input.

## Known limitations, held open for W0/W4 approval

1. **No authentication provider.** Caller principal is independently authenticated by the trusted host; an attacker can spoof the callback if given Python-process access.
2. **Not externally tamper-resistant.** A malicious OS/database owner can replace the SQLite file with another well-formed one and erase revocations. Use protected storage, external anchors and appropriate key custody before deployment.
3. **Check/use race.** Verification can precede a concurrent revocation while a world action later commits. Transactionally binding permission validity to the **action commit boundary** requires another design and test; this adapter does not provide it.
4. **No issuer key rotation or multi-host replication.** A shared symmetric HMAC key must be protected; the adapter is designed for one trusted local host and database.
5. **No complete access audit, issuance record, retention/erasure policy or secure backup/restoration procedure.**
6. **No sandboxing.** In-process user-generated Python can bypass a gateway, so never run untrusted policies alongside a trusted host.
7. The reference registry is not integrated into `GuardedWorldGateway` by default. It can be injected where `CapabilityAuthority` is used but owner review must cover the entire call chain, isolation and replay semantics.
8. This does **not** change or ratify RFC-006, the exact memory envelope, W3 event journal, cross-owner consent, or production networking.

## Admission and rollback

Require Python 3.11 clean CI, W0 review of durable revocation and identity semantics, W4 security review, W5 multi-process failure testing, and independent authorization audit before any public API or production use. Keep Issue #11 open.

Rollback: revert the new optional module, nine tests and this note. No existing databases, APIs, live user data or deployments changed.
