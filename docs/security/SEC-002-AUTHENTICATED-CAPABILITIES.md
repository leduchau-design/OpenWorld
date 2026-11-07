# SEC-002 — Durable Agent Capabilities and Authenticated Subject Binding

**Status:** Research-only implementation candidate. **Issue:** #34. No production authentication or multi-tenant security certification.

## Security contract

The new `durable_identity.py` module separates two independently keyed concerns:

1. **LocalSessionVerifier:** an offline stand-in for a trusted identity provider. Its short-lived signed session supplies the authenticated `sub` and a designated service `aud` rather than accepting a caller's raw `requester_owner_id`. Crucially, the `issue()` method MUST NOT be reachable by an untrusted client. This is not proof of any human's identity, and a stolen bearer session remains usable until expiry.
2. **DurableCapabilityAuthority:** a second, separately keyed HMAC issuer plus a SQLite grant registry. An authenticated owner may issue a grant to an explicitly named subject for one `(owner, agent, resource, action, purpose)` and designated audience. Each grant has a random `jti`, key ID, `nbf`, `exp`, maximum-use budget (1..10), current use count, and durable revoked flag. Authorization verifies the independently signed session **and** stored grant inside `BEGIN IMMEDIATE`, atomically consumes one use and records an audit receipt. Missing DB records, wrong audience, wrong subject, incorrect scope, exhausted use budgets and revoked/missing keys fail closed.

`AuthenticatedMemoryReader` provides a narrowly scoped experimental gateway for HM-P1e. It consumes authorization prior to reading a private agent state or exact event. The facade additionally checks the exact-event row's agent ID, because W1's raw event reader enforces owner but not agent membership. A denied wrong-agent lookup may still consume a one-use grant, by design; authorization and the raw memory read are not an atomic cross-store transaction. The memory store itself MUST NOT be accessible from an untrusted process. Bearer capabilities are never assumed to authenticate the truth of observed world events.

## Key rotation and restart

The registry persists key identifiers and status (`active`, `retired`, `revoked`). Rotation retires the previous signing key and makes new issuances use the new key; previously issued capabilities may remain valid on a **retired** key until expiry, exhaustion or revocation. Explicit key revocation disables the old key. Historical key IDs cannot be reused. Actual bytes stay outside SQLite via injected keys. Missing active key on restart blocks startup; missing retired key blocks old grant verification.

**Important:** The example `rotate()`/`revoke_key()` methods are **privileged administrator operations**, not authorization endpoints. A trusted operator or KMS must control who can call them, provision keys and replace old application instances. Session signing keys and capability signing keys must be independently held. In-memory key dictionaries and a local SQLite database alone are NOT secure key custody.

## Threat boundaries and limitations

| Threat | Tested or addressed | Remaining issue |
| --- | --- | --- |
| Claimed owner/subject strings | Signed session bound to issuer/audience; signed grant bound to subject | Local issuer is an IDP simulation; account registration/authentication is absent |
| Replay/excess usage | Atomic SQLite `used < max_uses` plus durable revocation | Theft of **unused** bearer token still permits use before expiry |
| Restart/old-key exposure | Durable revocation and retired/revoked key states | DB **rollback to an older backup** could resurrect revoked grants absent an external monotonic anchor |
| Two concurrent authorizations | SQLite `BEGIN IMMEDIATE` serializes use count updates | Multi-process/host and power-loss chaos, latency and federation not certified |
| Grant tampering | Strict JSON parsing, HMAC, registry body match | A compromised issuer key together with DB write privileges defeats local custody |
| Cross-owner memory access | Exact scoped access via wrapper | Underlying `HyperMemoryP1e` remains importable/callable inside the trusted process |
| Source provenance | Explicitly not upgraded | Valid grant is not evidence that an outside-world observation is true |
| Consent | Purpose-scoped issuer authorization | Receiver consent, bilateral execution and withdrawal still require Issue #35 |
| Read side-effects | Authorization consumed before read | The grant-use debit and memory read are **not one cross-database transaction** |

## Owner review and integration gate

- A hosting service must keep session-issuer methods, signing keys, the grant DB and raw HM-P1e instances away from untrusted code. Do not expose this Python class as a production security boundary.
- Add an external, independently authenticated identity provider (OIDC/mTLS or equivalent), key-management and external monotonic audit anchor before real accounts.
- Test DB rollback after revocation, multi-process write contention, NTP/skew policy, session theft, backups, restoring keys and disaster recovery.
- Explicitly design consent, erasure, audit retention and receiver authorization. Until then **cross-owner operations remain blocked** by `world_guard.py`.
- Run all repository tests on the exact PR/merged SHA, including the integrated HM-P1e tests. The isolated test module skips two gateway integrations if the W1 module is absent; GitHub CI must execute both against real W1 source.

**Decision:** This is a falsifiable local reference for Issue #34, not completion of its production gates and not authorization to deploy externally.