# P6 Ten-Seed W3 Exposure Cap and Probe Challenge — Measured Results

**Source commit:** `dacbb0d426ea298b8d9df1c13b843ec8d3b6f512`; [Python 3.11 GitHub Actions job 123294839067](https://github.com/CocAgent/OpenWorld/actions/runs/40827828742/job/123294839067) **SUCCESS**: **440 tests run, zero unexpected failures** (one skipped, two expected failures), syntax/layout PASS.  
**All raw cases:** [P6-TEN-SEED-840-CASES.json](P6-TEN-SEED-840-CASES.json), including unrounded per-seed reward and worst-exposure fields. This is measured synthetic W3 evidence, **not production security/safety validation**.

## Actual environment and controls

- **10 seeds 10101–10110 × 7 policies × 6 scripted partner regimes × 2 feedback channels = 840 cases**.
- Each case: **30 registered agents; only 10 active donor policies**; 20 donor/recipient rounds and 40 committed W3 ticks, one trusted synthetic owner. Every attempted transfer uses the existing guarded PopulationRouter and W3 world, with exact replay and resource conservation checked.
- Same seeded initial W3 fingerprint for all methods/regimes/feedback modes within each seed. The donor sees only its **delivered** own accepted transfer and return outcome; no response is fabricated for an unmade donation.
- The **hard risk cap** is per-donor: *known unrepaid accepted transfers + accepted transfers with unresolved notification* must not exceed **4 single-unit exposures**. A W3 return observed by the policy releases that reservation; an unreported return does not. This cap is a trusted toy-host pre-action guard, **not a W4 capability or universal monetary-loss limit**.
- The **uncapped_offer** comparator deliberately omits this additional guard; it still obeys W3 finite balances and signed same-owner grants. Its observed peak exposure reaches **13**, compared with **4 or less** for every capped method.
- Immediate feedback and delayed/censored **notification** are different from instant or delayed resource settlement: the W3 transfer always settles in the current W3 recipient tick. Censored notification preserves uncertainty; it does **not** delete actual W3 events.

## Reward per donor decision (mean of ten seeds)

Each accepted gift costs 0.25 artificial reward, a confirmed return adds 0.85; hold scores zero. The fixed-given partner scripts are not real independently authenticated users. Negative is worse than hold.

| Feedback | Partner | Hold | Capped offer | Uncapped offer | All-history | Fixed probe | Seeded probe | Change detector |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| immediate | cooperative | 0.0000 | 0.6000 | 0.6000 | 0.6000 | 0.6000 | 0.6000 | 0.6000 |
| immediate | hostile | 0.0000 | -0.0500 | -0.1000 | -0.0250 | -0.0500 | -0.0490 | -0.0490 |
| immediate | collapse | 0.0000 | 0.2500 | 0.2000 | 0.2500 | 0.2625 | 0.2579 | 0.2579 |
| immediate | recovery | 0.0000 | -0.0500 | -0.1000 | -0.0250 | 0.0225 | 0.0033 | 0.0033 |
| immediate | mixed | 0.0000 | 0.0541 | 0.1133 | 0.0473 | 0.0524 | 0.0522 | 0.0522 |
| immediate | probe_gamer | 0.0000 | 0.0400 | 0.0200 | 0.0400 | 0.1000 | 0.0235 | 0.0235 |
| delayed_censored | cooperative | 0.0000 | 0.5295 | 0.6000 | 0.5295 | 0.5295 | 0.5295 | 0.5295 |
| delayed_censored | hostile | 0.0000 | -0.0500 | -0.1000 | -0.0349 | -0.0500 | -0.0495 | -0.0495 |
| delayed_censored | collapse | 0.0000 | 0.2638 | 0.2000 | 0.2638 | 0.2649 | 0.2650 | 0.2650 |
| delayed_censored | recovery | 0.0000 | -0.0500 | -0.1000 | -0.0349 | -0.0223 | -0.0197 | -0.0197 |
| delayed_censored | mixed | 0.0000 | 0.0498 | 0.1133 | 0.0425 | 0.0483 | 0.0459 | 0.0459 |
| delayed_censored | probe_gamer | 0.0000 | 0.0373 | 0.0200 | 0.0373 | 0.0833 | 0.0285 | 0.0285 |

## What these measurements establish (and do not)

1. **Finite exposure control works in the tested fixture.** Every non-uncapped policy recorded `max_unreturned_or_pending <= 4` over all 840-case results. Under immediate **hostile** partners, capped always-offer averages **-0.0500** against **-0.1000** uncapped. That is smaller synthetic loss, not zero risk.
2. **Probes cannot guarantee safety under hostility.** Immediate hostile reward is **-0.0500** for fixed probes and **-0.0490** for seeded probes, both worse than all-history **-0.0250** or fixed hold **0**. Under delayed/censored hostility, seeded probes score approximately **-0.0495**, still negative. Real W3 returns may remain unknown to the donor even when they occurred.
3. **Change detection did not demonstrate incremental value.** The current `change_point` and `random_probe` variants recorded identical mean reward to four decimals in all 12 regime/feedback combinations. This heuristic must **not** be promoted as a validated change-point detector.
4. **Controlled collapse and recovery:** immediate collapse yields **0.2625** for fixed probes and **0.2579** for seeded probes. Immediate recovery yields **0.0225** fixed and **0.0033** seeded, while all-history scores **-0.0250**. But with **delayed/censored** feedback, recovery scores become **-0.0223** fixed and **-0.0197** seeded; the claimed recovery benefit largely disappears.
5. **Schedule gaming is not defeated by randomization alone.** Under the constructed `probe_gamer` recipient (responds on publicly known 0/1 and every fifth round), immediate fixed probing **0.1000** exceeds seeded probing **0.0235**; with censored feedback it is **0.0833** vs **0.0285**. This is a specifically chosen **counterexample to any blanket claim that randomized probes outperform fixed probes**. It does not prove strategic resistance or general gaming incentives.
6. **Throughput is not established.** The benchmark ran on Python 3.11.17 / Linux-7.0.0-1017-azure-x86_64-with-glibc2.43 (4 CPU reported), with **7.29 seconds** for the bounded experiment and process peak **31876 KiB on Linux; bytes on macOS**. P95 router timing is recorded per case, but this is not a production latency, end-to-end agent cost or scaling guarantee.

## Required next gate

**Do not select any P6 policy as a default.** A future study would need (a) adaptive strategic partners who react to observed donor decisions, rather than one fixed calendar; (b) independently randomized unseen seeds; (c) calibrated change-detection false positives and missed recoveries; (d) actual delayed W3 settlement/reconciliation, which is *not* simulated by merely withholding notifications; (e) stateful crash/recovery and atomic budget enforcement against multiple concurrent donors or processes; and (f) independent W0/W3/W4/W5 review.

Keep [Issue #68](https://github.com/CocAgent/OpenWorld/issues/68), [Issue #65](https://github.com/CocAgent/OpenWorld/issues/65), [Issue #51](https://github.com/CocAgent/OpenWorld/issues/51) and independent [Gate #11](https://github.com/CocAgent/OpenWorld/issues/11) OPEN. CI verifies a synthetic reference, not authenticated multi-owner consent, verified external events or safety of economic transactions.

**Provenance:** All 840 unrounded cases were parsed from CI console output of the exact source SHA above. This documentation-only evidence commit is distinct and requires its own CI validation before merge.
