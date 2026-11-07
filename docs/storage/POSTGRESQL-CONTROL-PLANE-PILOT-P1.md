# Issue #42 — Optional PostgreSQL control-plane pilot (P1)

**Status:** DRAFT / research implementation. This is a storage contract and executable adapter, **not a PostgreSQL performance result** or authorization service.

## Why this experiment exists

OpenWorld must distinguish **local predictive HyperMemory** from an **authoritative shared control plane**. SQLite is appropriate for local, reproducible, single-process memory experiments. PostgreSQL is a candidate backend for shared transactional operations involving multiple owners and services, but its operational cost and concurrency behavior must be measured rather than assumed.

The existing `AtomicWorldLedger` uses a single SQLite database file and commits the sender/receiver approvals, balances, global tick, receipt and outbox together. Its `authenticated_owner` field is an **assertion by a trusted test fixture**, not independently authenticated identity or SEC-002 grant consumption.

## What this PR implements

- `PostgresWorldLedger`: optional Psycopg **3** adapter with no changes to the default SQLite engine.
- Explicit `autocommit=True` connection and `with connection.transaction()` to ensure the block is the outermost commit, not an implicit savepoint in an already-open transaction.
- PostgreSQL constraints on owners, nonnegative balances, globally unique request nonce, per-intent dual role approval, one receipt and one outbox event per intent.
- `SELECT ... FOR UPDATE` locks a **single global world tick** and both account rows before changing balances. This intentionally serializes execution; it is a reference for atomicity, not a throughput-optimized scheduler.
- A synthetic fault injected **after source debit but before target credit** must roll back *all* changes.
- An exact same-intent retry returns the already committed receipt; a changed request hash or duplicate nonce is rejected.
- Static/schema and SQLite reference tests run without any external dependencies. The real PostgreSQL integration test is **opt-in** and skips by default.

## Optional local verification (requires explicit throwaway database)

No PostgreSQL service, live dataset, credentials or cloud instance is provided by this repository. These commands are **instructions, not completed measurements**:

```bash
# In a disposable virtual environment:
python -m pip install 'psycopg[binary]>=3,<4'
# Provision an empty, isolated, local PostgreSQL test DB by your own means.
export OPENWORLD_PG_TEST_DSN='postgresql://test_user@localhost/openworld_disposable'
export OPENWORLD_PG_TEST_ISOLATED='YES_EPHEMERAL_DB'
python -m unittest discover -s tests -p 'test_postgres_control_plane.py' -v
```

**Safety:** The opt-in test initializes persistent `ow_p1_*` tables and adds fixture rows. Never point it at a shared, reused or production database. It refuses to proceed when the test ledger already contains accounts or a nonzero tick. The variables are not read during ordinary CI.

## Conformance and future acceptance

| Requirement | Current evidence | Pending |
|---|---|---|
| SQLite reference: atomic debit/credit, exact receipt | Local CPU-only test | Recheck on merged main |
| PostgreSQL schema and adapter code | Compile/schema/static tests | Run with real PostgreSQL |
| PostgreSQL rollback/retry semantics | Opt-in executable test | Needs provisioned throwaway PG service |
| Multi-process concurrency | Global tick lock design | Actual race/latency tests |
| Postgres vs SQLite p50/p95/p99, CPU, RSS, WAL | No benchmark yet | Controlled matched traces + repetition |
| SEC-002 authenticated identity and receiver consent | Not integrated | Must be inside reviewed trusted service boundary |
| SEC-003 independent anti-rollback witness | In-memory reference only | Real external independent custody and fail-closed recovery |
| Cross-owner W3 gateway | Still default deny | Explicit owner/security authorization before enabling |

## Consequences

**Do not** silently migrate HyperMemory to PostgreSQL. Do not interpret successful SQL-atomic synthetic balance movements as an authenticated transfer. A local PostgreSQL transaction cannot roll back an already delivered HTTP/tool effect; outbox dispatch must have idempotent receipts and recovery procedures.

This is the first PG backend experiment, not completion of Issue #42. Independent scientific evaluation must compare equivalent semantics and storage durability, not only raw throughput.

### References

- [Psycopg 3 transaction contexts](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)
- [PostgreSQL row locking](https://www.postgresql.org/docs/current/explicit-locking.html)
- [PostgreSQL unique constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)