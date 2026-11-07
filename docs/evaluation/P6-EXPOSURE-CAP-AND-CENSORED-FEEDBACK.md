# P6 — Exposure Cap and Censored Feedback in a Local W3 Population

**Research status:** synthetic, trusted-host, same-owner W3 fixture. **Not** a financial risk engine, reliable reputation score, a production safety control, proof of social trust, independent cross-owner consent, or general multi-agent RL.  
**Tracking:** [Issue #68](https://github.com/CocAgent/OpenWorld/issues/68), [P5 raw five-seed evidence](P5-FIVE-SEED-RESULTS-REPORT.md), [W3 local population links](../world/W3-POPULATION-LINKS-P0.md).

## Objective and invariant

P5 showed a useful but imperfect trade-off: periodic probes helped recognize partner recovery but caused real synthetic loss under stable refusal. P6 adds a **per-donor hard budget of 4 exposure units**. Before any W3 donation is issued, the trusted reference checks:

```text
known_unreturned_donations + unresolved_accepted_donations + 1 <= 4
```

The reference never credits unobserved counterfactuals or a return merely *expected* from a probability score. A confirmed W3 donation reserves one unit. An outcome notification that is successfully delivered then releases the reservation; an observed non-return also increments the permanent loss count. An **unknown, censored or not-yet-delivered** response remains reserved until evidence is explicitly available. Even when a real W3 return occurred, a dropped *notification to the toy donor policy* cannot free this risk allowance. This is a *cautious bound on possible unreturned unit transfers*, **not a mathematical bound on all economic loss, reputation or external harms**.

The sole `uncapped_offer` policy is included as a deliberately unsafe **negative reference**. Every other candidate, including fixed hold and fixed cooperative strategies, is subject to the same four-unit ceiling.

## Comparators

- `hold`: never transfer; synthetic reward of zero.
- `always_offer`: transfer whenever permitted by W3 balances and four-unit exposure bound.
- `uncapped_offer`: ignore the additional research exposure cap; still constrained by finite W3 balance and the existing authorization gateway.
- `all_history`: optimistic response-rate estimate from **actually delivered** prior outcomes.
- `fixed_probe`: public every-fifth-round probe after insufficient evidence, plus the initial sampling steps.
- `random_probe`: deterministic seeded probe events with approximately one-fifth per-round selection; a reproducibility tool, **not cryptographically hidden randomness**.
- `change_point`: same seeded probes plus a small short-term failure detector. The detector is a heuristic, not statistically calibrated.

All donor policies share the same one-unit W3 action opportunity. We do not assume that adding a change detector increases reward or reduces risk.

## Evidence and partner interventions

The experiment evaluates **10 unseen test seed families** × **7 policies** × **6 partner schedules** × **2 feedback modes**, totaling **840 case records**. Each case has 30 registered synthetic agents, **10 donor decision agents**, 10 scripted recipient agents, 10 passive agents, 20 decisions per donor and **40 W3 committed ticks**. All actions pass the same `PopulationRouter` and `GuardedWorldGateway` as P5. Each case verifies exact W3 event replay, conservation of integer resources and `SIMULATED` provenance.

Partner schedules: always cooperate, always refuse, cooperate-then-collapse, refuse-then-recover, seeded mixed probability, and `probe_gamer`. The last script returns on rounds 0–1 and public multiples of five, trying to make a published fixed probing interval look safe. It is **not** a learning adversary and does not see agent model weights or secret credentials.

The `immediate` mode delivers W3 outcome notifications in the same recipient phase. The `delayed_censored` mode delays the **policy notification** by 1–2 subsequent donor rounds, with deterministic notification losses. **The underlying W3 transfer happens immediately**; the delay simulates partial information, not a slow bank settlement, an asynchronous cross-world transaction or proof of delivery. The policy never sees a hidden partner type, a future outcome or a response to an unmade donation.

## Pinned measured ten-seed checkpoint

[Actual Python 3.11 CI evidence report](P6-TEN-SEED-RESULTS-REPORT.md) and [complete unrounded JSON](P6-TEN-SEED-840-CASES.json) were recorded from exact source commit `dacbb0d426ea298b8d9df1c13b843ec8d3b6f512`: **440 tests passed with no unexpected failures**, and 840 experiment cases covering ten seeds. Under immediate hostile partners, capped always-offer has reward **-0.0500**, compared with uncapped **-0.1000** and risk-free hold **0**. Every capped case has measured peak exposure **at most 4**, versus **up to 13** in the uncapped baseline across delayed/censored conditions. The seeded/randomized and change-point heuristics do **not** demonstrate universal partner-shift superiority. This is bounded simulation evidence, not a rollout decision.

## Measured fields and acceptance

Record per-case synthetic donor reward, first/second-half reward, worst-half reward, accepted donations and returns, **per-donor peak exposure**, known non-returns, unresolved/censored observations, probe attempts, cap blocks, observed feedback count and W3 router p95. Verify all seven methods receive bit-identical *starting worlds* under the same seed. Store the **complete actual CI output and all unfavorable outcomes**, with exact commit SHA and environment.

For the bounded research interpretation, check:
1. Every capped policy has `peak_exposure <= 4`, independently of donor balance or partner deception. The uncapped comparator must be clearly distinguished.
2. An unknown outcome **cannot** be interpreted as a success. No learning feedback appears from abstentions.
3. A known public probe schedule can be gamed in the constructed `probe_gamer` condition; report any non-improvement of seeded probing honestly.
4. Preserve both short-run reward and the cost of probes under hostile partners; holding is an essential zero-risk baseline under this artificial reward.
5. Do not infer a convergence theorem, calibrated confidence level, independent agent cooperation or production-grade safety from a green unit test.

## Reproduction

```bash
python -m unittest discover -s tests -p 'test_p6_risk_budget.py' -v
python -m unittest discover -s tests -v
python scripts/check_repository.py
python benchmarks/p6_risk_budget.py --seeds 10 --seed-start 10101 --out p6-cases.json
```

**Owner review required:** W0/W3/W4/W5 before merge. Existing external identity, rights and world-authentication mechanisms remain unchanged. This is **research-only**; [Issue #68](https://github.com/CocAgent/OpenWorld/issues/68), [Issue #51](https://github.com/CocAgent/OpenWorld/issues/51) and [Gate #11](https://github.com/CocAgent/OpenWorld/issues/11) remain open until independent fault, causality and security verification are accepted.

**Rollback:** delete optional `risk_budget.py`, P6 benchmark, tests and note; no migration, runtime contract, user data, production dependency or network endpoint.
