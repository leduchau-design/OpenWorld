# EXPR-001 — Composable World Fixture

**Status:** Experimental local example; **not** RFC-007, a stable protocol, or a ratified core API.  
**Research home:** OpenWorld, independent of AHappy.  
**Related:** [RFC-007 mathematical foundations](../math/RFC-007-OPENWORLD-MATHEMATICAL-FOUNDATIONS.md), [W2 P0 gates](../math/MATHKERNEL-P0-IMPLEMENTATION-GATES.md), proposed [RFC-006 memory contracts](../rfcs/RFC-006-MEMORY-AND-AGENT-CONTRACTS.md), and [Issue #11](https://github.com/CocAgent/OpenWorld/issues/11).

## Source boundary

The active OpenWorld discussion motivates categorical composition, agent blueprint generation, an authoritative world state and replay. The separately supplied share URL https://chatgpt.com/share/6ae214d5-8860-83ec-b076-f7834ec8a002 could not be fetched. Its full transcript is **not** an imported source. No unseen decisions, identities, claims, archives or historical benchmarks were inferred from the link. Naming proposals such as OCP/OWP are not adopted standards; **OpenWorld** remains the project name.

## What is implemented

The standalone [Python example](../../examples/composable_world.py) uses only the standard library:

- **Typed pure arrows:** sequential composition, identity, associativity examples and port mismatch rejection. The laws assume pure total functions; arbitrary effectful Python functions are not proven lawful.
- **Blueprint genesis:** seeded, repeatable role/trait blueprints with lineage constraints; neither learned intelligence nor trusted authentication, ownership proof, policy weights or capability grants.
- **In-memory world:** per-command atomic transfer, a host-provided permission map, nonnegative resources, deterministic conflict order, stale/duplicate rejection and a simulated event hash chain.
- **Replay:** reconstruct outcomes from submitted commands, trusted grants and the same initial state/code. Hash consistency is not source authentication.

### Local verification

```bash
python -m unittest discover -s tests -p 'test_composable_world_experiment.py' -v
```

At authoring time, 11/11 **isolated** tests ran successfully with Python 3.13.5 on local CPU. This does not close the independently executed merged-main gate (#11). The full repository was not cloned/tested here because container network DNS access was unavailable.

## Precise non-goals

This is **not** a secure sandbox, persistent or distributed transaction engine, identity provider, formal categorical proof, real stochastic game, AI-training system, authenticated provenance mechanism, mod-federation network, or real-world vehicle/weapons controller. Rejected requests are not durably audited. Request-ID priority is a toy ordering rule and should be replaced after fairness analysis. Historical or external observations must never be presented as verified merely because simulation is deterministic.

## Next integration gates

1. W0 reviews identity, owner, provenance, action schema and version boundaries against RFC-006 before any public contract freeze.
2. W2 finishes finite stochastic kernels, filters and counterexamples independently of this pure-arrow fixture.
3. W3 tests world replay with persistence, complete exogenous inputs, quotas and adversarial conflict cases.
4. W4 designs deny-by-default capability admission and isolated agent/mod execution; optional MCP/A2A adapters remain outside the tick loop.
5. W5 repeats independent tests, adversarial controls and cost measurements. Game engagement or large-scale agent performance are **not** established by this example.

**Rollback:** Remove this document, the mathematical notes, example module, test file and README pointer. No production state migration is involved.
