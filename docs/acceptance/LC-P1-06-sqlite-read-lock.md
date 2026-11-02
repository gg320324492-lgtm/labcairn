# LC-P1-06 — SQLite read lock

**Subject:** release notes §2.17, `src/labcairn/db/session.py`
**Date:** 2026-11-02
**Verdict:** the debt is closed. A read now takes a snapshot instead of
SQLite's write lock, and the write transaction still takes the write lock
before its first read — ADR-0003 C3 unchanged.

## The debt, as it was recorded

> `src/labcairn/db/session.py` opens every transaction with `BEGIN IMMEDIATE`.
> That is right for a write; a read is a transaction too, so a read takes the
> write lock for as long as it is open. The per-request session bounds that
> window to one request.
>
> — release notes §2.17

The code's own comment said *"Readers do not block the writer"*. That is true
of WAL and was **not** true of the application's own reads: the engine put the
same `BEGIN IMMEDIATE` on every transaction, read or write.

## Measured before the change

Product code, a migrated file, a writer holding `BEGIN IMMEDIATE` without
committing, and a second engine opening its own connection. Busy timeout was
300 ms so the wait would be reported rather than hidden.

| Observation | Result |
|---|---|
| `PRAGMA journal_mode` on a fresh raw connection | `wal` — WAL was already enabled and persistent |
| Raw `sqlite3` connection, deferred `BEGIN`, read while the writer holds | **6.0 ms**, completed |
| Product session, pure `SELECT` while the writer holds | **failed after 0.40025 s**: `database is locked` |

The conclusion is the one the numbers force: WAL was doing its job, and the
lock was the read's own `BEGIN IMMEDIATE` asking for the write lock. The
candidate direction "switch on WAL" was therefore not the fix — it was already
the state.

## What changed

* `create_db_engine(..., readonly=True)` — a read-only engine. Its `begin`
  event issues a plain deferred `BEGIN`, and every connection sets `PRAGMA
  query_only=ON` **after** `journal_mode=WAL` (switching a database into WAL
  writes the file header, which `query_only` would refuse). The two settings
  are deliberately redundant: the deferred `BEGIN` is what lets the read take a
  snapshot, and `query_only` makes SQLite refuse a write on that connection, so
  a read-only session handed to writing code fails loudly instead of silently
  upgrading.
* `application_context(..., readonly=False)` — the context every task-scoped
  command runs against now has an explicit read-only form.
* Four CLI commands that only read use it: `task status`, `sources inspect`,
  `sources addresses`, `artifacts list`. Commands that write anything keep the
  default context.
* The write engine is unchanged: `BEGIN IMMEDIATE` before its first read.

## Measured after the change

Same scenario as the "before" table (writer still holds the lock):

| Observation | Result |
|---|---|
| Read on the read-only engine | **0.00015 s**, correct value |
| `PRAGMA query_only` on that connection | `1` |
| Write attempted on that connection | refused in **0.00015 s**: `attempt to write a readonly database` |
| `PRAGMA journal_mode` after every engine was disposed, read raw | `wal` |

## Witnesses

All in `tests/test_store_concurrency.py`:

| Test | What it holds |
|---|---|
| `test_the_read_only_engine_emits_a_deferred_begin` | the read-only engine really emits `BEGIN`, not `BEGIN IMMEDIATE` |
| `test_a_read_completes_while_a_write_transaction_holds_the_lock` | the behaviour: the read finishes while a writer holds the lock |
| `test_a_read_only_session_refuses_a_write` | `query_only=1` and SQLite refuses the write |
| `test_wal_survives_the_engine_that_set_it` | WAL is read from a raw connection after all engines are gone — the setting is in the file |
| `test_a_read_only_cli_command_reads_while_a_writer_holds_the_lock` | wiring: `task status` completes in-process against a workspace the CLI made, while a writer holds the lock |

`test_the_write_lock_is_taken_before_the_first_read` is unchanged and still
green: the write engine emits `BEGIN IMMEDIATE` for every transaction.

## Mutation checks — the witnesses were made to fail

A witness that cannot fail is a sentence. Each mutation was applied to the
working tree, the named test was run, and the file was restored byte-for-byte
from a backup (not `git checkout`).

| Mutation | Result |
|---|---|
| Read-only engine emits `BEGIN IMMEDIATE` (as before the change), `query_only` removed | `test_a_read_completes…` **failed in 3.37 s** with `database is locked` — the property itself, not a neighbouring assertion |
| Same, with `query_only` left in place | two witnesses failed, at `BEGIN IMMEDIATE` refused by `query_only` |
| `PRAGMA query_only=ON` removed | `test_a_read_only_session_refuses_a_write` failed: `PRAGMA query_only` read `0` |
| `PRAGMA journal_mode=WAL` changed to `DELETE` | `test_wal_survives_the_engine_that_set_it` failed: `delete` ≠ `wal` |
| `task status` built without `readonly=True` | the wiring witness **failed after 12.24 s** with `database is locked` |

The first row is the "before" state reproduced on the new test: a read whose
`BEGIN IMMEDIATE` meets a held write lock waits out the busy timeout and fails.
That is the number 0.40025 s measured above, and it is why the fix is the
deferred `BEGIN` rather than WAL.

## Runs

| Check | Result |
|---|---|
| `tests/test_store_concurrency.py` | 12 passed |
| `tests/test_store_concurrency.py` + `test_store_atomicity.py` + `test_store_migrations.py` | 31 passed |
| `python -m mypy` | Success: no issues found in 376 source files |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 414 files already formatted |

The measurement is local; no CI run was started and no pull request was
opened. The tests were added to an existing file, so the three registrations
do not change. That file's measured cost is 2.36 s on Ubuntu and 30.34 s on
Windows, against a balance growth room of 98.5 s and 508.9 s respectively in
`.github/ci-shards.json`, so the shard costs do not need re-measuring.

## What was not done

* **The service still uses one write context for its lifetime.** `labcairn
  serve` builds a single `application_context` and its read requests still take
  the write lock. Wiring the service's reads to a read-only engine is a larger
  change — it needs a per-request or per-read session and a decision about the
  session's lifetime — and this record does not claim it.
* Commands that write (create, run, resume, report, claim, approvals, ingest,
  figure, rule confirmation) keep the write context, by design.
* No change to migrations or to `TaskStore`; the read-only engine is a
  constructor option and the store does not need to know which one it is on.
* **The residual is stated rather than hidden:** a read-only context is only
  safe because SQLite refuses writes on it. A future command that needs to
  write one row and read the rest must stay on the write context; the
  `pytest.raises` in `test_a_read_only_session_refuses_a_write` is the
  witness that the refusal is real, not a convention.
