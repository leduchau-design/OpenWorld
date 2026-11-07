# W5 P1 — SQLite / PostgreSQL Transaction Parity Protocol

**Status:** Implemented parity harness; **PostgreSQL live run still required**.  
**Issue:** #42 · Supporting #35, #41 and Gate #11.

## Scope

The experiment compares the existing `AtomicWorldLedger` (SQLite) and
`PostgresWorldLedger` (PostgreSQL) on the same small, deterministic synthetic
transaction trace. It is a **behavioral differential test** first, not a speed
competition or a test of authenticated human consent.

The trace covers: three initially provisioned synthetic agents, missing receiver
consent, incorrect owner assertion, an injected failure after debit, unchanged
replay, changed intent rejection, revoked receiver approval, a second legitimate
transfer, global tick and receipt/outbox invariants, stale-tick rejection, and
conservation of resources. The expected final state is 91/17/22 units, tick 2,
two durable receipts and two outbox records. A **separate two-connection race**
then makes two intents contend for the same world tick; exactly one must commit,
leaving tick 3, three receipts and three outbox rows while preserving 130 units. Both systems must produce **identical
logical outcomes**, including all denials.

## No-cost SQLite verification

```bash
python -m unittest discover -s tests -v
python benchmarks/w5_storage_parity.py
```

This needs Python 3.11+ and no third-party dependencies. It runs entirely in a
temporary SQLite database and never contacts an external server.

## Opt-in PostgreSQL verification

**Only use an empty disposable database** whose name starts
`openworld_ephemeral_`. The operator must provision it separately and install
Psycopg 3 into an isolated Python environment. The runner checks both explicit
opt-in and the database name before issuing CREATE TABLE or any mutation.
Do **not** point it at a development database that contains any valuable data.

```bash
# Illustrative local commands; do not commit credentials or real DSNs.
python -m pip install 'psycopg[binary]>=3,<4'
export OPENWORLD_PG_TEST_ISOLATED=YES_EPHEMERAL_DB
export OPENWORLD_PG_TEST_DSN='postgresql://.../openworld_ephemeral_test'
python benchmarks/w5_storage_parity.py --with-postgres
```

The runner checks initial metadata, account, receipt and outbox state and
raises on nonempty ledgers. No tables are dropped by the script. Never store
credentials in CI output or benchmark artifacts; configure credentials out of
band. A named ephemeral database and opt-in flag reduce accidental misuse,
but do **not** provide a sandbox boundary against malicious processes.

## Data and metrics

- Per-operation normalized outcomes (`ok`, `denied`, `rolled_back`).
- Exact final balances/tick and receipt/outbox counts; mismatches cause failure.
- Wall-clock total/median/p95/p99 of this short fixture as **diagnostics only**.
- Python/SQLite/OS and, if enabled, PostgreSQL server version.

**Not provided yet:** a powered PostgreSQL instance in project CI; meaningful
throughput/load/stress data; multi-process PostgreSQL writers beyond the bounded
two-connection race;
controlled CPU/RSS/network/disk measurements; WAL/fdatasync durability under
power loss; independent anti-rollback witness; production identity provider;
atomic SEC-002 capability debit + world effect across separate systems.

A single sequential trace cannot establish which backend is faster. PostgreSQL
results include network/driver overhead while SQLite is in-process. Hardware,
server placement, connection pooling, warmup, durability settings and contention
must be controlled before making any selection. Retain SQLite for local
HyperMemory and PostgreSQL as a **candidate control-plane authority**, not a
mandated global migration.

**Safety:** No real value transfer, user data, network messaging, model calls,
payment integration, or cross-owner W3 gateway enablement. `authenticated_owner`
is still a string asserted by the synthetic fixture, not independently verified.


## Manual-only disposable PostgreSQL CI

`.github/workflows/w5-postgres-parity-manual.yml` uses GitHub
`workflow_dispatch` **only**. It does not run on push, pull request, or a
schedule; it requires owner action once the workflow is available on the default
branch. It starts one disposable `postgres:16` service, installs the optional
Psycopg driver, runs this same logical trace plus a two-connection contention
check, and retains the synthetic JSON artifact for seven days. It never connects
to production or a user-provided database.

**Cost warning:** The optional workflow uses GitHub-hosted runner minutes and
package/container downloads. The repository owner must check Actions budget and
availability before manually dispatching it. No paid service is activated by
merely merging the file. Until a successful manual run is inspected, PostgreSQL
parity and any performance claim remain **UNVERIFIED**.
