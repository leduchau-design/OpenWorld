# W5 — Local disposable PostgreSQL parity runner

**Status:** Optional research procedure. Not evidence that live PostgreSQL has already been exercised. Related to Issue #42, manual GitHub Actions workflow from PR #54, and artifact validator from PR #56.

## Why

The existing `workflow_dispatch` experiment uses a GitHub-hosted runner and may consume Actions minutes. A local Docker option runs the **same tested Python parity trace** without starting a GitHub Actions job, cloud service or production database. It is not automatically executed, and it does not change the default SQLite HyperMemory backend.

## Requirements and owner approval

1. Review the code in `scripts/run_w5_pg_local.sh` before running it.
2. Use a trusted development machine with Docker Engine, Bash, Python 3.11+ and Psycopg 3. Do not expose the local Docker socket to untrusted tenants.
3. Manually download and inspect the PostgreSQL 16 image in advance, e.g. `docker pull postgres:16`, if absent. Download traffic may consume bandwidth. This script uses `--pull=never` and will not fetch it.
4. Install optional Psycopg 3 in an isolated Python environment if needed: `python -m pip install 'psycopg[binary]>=3,<4'`. The script **does not** install packages.
5. Explicitly acknowledge creation of a **disposable** database container, then run from the OpenWorld checkout:

```bash
OPENWORLD_PG_LOCAL_CONFIRM=YES_EPHEMERAL_CONTAINER \
  bash scripts/run_w5_pg_local.sh
```

The runner requires no arguments and refuses a caller-supplied DSN; any existing PostgreSQL or application database is out of scope. Do not run it with production privileges or live records.

## Safety and evidence

- Always creates a uniquely named, disposable `postgres:16` Docker container, not a database inside an existing instance; the image must already be local.
- Publishes PostgreSQL only on a **dynamic `127.0.0.1` port**. Uses an ephemeral randomly generated password; a temporary permissions-restricted env file is removed after `docker run`. Local Docker administrators may still inspect container environment; this is **not** secret isolation from a malicious host administrator.
- Allows at most a short readiness window and removes only the container **it created** on normal exit, errors and normal signals. It never invokes `docker system prune`, changes Docker volumes globally or calls remote APIs.
- Runs `benchmarks/w5_storage_parity.py --with-postgres` and `scripts/verify_w5_pg_report.py` from the checked-out source. Aborts on missing PostgreSQL results or mismatched logical outcomes.
- Writes an isolated temporary report directory under `/tmp` (or `TMPDIR`) with `w5-parity-result.json` and `run-metadata.json` containing the local Git commit, image ID and SHA256 of the report. **No DSN or password is saved in these report files.** Remove the report directory manually after reviewing.
- A successful report is **synthetic transaction parity**, not authentication, physical crash durability, high concurrency, performance superiority or production trust evidence. Environment timings are diagnostic only.

## Known gate gaps

The local runner is tested with offline guard tests, including fail-closed default refusal and Bash syntax checks. Those checks **do not launch PostgreSQL**. Independent live run evidence must record: OS/kernel, CPU, Docker Engine, image ID, Python/Psycopg version, exact source commit, CLI exit code, report SHA256 and full logical comparison. Keep Issue #42 OPEN until genuine PostgreSQL logs and independently reproduced results exist. Keep Issues #41/#34/#35 and Gate #11 OPEN for identity, key custody, rollback witnessing and consent integration.

The local run is *not* an alternative to an independently administered monotonic anti-rollback witness. Cross-owner W3 actions stay denied.