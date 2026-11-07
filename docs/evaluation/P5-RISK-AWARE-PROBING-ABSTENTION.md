# P5 — Capped Probing and Risk-Aware Abstention Under Partner Shifts

**Status:** Research-only synthetic single-owner W3 fixture. Neither a production safety guarantee nor a policy for real-world finance, consent, access control, legal cooperation or self-evolving societies.  
**Motivation:** [P4 measured partner-shift report](P4-FIVE-SEED-RESULTS-REPORT.md) found that a previously useful shared policy can incur **negative reward** when an expected partner refuses to reciprocate. This is a *decision uncertainty and monitoring problem*, not evidence that ECF needs more frequencies.

## The narrow decision being tested

Ten resource donor agents (among **30 registered synthetic agents**) decide once per round whether to transfer **one** integer unit to their fixed neighbor. Their receiving counterpart is a **scripted test policy**, not an independently authenticated owner or a learned agent. Every attempted transfer and return goes through the existing same-owner **PopulationRouter → GuardedWorldGateway → W3 reducer**. A run has **20 rounds = 40 committed W3 ticks**, and each donor begins with eight finite units.

If W3 confirms a donation and a later W3 transfer back, the donor earns **+0.60** (defined as 0.85 benefit minus 0.25 cost). An accepted donation without a return costs **-0.25**. An abstention costs **0**. These are **constructed toy rewards**, not observed economic returns. The break-even probability for a response, if its probability were known, is:

```math
p_{mathrm{break-even}}=rac{0.25}{0.85}approx 0.2941.
```

The actual partner response probability is **never included in the donor's observation**; it exists only in the host's fixed synthetic scenario. A donor sees the history of its **own accepted donations and returns**. The policy does not receive the hypothetical outcome of an action that was not taken.

## Four predeclared policies

| Policy | Behavior | Scientific purpose |
|---|---|---|
| `hold` | Never donate | Risk-free abstention reference, 0 in this toy reward |
| `always_offer` | Donate whenever own W3 balance permits | Cooperation with no partner risk sensitivity |
| `all_history` | Donate when an optimistic Beta(1,1)-smoothed empirical response rate exceeds break-even | Simple online learning; may never recover once it ceases observing outcomes |
| `risk_window` | Use a three-observation sliding window and a Wilson-style lower score; make bounded *probe transfers* early and every fifth round while confidence is insufficient | Explicitly explore a changing partner with **observed** evidence, not an oracle |

The Wilson-style lower bound uses a **fixed z=1.0** selected as a demonstrative conservative score, not a statistically calibrated one-sided confidence guarantee. It is **not** a warranty against resource loss, and a malicious partner can adapt strategically to the probing schedule. The risk-aware policy is **not** the same as an action-approval or capability policy. When funds reach zero, W3 rules and donor checks prohibit more transfers.

**Why probes are needed:** after abstaining, the donor cannot observe whether an unmade donation would have been returned. A strictly greedy learner can stop forever. P5 tests whether small, explicit attempts help regain information after conditions improve, while measuring the loss those attempts cause against an adversarial refusal.

## Five synthetic partner schedules

- **cooperative:** always returns a received transfer;
- **hostile:** never returns;
- **collapse:** cooperates during rounds 0–9, refuses during rounds 10–19;
- **recovery:** refuses during rounds 0–9, cooperates during rounds 10–19;
- **mixed:** returns with scripted 50% probability.

Each scripted response is computed from an exogenous hash of **(world seed, round, recipient ID)**, independently of which donor policy is being evaluated. All four policies start from the same **bit-identical W3 world fingerprint** for the same seed and partner schedule. The donor policy does **not** see the regime, hidden switch point, scheduled response probability, or unchosen outcomes.

A **five-seed** experiment, with four policies and five partner regimes, generates **100 independent case summaries**. Within a case, all 10 donors and their scripted receivers operate across 20 rounds. This is *not* 30 independently learning agents: there are 10 active donor policies, 10 scripted counterpart actors and 10 registered passive context agents.

## Actual measured five-seed checkpoint

The [CI-backed five-seed results report](P5-FIVE-SEED-RESULTS-REPORT.md) and [complete 100-case raw JSON](P5-FIVE-SEED-RESULTS.json) preserve every positive and negative outcome. On source commit `bfaf81a6dde1fbd4cf55aa5e4ec8ea6d892c5288`, GitHub Actions ran **425 tests with zero unexpected failures** (one skipped, two expected failures). Risk Window improves the *collapse* and *recovery* controlled cases relative to always-offer, but it is worse than all-history estimation under stable hostility, and less rewarding than always-offer under a mixed partner. **It is not a universally safe or optimal default.**

## Evaluation and nonclaims

The test reports **actual W3-confirmed accepted transfers**, returned transfers, unreciprocated resource exposure, explicit probing attempts, total donor reward and **per-phase** reward (first vs second 10 rounds). It also reports the **worst phase** rather than concealing losses under a positive episode average, exact replay and resource conservation, host W3 router p50/p95 call time, process wall/CPU and process peak RSS (OS-dependent units).

An observation ledger in the donor policy is a *local synthetic outcome history*, not W1 private autobiographical memory or an externally verified reputation system. The W3 journal records only **SIMULATED** events. The risk policy itself has **no authority** to create signed grants, override a host action approval or interact with a different owner.

**What P5 cannot prove:** statistical calibration, Bayes-optimal strategy, incentive-compatible contracts, resistance to an intelligent adversarial partner, safe exploration of sensitive assets, true social trust, convergence of multi-agent learning, persistent organizations or federated interoperability. The partner uses a fixed test script; no strategically optimizing counterpart is included. A fixed, predictable probe interval is especially vulnerable if exposed to strategic opponents.

## Reproduction

```sh
python -m unittest discover -s tests -p 'test_p5_risk_aware.py' -v
python -m unittest discover -s tests -v
python scripts/check_repository.py
python benchmarks/p5_risk_aware.py --seeds 5 --seed-start 9101 --out p5-results.json
```

The full W5 test emits JSON case lines to GitHub Actions for later extraction, without requiring a numerical winner. Actual figures and conclusions must be tied to exact source SHA, actual Python environment, five seed IDs and raw case data. Do not declare a passed safety gate from these scripted tests.

**Admission / rollback:** independent W0/W3/W4/W5 review before any production or shared-contract decision. Keep [Issue #65](https://github.com/CocAgent/OpenWorld/issues/65), [Issue #51](https://github.com/CocAgent/OpenWorld/issues/51) and independent [Gate #11](https://github.com/CocAgent/OpenWorld/issues/11) open. Remove the standalone P5 benchmark/tests/note to roll back; no live security schema, state, migration or deployment changes.
