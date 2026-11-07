# W5 PostgreSQL report acceptance gate

**Status:** Research artifact validation; a successful JSON check is not independently authenticated evidence of an actual PostgreSQL server run. This is a follow-up to merged PR #54 and [Issue #42](https://github.com/CocAgent/OpenWorld/issues/42).

## Scope

The manual-only workflow `.github/workflows/w5-postgres-parity-manual.yml` retains `workflow_dispatch` as its **sole trigger**. It runs a disposable PostgreSQL 16 service and the already-authored differential trace. The new `scripts/verify_w5_pg_report.py` rejects reports that hide omitted PostgreSQL execution or omit crucial results even when a simplistic parity flag says `MATCH`.

## Exact independent expectations

- Three initial synthetic agent balances 100/10/20; exactly 26 operations with known expected denial, rollback and success outcomes.
- After the ordered trace: balances **91/17/22**, total **130**, tick **2**, exactly **2** receipts and outbox entries.
- In a separate two-connection race: **1** committed, **1** denied, tick **3**, receipts/outbox **3**, total **130**.
- Both databases must report **the same normalized domain trace**, and it must equal the independent expected values. A forged report saying both databases agree on an incorrect transfer is rejected.
- PostgreSQL must report `MATCH`, a nonempty server version and redacted ephemeral database marker; `NOT_RUN` is explicitly rejected by default.
- Timings must be finite and nonnegative, sorted by percentile, and carry the exact trace-operation count. They remain diagnostics, **not capacity or speed evidence**.
- The workflow attaches `GITHUB_SHA` and `GITHUB_RUN_ID` to the report; the validator checks them against its invocation. These **self-reported values do not authenticate the artifact**. Inspect the trusted GitHub Actions run, logs and source SHA separately.

## Owner procedure (manual)

1. Before spending hosted Actions minutes, review organizational/repository billing settings. Confirm the job and PostgreSQL service use only disposable data.
2. Open [Actions — W5 PostgreSQL parity (manual research)](https://github.com/CocAgent/OpenWorld/actions/workflows/w5-postgres-parity-manual.yml).
3. Select **Run workflow** on the reviewed `main` commit, once. Enter the exact acknowledgement `YES_BUDGET_CHECKED` **only after** checking Actions billing/quota. Never select a production database. Missing/incorrect acknowledgement or a branch other than `main` makes the job **SKIPPED**; a skipped job is **not** a successful PostgreSQL run.
4. Open the resulting run; require all steps to succeed. Download its artifact `openworld-w5-sqlite-postgres-parity` (7-day retention) and compare artifact `execution.git_sha` and `execution.github_run_id` with the trusted run metadata.
5. The artifact may also be checked offline:
   ```bash
   python scripts/verify_w5_pg_report.py w5-parity-result.json --expected-sha COMMIT_SHA --expected-run-id RUN_ID
   ```
6. Attach the pin, run URL, interpreter/PG version, run conclusion, validated JSON and any adverse result to Issue #42. If PostgreSQL fails or diverges, **keep Gate #11 and Issue #42 open** and diagnose; never edit benchmark results to manufacture parity.

## Explicit limits

- Unit tests validate **the report validator using entirely synthetic data**, not a running PostgreSQL server. Default CI does not launch PostgreSQL and does not provide PostgreSQL performance evidence.
- One bounded trace and two racing writers cannot establish throughput, p99 distributions, scale, external key custody, provenance or disaster recovery guarantees.
- The runner's `authenticated_owner` inputs remain fixture assertions; neither consent nor SEC-002 grants are tied to real external identity.
- The research workflow uses GitHub-hosted resources and must not execute automatically or repeatedly.
- Keep HyperMemory SQLite local by default; real cross-owner W3 execution remains disabled.
