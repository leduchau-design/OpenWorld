# P5 Five-Seed Capped-Probing Evidence — Mixed, Not a Universal Winner

**Measured source:** `bfaf81a6dde1fbd4cf55aa5e4ec8ea6d892c5288` on [GitHub Actions Python 3.11 run](https://github.com/CocAgent/OpenWorld/actions/runs/40822991087/job/123279474111) **SUCCESS**, **425 tests run with zero unexpected failures** (1 skipped, 2 expected failures), syntax and layout checks PASS.  
**Raw JSON:** [P5-FIVE-SEED-RESULTS.json](P5-FIVE-SEED-RESULTS.json) — **all 100 policy/partner/seed cases**, grouped measurements, W3 fingerprints and timings. This report does not supply synthetic or guessed numerical outcomes.

## What was actually executed

- **5 seed families 9101–9105**, 4 decision rules × 5 partner regimes = **100 W3 cases**, each lasting 20 rounds / 40 committed W3 ticks.
- **30 registered synthetic agents**, only 10 donor policies make decisions, 10 recipients follow a **host-scripted partner response**, 10 other agents are passive context members.
- Every accepted transfer and return is a genuine **SIMULATED W3 event** checked through the existing same-owner PopulationRouter and GuardedWorldGateway, with exact replay and resource conservation checked per case.
- All four donor policies face the same bit-identical initial world for a given seed, and partner response potential outcomes depend only on seed, round and recipient ID, not policy; **unchosen outcomes are never shown to the donor**.
- A returned donation earns the donor +0.60, a donation without return costs -0.25, and abstention produces 0 in the artificial reward function. Results are **reward per donor decision**, averaged over 5 seeds.

## Actual measured average reward / decision

| Partner regime | Hold | Always offer | All-history estimator | Risk Window |
|---|---:|---:|---:|---:|
| cooperative | 0.0000 | 0.6000 | 0.6000 | 0.6000 |
| hostile | 0.0000 | -0.1000 | -0.0250 | -0.0625 |
| collapse | 0.0000 | 0.2000 | 0.2000 | 0.2625 |
| recovery | 0.0000 | -0.1000 | -0.0250 | 0.1425 |
| mixed | 0.0000 | 0.1259 | 0.1013 | 0.0615 |

Fixed hold is 0 in **every** regime and therefore protects the simulated finite resource balance, but forfeits benefits of cooperation.

## What P5 supports and falsifies

1. **Abrupt collapse, partial improvement:** risk_window obtains **0.2625**, against **0.2000** for always-offer and all-history. Its second-half reward is **-0.0750** compared with **-0.2000** for always-offer. The rolling observation window stops further exposure after failures, but it still has losses from periodic probes.
2. **Unexpected recovery, meaningful difference:** risk_window obtains **0.1425**, whereas always-offer is **-0.1000** (depletes its finite resources before the recovery) and all-history is **-0.0250** (stops sampling and cannot discover recovery). Risk_window's second-half reward reaches **+0.3600**. This is the intended positive control for periodic probes.
3. **Stable hostility, failure of the risk-window selection:** risk_window scores **-0.0625**, which is better than always-offer **-0.1000**, but WORSE than all-history **-0.0250** and fixed hold **0.0000**. Its periodic probes cost real simulated resources. The measured risk_window makes on average **50 probing donations across 10 donors per hostile 20-round case**, so it is **not** risk-free or 10 total probes per population.
4. **Stable cooperation:** both learned donor rules and always-offer reach **0.6000**, while fixed hold earns 0. This outcome is built into the simulated reward; it is not evidence of altruism.
5. **Uncertain mixed partner:** always-offer has **0.1259**, all-history **0.1013**, and risk_window only **0.0615**. The risk-window rule can be overcautious when the underlying cooperation probability is profitable but noisy. It is not a calibrated posterior, a dominance theorem, a guaranteed improvement or a production-ready safety threshold.

## Experimental caveats

- The scripts use **fixed, known schedules** for scripted partners (cooperative/hostile, switch after round 10, and seeded 50% mixing). The hidden schedule is not shown to the donor, but it is a constructed problem. No truly adversarial strategic recipient changes behavior in response to probe timing.
- The window length 3, probe interval 5 and Wilson-style score with z=1 were **chosen as heuristic values**, not calibrated for a safety guarantee, and were not selected using held-out independent challenge tasks. Do not claim statistical coverage.
- Rewards are designed and asymmetric; returned resources produce a positive artificial net benefit. **Risk and expected utility need separate definitions for any consequential domain.**
- A donor sees only its own successfully accepted donation/return history, not independent evidence of another agent's trustworthiness, real identity, signed intention or authorization. Probe timings could be gamed by an adaptive counterpart.
- Registered population size, active donors and independent learned policies are different quantities. P5 has **10 active donor decision policies and scripted recipients**, not 30 learning agents.
- GitHub Actions reports **0.94 s** of standalone benchmark wall time and **31996 KiB Linux peak process RSS** on a 4-CPU Python 3.11.17 host. This is not per-agent latency, production throughput or an AHappy/Vua Cóc deployment estimate.

## Decision and next gate

**Do not promote risk_window as a universal default.** Keep it as a **bounded research candidate** that demonstrates a real exploration/exposure trade-off under abrupt change. Before P6, predeclare an explicit maximum cumulative downside, budgeted randomized probes (rather than predictable times), adaptive change detection, delayed/dropped feedback and a strategic partner capable of gaming probe schedules. Test against fixed hold and all-history on **fresh independent seeds**, with worst-case losses and role-specific harm, not only mean reward. Stop if there is no measurable benefit net of exposed resources.

W0/W3/W4/W5 review is still mandatory. [Issue #65](https://github.com/CocAgent/OpenWorld/issues/65), [Issue #51](https://github.com/CocAgent/OpenWorld/issues/51) and independent [Gate #11](https://github.com/CocAgent/OpenWorld/issues/11) remain OPEN. No cross-owner interaction, production policy, generated claims of verified events, permissions, contracts or new external APIs are included.

**Evidence provenance:** The exact CI job emitted metadata plus one JSON object per case. These values are compiled from all 100 actual case records; this evidence commit has a **new SHA requiring its own CI check**.
