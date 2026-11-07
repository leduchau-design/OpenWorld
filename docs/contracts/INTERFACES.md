# Interface boundaries — W0 contract proposal

| Producer | Consumer | Payload | Rules |
|---|---|---|---|
| World runtime | Memory compiler | Versioned event envelope | Validate identity, policy and provenance |
| Memory compiler | Exact ledger | Protected bytes, ordered stream metadata | Atomic commit with state |
| Memory compiler | Predictive state store | State deltas, estimator version | Never claim exact historical recall |
| Memory compiler | Generative trace store | Algorithm ID, PRNG metadata, checkpoint, inputs | Replay permitted only if complete |
| Capability gateway | Agent execution | Scoped grant and owner identity | Deny if grant missing or revoked |
| Recall | Human/tool client | Value + source + provenance + limitations | Never promote model output to observation |

This file documents **proposed interoperability**, not current API implementation. JSON Schema validation requires an explicit library in clients; the core bootstrap stays dependency-free.

External model access, data collection, and network permission are **out of scope** for the initial research runtime.
