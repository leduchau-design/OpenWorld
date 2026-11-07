# Issue #35 — Two-Party Consent Protocol (design proposal)

**Status:** PROPOSED; no cross-owner execution enabled. Depends on review of SEC-002 (#34) and Gate #11.

## Protocol goals

A sender's authenticated identity and authorization over **their own** resources cannot stand in for the receiver's permission. For a cross-owner `transfer` or `signal`, the service must obtain two independently authenticated and revocable consents bound to the same **operation digest**, with no ambiguity about sender, recipient, ownership, action, payload class, maximum amount, expiry, and intended purpose.

### Suggested stages

1. `PREPARE`: create an immutable intent `{version, intent_id, source_owner, source_agent, target_owner, target_agent, action, amount_or_content_class, purpose, nonce, not_before, expires_at, expected_world_tick}`. This is only a proposed action, not an executed transaction.
2. `SOURCE_AUTHORIZE`: issue a source-owner grant bound to the canonical intent digest and source agent. The grant cannot authorize recipient resources.
3. `RECEIVER_ACCEPT`: receiver independently authenticates and issues a consent grant bound to **exactly** the same digest, receiver agent, purpose, expiry and execution budget. Silence, read receipt or mere graph adjacency are not consent.
4. `EXECUTE`: the trusted coordinator checks both grants, current ownership and resource balances, rejects revoked/expired/overused or changed requests, and performs exactly one **atomically committed** state transition with durable grant consumption and event journal. Cross-database transactions must be designed; SEC-002's grant consumption alone is insufficient.
5. `AUDIT`: persist issuer, receiver, version, grant references, policy version, replay ID, decision outcome, and simulated vs independently verified provenance. Never include raw secrets in the audit record.

## Required negative tests

- Missing receiver consent; same sender for both signatures; wrong receiver agent; changed amount or purpose; forged or mismatched intent digest.
- Revoked receiver consent before commit; expired authorization; duplicate nonce; replayed request across ticks; conflicting request IDs.
- Simultaneous transfer attempts with insufficient balance; crash between capability debit and world mutation; rollback and retry with an authoritative journal.
- Receiver changes owner during handshake; source/target owner impersonation; unauthorized neighbor signals; hub-shaped adversarial topology.

## Non-goals and explicit blockers

No real payment, wallet, external service, user data, or cross-owner W3 execution is allowed in this design phase. The current W3 deterministic `World` reducer does not persist authenticated authorization receipts and permits unguarded direct imports within the same process. Keep W3's cross-owner denial intact until an independently reviewed coordinator and atomic storage boundary are implemented.

**Proposed dependency order:** SEC-002 review → independent Gate #11 checks → bilateral consent state machine → W3 transaction and replay integration → W5 adversarial evaluation.