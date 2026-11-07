# Inter-World Discovery P0 — Public Metadata, No Authority Transfer

**Status:** DESIGN ONLY. No network connection, schema ratification, distributed trust, bilateral consent, cross-world transaction or remote tool call implemented.  
**Date:** 2026-10-29. **Workstreams:** W0/W3/W4/W5. **Tracking:** [Issue #59](https://github.com/CocAgent/OpenWorld/issues/59), [two-party consent Issue #35](https://github.com/CocAgent/OpenWorld/issues/35), [independent Gate #11](https://github.com/CocAgent/OpenWorld/issues/11).

## 1. Smallest useful goal

Two independently operated worlds should eventually be able to determine whether they **might** understand the other's *public and explicitly approved metadata*, without granting access to private agents, permissions, resources or state. The first deliverable is a **read-only discovery and compatibility specification**; implementing distributed resource transfers now would create security promises the existing local world cannot satisfy.

The existing [W3 Population Links P0](../world/W3-POPULATION-LINKS-P0.md) demonstrates **three groups under one synthetic owner**. That is not two-world federation and cannot be treated as cross-owner consent.

## 2. Candidate public world descriptor (NOT a ratified schema)

For a future bounded offline compatibility preflight, a public descriptor MAY contain only:

| Field | Purpose and restrictions |
|---|---|
| format_version | Explicit proposed discovery format version; unknown versions reject |
| world_id | Opaque, bounded ID assigned by an operator; self-declared value is not verified identity |
| claimed_owner_id | Informational claim only, marked UNVERIFIED until a separate trust mechanism authenticates it |
| world_engine | OpenWorld engine implementation and schema compatibility label; no executable URL |
| engine_build_sha256 | Content fingerprint for a reviewed engine artifact; a digest alone does not verify the artifact or its publisher |
| allowed_public_artifact_types | Small allow-list for public read-only metadata; never private state, tokens or raw event logs |
| issued_at / expires_at | Time-bounded descriptor freshness; clock and replay semantics need W0/W4 review |
| declared_max_bytes | Host-enforced bound on a future descriptor/public artifact; not permission to download arbitrary URLs |
| descriptor_digest | Canonical content checksum for accidental modification detection; NOT a signature or owner proof |

A descriptor is **not** a remote W3 Action, a PopulationLink, a grant, an organization charter, a World Genome that modifies kernel invariants, or a bearer token. No secret, IP address, user data, model prompt, private genome memory or tool instruction should be copied into a public descriptor.

Until W0 ratifies canonical encoding, field names and versions, **do not** publish a JSON Schema or advertise network interoperability. This document describes requirements for a future schema, not an already accepted protocol.

## 3. Proposed research stages

**Stage D0 — offline static compatibility comparison.** On synthetic user-authored fixtures only, a locally controlled evaluator reads two *already available* descriptors (no URL fetching). It enforces length/type bounds, unknown-field denial, canonical serialization, compatible format/engine versions, prohibited artifact types, expiry and explicit provenance. Outcome is limited to COMPATIBLE_FOR_REVIEW or REJECTED. Never treat compatibility as consent.

**Stage D1 — authenticated public artifact.** Only after W0 and W4 review, introduce a separately authenticated publisher and reviewer-approved **public non-executable artifact**. Verify its declared provenance independently; a checksum of untrusted content cannot establish truthful origin. Make every access read-only and auditable.

**Stage D2 — negotiated inter-world action (NOT APPROVED).** This requires [Issue #35](https://github.com/CocAgent/OpenWorld/issues/35): two independently authenticated, owner-scoped, revocable consents bound to the same canonical intent digest, current ownership, payload, purpose, quantity, expiry and expected world version. The action must atomically consume authorization and persist outcome in an authoritative journal, with a defined failure/retry model.

**Stage D3 — federation, if justified.** Resource/asset reconciliation between autonomous hosts cannot rely on two independent SQLite commits being atomic. Before proposing a distributed transaction protocol, choose a concrete product use case and specify escrow/commit/abort semantics, idempotency and crash recovery. No consensus, eventual consistency, smart-contract platform or paid infrastructure is justified in P0.

## 4. Mandatory negative controls

- Forged claimed owner, duplicate world ID, unknown engine version, downgrade attempt, stale or replayed descriptors.
- Oversized/unexpected fields; executable/model/tool payloads disguised as metadata; attempts to embed filesystem paths, file URLs, private resource references or automatically fetched network endpoints.
- Hash with no external trust anchor; invalid issuer signature; missing receiver approval; revoked/expired grants; different intent digest for each party.
- Same-host/same-owner grants presented as independent bilateral authorization.
- Remote claim of W3 resources, agent memory, permission, world-genome authority or exact event authenticity without a trusted source.
- Race between revocation check and action commit; crash after one world records a transfer but before the second accepts; replay and duplicate consumption.

## 5. Mathematics: keep identity, probability and trust separate

An optional group distribution sketch (mean, histogram, ECF) may summarize **approved non-sensitive public features** within one world. It is not an identity credential, causal explanation or evidence of consent. Similarity of population embeddings does not imply interoperability or lawful transfer.

The actual cross-world authorization problem is a **state machine with independently validated principals and an atomic outcome**, not a missing Fourier, category-theoretic, quantum or number-theoretic formula. Typed composition can guide interfaces, but does not prove a secure distributed transaction.

## 6. Review decision and rollback

- **Ready today:** stage D0 specification only. The design introduces no network activity, no code execution, no change to W3 authorization and no new public API.
- **Not authorized:** cross-owner signals, transfers, organization membership changes, live user data, remote code execution, automatic model import or federated societies.
- **Prerequisites:** W0 schema decision, W4 source/receiver authentication and revocation, W3 coherent world-event transaction, W5 independent fault and security testing.
- **Evidence discipline:** tests on future synthetic offline descriptors are necessary but not sufficient; no world-interoperability claim until two independent reference implementations are reviewed.

Rollback: revert this document. No database, credentials, deployment, exposed endpoint or production actor is affected.
