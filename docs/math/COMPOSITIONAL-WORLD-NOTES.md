# Compositional World Mathematics — Research Notes

**Status:** mathematical mapping and finite executable examples; not a formal proof of the complete OpenWorld architecture.

## Pure composition

Let a category have port types as objects and pure total functions as arrows. For `f: X -> Y`, `g: Y -> Z`, composition is `g ∘ f: X -> Z`; `id_X` is the identity. Function composition is associative. The experimental `Arrow` class performs strict runtime type checks. Passing tests for particular arrows does NOT prove all arbitrary Python functions are pure, terminating or effect-free.

A future world composer may use operads/wiring diagrams for multi-input graphs, but cycles require explicit clock/feedback semantics and cannot be inferred from sequential composition.

## Stochastic semantics

For finite state spaces, `K(s'|s,a,e)` is a controlled transition kernel and `Omega(o|s)` is an observation kernel. A valid stochastic kernel has nonnegative probabilities and each conditional row sums to 1. For sequential kernels, `(K2 ∘ K1)(z|x) = Σ_y K1(y|x) K2(z|y)`.

POSG interaction may be modeled as observation -> joint policy -> world transition. The product of per-agent policies only models a conditionally independent choice; correlated policies and shared randomness need a joint policy. An agent with memory requires a sufficiently augmented state. One-time marginal characteristic functions do not identify stochastic dependence.

## Stateful effects and evidence

The transfer example ensures `sum(balances_after) = sum(balances_before)` because no production/consumption exists. More general resource models must account separately for production and sinks. State-changing commands are typically noncommutative, so deterministic arbitration is not a categorical theorem.

`SIMULATED` events are **not** verified history. Hash chaining can detect inconsistent recomputation but does not establish authenticity, persistence, or a secure trust anchor. Consult RFC-006 before integrating with exact evidence/memory.

## Falsifiable evaluation

Before adopting additional mathematical machinery, compare it with a simpler typed pipeline under identical tasks: integration errors, conformance-test coverage, development complexity, resource cost and gameplay utility. Use negative cases for invalid ports, conflicting writes, unauthorized access, and incomplete replay inputs. Mathematical notation must map to executable semantics and measured value.

## References

- Ghani et al., *Compositional Game Theory* (LICS 2018).
- Tobias Fritz, *A synthetic approach to Markov kernels, conditional independence and theorems on sufficient statistics*.
- AlgebraicJulia — https://www.algebraicjulia.org/
- PettingZoo Parallel API — https://pettingzoo.farama.org/main/api/parallel/
