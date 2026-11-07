# W3 — Capability-Gated World Research Adapter

**Status:** Experimental, not a public protocol, production authentication service, or verified cross-owner network authorization.  
**Depends on:** SEC-001 scoped capability reference and W3 local fixture.

The optional `GuardedWorldGateway` wraps W3's in-memory `advance()` and `observe()` with strict owner/resource/action grant checks. Every submitted action is validated before the reducer runs. For now, **all cross-owner transfers and signals fail closed**, even when the actor has an owner grant. This conservative default is temporary until a future bilateral consent/contract protocol is specified and independently tested.

An externally authenticated principal must be supplied by the host, and HMAC keys must be managed securely outside the untrusted caller. The current gateway trusts its configured callback, so a hostile process capable of replacing the callback or directly importing `world_fixture.advance` **can bypass the demonstration boundary**. The W3 journal does not store token proof, grant provenance, revocation state or a durable access audit. Replay reproduces the declared simulated state, **not authentication decisions**. Weather updates are still supplied by a trusted host and are not independently sourced.

## Acceptance coverage

- Valid owner-scoped action preserves balances and exact world replay.
- A second action with an invalid grant aborts the entire batch before reducer invocation.
- Wrong principal, resource, owner and revoked grants reject access.
- Observations require a `read_world` grant bound to the exact agent and owner.
- Cross-owner communication and resource transfers are denied, pending a future protocol.
- The gateway does not add paid APIs, network access, real user data or new persistent data.

The 12 W3 gateway tests are additional to the 30 isolated SEC-001 security tests and five HyperMemory integration tests. Run the full integrated repository unit suite before accepting the stack.

## Future gates

Authenticate transport and subjects, persist revocation and decision audits, require explicit receiver consent for cross-owner interactions, bind grant lineage to RFC-006 provenance, and test adversarial concurrent execution and persistence/crash recovery. Do not turn this example into a public API without threat review and operator approval.
