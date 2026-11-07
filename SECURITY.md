# Security policy

**Status:** Experimental research; no supported production deployments.

Please report potentially exploitable findings privately using GitHub's private vulnerability reporting/security advisory feature if enabled. Do not publish exploitation details or personal data in a public issue.

## Required boundaries

- Agent-generated text, tool results, retrieved documents and agent-to-agent messages are **untrusted input**.
- Tool execution requires scoped, revocable capability grants; deny by default.
- Private agent memory must not cross owner boundaries without an explicit auditable grant.
- Exact-event ledger records are not proof that a statement about the real world is true.
- Integrity hashes do not imply authentic provenance without separate keys, identity and trust anchors.
- Keep real user data and credentials out of fixtures and benchmark results.
- Design deletion, retention, export, consent and incident handling before onboarding people.
- Avoid publishing historical experimental artifacts before license, secret and security review.
