# Gate #11 — independent reproduction handoff

**Status: OPEN.** This runbook does not itself appoint an independent reviewer,
certify historical evidence, or approve production safety. It packages
the existing [Issue #11](https://github.com/CocAgent/OpenWorld/issues/11)
commands and additional synthetic holdout/negative cases.

## Reproduction from clean merged main

Use a clean checkout on a *different contributor's* CPU-only machine.
Do not use real personal data, production databases, model API keys,
paid services or untrusted external event feeds.

```sh
git clone https://github.com/CocAgent/OpenWorld.git
cd OpenWorld
git fetch --prune origin main
git switch main
git merge --ff-only origin/main
git status --porcelain
git rev-parse HEAD
git rev-parse refs/remotes/origin/main
python scripts/gate11_reproduction_bundle.py --list-only
```

Copy the exact 40-character lowercase HEAD SHA and execute:

```sh
python scripts/gate11_reproduction_bundle.py --expected-sha <FULL_COMMIT_SHA> --out-dir ../openworld-gate11-evidence
```

The output directory must not already exist, must be outside the repository
and its parent must exist. The command refuses a dirty worktree,
a detached checkout, a local main or fetched origin/main that differs from
the pinned SHA, or SHA mismatch. It checks the *local fetched ref*, not live
GitHub availability: the reviewer must fetch and independently compare the
ref's SHA to the public repository before asserting freshness. It runs the **full tests** with OPENWORLD_SLOW_TESTS=1,
repository checks, W5 abrupt/stable/noise benchmarks from Issue #11,
additional gradual/alternating holdout seeds, the protected five-agent
SEC-001 replay/corruption suite, owner namespace negatives, and R0 demo.

## Evidence package

The tool saves every command's stdout and stderr **without editing them**,
plus exit code, argv, wall duration, process child CPU delta, child RSS
(native OS units), Python/SQLite/OS/CPU summary, exact main SHA and SHA256
for each raw stdout and stderr file. Its manifest is a local measurement
record, **not** a cryptographic attestation or an independent review by
itself. Keep the original logs for audit; publish only synthetic material
after the reviewer checks they contain no secrets.

## Second-contributor acceptance checklist

- [ ] Independent reviewer identity/attribution is recorded by the
      repository's normal governance process.
- [ ] Clean checkout, main HEAD and expected SHA match; raw files and
      manifest hashes verified against the reviewed commit.
- [ ] All command exit codes are zero; errors, test skips, expected-failures
      and stochastic negative results are explicitly recorded.
- [ ] W5 baseline Brier, latency and SQLite main+WAL+SHM bytes are
      reproduced, with CPU/RSS/filesystem context and uncertainty.
- [ ] Five-agent protected-event replay, evidence corruption and
      unauthorized cross-owner access scenarios are checked.
- [ ] Exact history is **not** falsely claimed reconstructable from compact
      predictive weights or a Fourier/Markov representation.
- [ ] W0 RFC-006 schema revision receives a separate authorized review;
      this script does not approve it.
- [ ] The R0 World-in-RAM / SQLite-HyperMemory non-atomicity, independent
      authentication, key custody, revocation and real power-loss gaps
      remain visible. None are solved by reproducible synthetic replay.
- [ ] Second contributor publishes signed/attributed acceptance or
      precise blockers on Issue #11. Gate stays OPEN until then.

## Recommended reviewer comment

Include exact commit SHA, OS/CPU/RAM, Python/SQLite, filesystem/WAL setup,
manifest SHA256, all step exit codes, failing/losing cases and whether
you actually ran the commands independently. Use one of:

- `PASS — independently reproduced the specified synthetic gates only`
- `FAIL — reproducible mismatch (attach raw evidence)`
- `BLOCKED — execution or evidence unavailable`

Do **not** report `production validated` or close Issue #11 solely on
CI PASS, local run PASS, or a single person's work. The W5 and R0 claims
remain deliberately bounded.
