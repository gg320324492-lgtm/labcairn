# LC-P3-02 — the record format for the twelve-row reopen rerun (2026-11-18)

**What this document is.** The format in which the twelve-row rerun's result
enters the repository, and the rules that make such a record checkable.

**Why it is a format and not a record.** The 44-row ledger of 2026-11-10 is in
the repository as a *record*
(`LC-P3-02-fifth-version-44-rows-2026-11-17.md`). The twelve-row rerun has
been run but not yet recorded, and the tool that records it has just moved
into the repository (`scripts/closeout_12_rows.py`) from a directory outside
it. This document says what the record will look like when it is written, so
that the record is not invented at the moment it is needed.

**The three sentences every such record carries.**

1. *What was observed* — the artefact, by path and by SHA-256.
2. *On which host, on which day, by whom.*
3. *That it is a second observation and not a replacement for the 44-row
   ledger of 2026-11-10.*

The third sentence is not decoration. The two observations are of the same
rows on different bytes, and a reader who takes the newer one for the older
one -- or the other way round -- reads a date where there is none.

---

## 1. What the record is, and what it is not

- It is a **second observation** of twelve of the 44 rows, on the regenerated
  artefacts, on a later day, in a later run.
- It is **not** a replacement for the 44-row ledger of 2026-11-10, and it does
  not amend it. The 44-row ledger's bytes and digest are unchanged by it, and
  the record says so.
- It is **not** a claim that any issue is closed. The tool judges each issue
  against **its own closure condition** and prints one of three verdicts;
  the record carries that judgement verbatim, including the gaps.
- It is **not** a support-matrix entry. #190 is closed by a dated
  support-matrix row, not by a passing row, and the record says that #190 is
  out of the rerun's scope.

## 2. Where it goes, and what it is called

| | |
|---|---|
| Directory | `docs/acceptance/` |
| File name | `LC-P3-02-rerun-12-rows-<YYYY-MM-DD>.md` |
| Title | `# LC-P3-02 — twelve-row reopen rerun (<YYYY-MM-DD>)` |

The date in the name and in the title is the **day of the observation**, not
the day the record was written. A record written on a later day than it
observes says so in its "Final status sentence".

## 3. The required fields

Every field below is required. A field that cannot be filled is written
`NOT MEASURED` with the reason beside it -- never `0`, never a blank, and
never a value carried forward from an earlier record.

| field | what it must say | why it is required |
|---|---|---|
| **Observation date** | the day the hosts were opened | a rerun on a different day is a different observation |
| **Operator** | who opened the files, and on which machine | the observation is a person's, and it is local |
| **Pack** | the directory the artefacts came from, and its name | the pack is the boundary of what was observed |
| **Artefact path** | the absolute path of the artefact, per row | the record says *which file*, not a family of files |
| **Artefact SHA-256** | the digest measured on that file, per row | a path is not an identity; the digest is |
| **Artefact bytes** | the size measured on that file, per row | it catches a truncated copy of the right file |
| **Host** | the host application and its version string, per row | a WPS result is not a Word result |
| **Tool** | `scripts/closeout_12_rows.py` and the repository revision it ran from | the judgement is a program's, and programs change |
| **Row verdicts** | the twelve row ids with their verdicts | the row-level evidence, in the reader's hand |
| **Issue verdicts** | `#189`, `#191`, `#192` with the tool's verdict each | what may be closed, and what may not |
| **Out of scope** | `#190`, and why | the place a reader looks when deciding what may close |
| **Ledger status** | the 44-row ledger's SHA-256 and the statement that it was not written to | the boundary between the two observations |
| **Not a replacement** | the mandatory sentence (see §4.4) | so that no reader mistakes one for the other |

## 4. The anchoring rules

### 4.1 The artefact is named by path **and** by digest

A path names a place; a digest names a thing. Both are printed, and the
digest is the one **measured by the tool on the file in the pack** -- not
copied out of the table it is checking, and not typed by hand. The tool
refuses a row whose `sha256_before` is not the artefact's digest, so a
mismatch is a finding rather than a silent pass.

### 4.2 The host is named with its version string

`host_name` alone is not enough: WPS 12.1 and WPS 12.2 are different hosts
for this purpose, and so are Word 2019 and Word 2010. The record gives the
version string, and the day it was measured.

### 4.3 The day and the person are named separately

The day the hosts were opened and the day the record was written are two
dates, and they are not the same. A record written days later says which is
which.

### 4.4 The sentence that must be in every such record

> The 44-row ledger of 2026-11-10 is a different observation, on different
> bytes; this record does not amend it and does not replace it.

