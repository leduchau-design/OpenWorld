# P4 Five-Seed Sample Efficiency & Partner Shift — Measured CI Evidence

**Status:** Bounded synthetic W3 experiment; **not** general MARL, stable cooperation, independent authorization or production rollout.  
**Source commit:** `e9906b230c48ff85240c1f8ae528caf82ca9881e`. [Actual GitHub Actions Python 3.11 run](https://github.com/CocAgent/OpenWorld/actions/runs/40818857953/job/123266311584) **SUCCESS: 406 repository tests completed with no unexpected failures**, Python syntax and repository layout passed. One test was skipped, two failures were expected (xfail).  
**Complete raw evidence:** [P4-FIVE-SEED-RESULTS.json](P4-FIVE-SEED-RESULTS.json). The JSON preserves all **120 model/seed/budget cases** and their **960 holdout partner/regime summaries**, including negative outcomes, exact input hashes and measured timings.

## Executed design, not extrapolated

- **Five independent seed families 8101–8105**. Holdout scenes come from seeds offset by 1,000,003; all eight models and three budgets receive exactly the **same initial W3 world fingerprints** per seed and scenario, as asserted in CI.
- **30 registered agents, of which 20 make decisions** (10 donors and 10 recipients); four donor/recipient rounds, **8 committed W3 ticks per episode**. All exchanges remain within one trusted synthetic owner and pass guarded W3 routing; per-episode world replay and conservation verified.
- Three **nested training budgets**, 8, 32 and 128 episodes, corresponding to **640 / 2,560 / 10,240 chosen-action updates per learned configuration per seed**. Fixed-rule controls have no weight updates. Policy state is frozen and content-hash checked during holdout.
- Each seed/method/budget has **3 holdout episodes** for each of eight conditions: original/shuffled starting resource allocation × native, fixed-hold, fixed-reciprocating or seeded mixed recipient policy. Shuffled resources preserve total resources **within each group**; partner changes occur only at evaluation.
- Shared models use **two policy tables** (donors/recipients) under one host; independent models use **20 policy tables**, still with equal action/update opportunities. No identity, memory or grant is shared by the population sketch.
- Child benchmark measured **37.18 s** wall time on Python 3.11.17 / Linux-7.0.0-1017-azure-x86_64-with-glibc2.43, reported **30692 KiB maximum process RSS** on Linux with 4 reported CPUs. This is **whole-process** peak, not per-method memory, server throughput or a 1,000-agent stress test.

## Mean measured joint reward by training budget

Values are five-seed means of each condition's **joint per-decision reward**, not probabilities or accuracy. "Normal" denotes the learned/fixed recipient behavior; "refuses" means a fixed hold recipient. Models were evaluated under the same starting W3 inputs but produce different future states.

| Training | Policy | Normal partner / original | Partner refuses / original | Normal partner / shuffled | Mean context keys |
|---:|---|---:|---:|---:|---:|
| 8 | Fixed hold | 0.0000 | 0.0000 | 0.0000 | 0.0 |
| 8 | Fixed cooperation | 0.5750 | -0.2250 | 0.5290 | 0.0 |
| 8 | Independent/full | 0.2239 | -0.0457 | 0.0726 | 78.8 |
| 8 | Independent/compact | 0.2871 | -0.1665 | 0.2645 | 57.0 |
| 8 | Role-shared/full | 0.5750 | -0.1613 | 0.2213 | 11.8 |
| 8 | Role-shared/compact | 0.5750 | -0.2250 | 0.5290 | 6.0 |
| 8 | Role-shared/histogram | 0.3642 | -0.0506 | 0.1332 | 38.2 |
| 8 | Role-shared/ECF | 0.3833 | -0.0525 | 0.1155 | 49.8 |
| 32 | Fixed hold | 0.0000 | 0.0000 | 0.0000 | 0.0 |
| 32 | Fixed cooperation | 0.5750 | -0.2250 | 0.5290 | 0.0 |
| 32 | Independent/full | 0.5271 | -0.1181 | 0.1771 | 95.2 |
| 32 | Independent/compact | 0.5635 | -0.2250 | 0.5175 | 60.0 |
| 32 | Role-shared/full | 0.5750 | -0.2062 | 0.2175 | 12.6 |
| 32 | Role-shared/compact | 0.5750 | -0.2250 | 0.5290 | 6.0 |
| 32 | Role-shared/histogram | 0.5654 | -0.0563 | 0.2213 | 72.2 |
| 32 | Role-shared/ECF | 0.5654 | -0.0563 | 0.1916 | 113.0 |
| 128 | Fixed hold | 0.0000 | 0.0000 | 0.0000 | 0.0 |
| 128 | Fixed cooperation | 0.5750 | -0.2250 | 0.5290 | 0.0 |
| 128 | Independent/full | 0.5750 | -0.1740 | 0.2136 | 106.0 |
| 128 | Independent/compact | 0.5750 | -0.2250 | 0.5290 | 60.0 |
| 128 | Role-shared/full | 0.5750 | -0.2062 | 0.2548 | 13.0 |
| 128 | Role-shared/compact | 0.5750 | -0.2250 | 0.5290 | 6.0 |
| 128 | Role-shared/histogram | 0.5750 | -0.0563 | 0.2271 | 114.2 |
| 128 | Role-shared/ECF | 0.5750 | -0.0563 | 0.2012 | 236.8 |

## What the results support

1. **Evidence for improved sample efficiency in this fixture.** At eight training episodes, both role-shared full and role-shared compact learners reach **0.5750** joint reward in the original/native condition — matching the fixed cooperative control. Independent/full reaches **0.2239**, independent/compact **0.2871**. Shared/compact uses about **6 distinct tabular context keys across two role tables**, versus about **78.8 across twenty independent/full tables**. Pooling reward and reducing state fragmentation are plausible mechanisms, but the experiment does **not** independently attribute which mechanism causes the benefit.
2. **More data improves some independent learners.** At 128 episodes, independent/full and independent/compact both reach **0.5750** in the original/native case, matching the fixed rule. Thus the very short training budget in P3 was at least a material obstacle for this constructed problem. It is not evidence of convergence in general nonstationary MARL.
3. **No robust all-partner winner.** A recipient that always refuses makes the fixed cooperative control score **-0.2250**. At eight episodes, role-shared/compact likewise scores **-0.2250** (not adapted), while shared/histogram scores **-0.0506** and role-shared/ECF **-0.0525**, both still negative. The fixed hold policy scores **0** under refusal and is preferable there. A method that scores well in the native condition can therefore fail under partner shift.
4. **Distribution-shift losses matter.** Role-shared/full drops from **0.5750** original/native to **0.2213** shuffled/native at eight episodes, while shared/compact remains **0.5290** on the shuffled case. The shuffle explicitly preserves group totals but changes individuals' resources; this is a controlled negative test for relying on training-specific balance patterns.
5. **Fourier is not a default.** ECF and histogram models have more context keys and perform worse than local compact representation on original/native and shuffled/native under several training budgets. Neither solves adversarial partner refusal. There is no evidence for adopting ECF, a learned mean-field encoder or agent-scale neural training as the default.

## Important limitations and decision

- These are short, deterministic, eight-tick synthetic worlds with engineered reciprocity rewards and no real third-party owners. Training and holdout use **the same world generator family**, apart from controlled partner/resource shifts. The five-seed average is not an independent statistical significance or confidence interval.
- "Partner override" is a **trusted host scripted intervention**, not another independently authenticated learner or real human participant. Shared policy objects are updated sequentially inside one Python process; not a concurrency-safe multi-owner learning service.
- The script logs W3 router-call p50/p95 and full-episode p95, but these are sensitive to runner/hardware load and **do not** represent end-to-end production inference latency. Maximum RSS is whole-process peak; no replicated worker or 10,000 agent capacity measured.
- Relative gains in native cooperation cannot justify unconditional deployment. The explicit worst-case reference **fixed hold = 0 reward** under partner refusal outperforms every transferring policy with negative rewards in that condition. Risk-aware safety requires separately defined utility and external evaluation.

**Recommendation:** Keep P4 as **experimental evidence**, not an automatic decision engine. P5 should test risk-sensitive *abstain/transfer* policies with informative partner observations and a longer-memory model, under independent partner holdouts and resource constraints, before adding more population statistics. Keep [Issue #65](https://github.com/CocAgent/OpenWorld/issues/65), [Issue #51](https://github.com/CocAgent/OpenWorld/issues/51), [Issue #59](https://github.com/CocAgent/OpenWorld/issues/59), and independent [Gate #11](https://github.com/CocAgent/OpenWorld/issues/11) OPEN.

**Provenance:** Every numeric cell in the table was computed from the exact 120 real CI case records. This evidence-writing commit is distinct from the measured source commit and requires its own validation. **No numerical result was invented or backfilled.**