The same sentence is carried in the notes of every row of the append record
(`rerun12-append-<run-id>.csv`), so that a reader who takes one row out of
context still sees it.

### 4.5 The judgement is anchored to the tool that made it

The record names `scripts/closeout_12_rows.py` and the revision it ran from.
A verdict without the tool and the revision behind it cannot be re-derived,
and a verdict that cannot be re-derived is a claim rather than a measurement.

## 5. The template

Copy this skeleton, fill every placeholder, and delete no section. A section
that has nothing to say is kept and says `NOT MEASURED` with the reason.

```markdown
# LC-P3-02 — twelve-row reopen rerun (<YYYY-MM-DD>)

**Date:** <YYYY-MM-DD, the day the hosts were opened>. **Recorded:**
<YYYY-MM-DD, the day this file was written>. **Type:** dated external-ledger
completion record for the twelve-row rerun of the reopen ledger. No DOCX
material, screenshot bytes, personal reviewer text, or raw ledger is
committed here; all of that stays under `<pack directory>`.

## Final status sentence

**Twelve-row reopen rerun: <N> of 12 rows completed and format-validated;
<verdict distribution>; every row re-hashed unchanged; validator
<VALIDATOR RESULT: PASS|FAIL>.**

This sentence reports observation completion and format validity. It does not
say all twelve host judgements are PASS, and it does not extrapolate a WPS
result into a Word result.

## Hosts and observation boundary

- WPS Office `<version string>`: <count> primary rows.
- Word reference rows: <count> rows on Microsoft Office 2019 `<version string>`.
- Operator: <who>, on <machine>.
- Pack: `<directory>`; the artefacts below are the ones the tool measured.

## The twelve rows

| row id | artefact | sha256 | bytes | host | verdict |
|---|---|---|---|---|---|
| `<row id>` | `<absolute path>` | `<sha256>` | <bytes> | `<host> <version>` | `<verdict>` |

## Ledger binding

| measured value | result |
|---|---|
| 44-row ledger SHA-256 | `<sha256>` |
| 44-row ledger bytes | <bytes> |
| 44-row ledger data rows | 44 |
| the ledger was written to by this run | no |
| validator | `<VALIDATOR RESULT: ...>`, format and boundaries only |

The 44-row ledger of 2026-11-10 is a different observation, on different
bytes; this record does not amend it and does not replace it.

## Issue verdicts

| issue | verdict | what the gap is |
|---|---|---|
| #189 | `<CLOSED-READY|NOT-CLOSED|NOT-SETTLED-BY-THE-MACHINE>` | <the unmet conditions, or the owner's part that is outstanding> |
| #191 | `<...>` | <...> |
| #192 | `<...>` | <...> |

**#190 is not in this round's closure scope** and is not closed by this
rerun: it is a WPS rendering limitation, its only row is not among the
twelve, and its closure route is a dated support-matrix entry.

## The tool that made the judgement

- `scripts/closeout_12_rows.py` at revision `<full sha>`, run id `<run id>`.
- The append record, the validation report, the closure table and the
  manifest it wrote are at `<paths>`; their digests are in the manifest.

## Evidence location

- The filled twelve-row table: `<path>`.
- The append record: `<path>`.
- Screenshots and the raw pack: under `<pack directory>`, outside the
  repository.
```

## 6. What may not go into the record

- **Material words.** The repository is public; the corpus's text, the
  operators' personal text and the reviewers' text stay outside it.
- **Screenshot bytes and raw ledger rows.** They stay under the pack
  directory; the record names them and gives their digests.
- **A number that was not measured.** A digest that was not measured is
  `NOT MEASURED`, and a count that was not counted is `NOT MEASURED`. The
  record is read by someone deciding whether an issue may be closed, and a
  false zero there is a false yes.
- **A claim that an issue is closed.** The tool's verdict is carried
  verbatim. `NOT-SETTLED-BY-THE-MACHINE` is **not** a soft yes: it means the
  machine ran out of things it can read, and the owner decides.

## 7. What the tool gives the record, and what the owner adds

| the tool writes | the owner adds |
|---|---|
| the per-row validation report | the screenshots' digests and what they show |
| the twelve-row append record | the day, the operator, the machine |
| the issue verdicts and the gaps | the support-matrix entry for #190, if it is closed |
| the manifest: digests, run id, the tool's revision | the declarations (screenshots, recorded decisions, waivers) that turn `NOT-SETTLED-BY-THE-MACHINE` into `CLOSED-READY` |

**The tool's output is the record's skeleton, not its judgement.** The tool
measures bytes and reads cells; the owner looks at a screen and decides. A
record that says which is which is a record a later reader can check.
