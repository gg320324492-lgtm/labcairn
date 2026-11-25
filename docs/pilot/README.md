# Pilot material registrations

**Every copy the pilot imports is registered here, and the registration is
what the pilot knows about the material.** The pilot's authorisation is
signed — the grant over `pilot/LC-P4-PILOT/desensitised-copy` in
[`../acceptance/LC-P4-PILOT-providers-config.md`](../acceptance/LC-P4-PILOT-providers-config.md)
§6 — and a signed grant over an unregistered material is a hole nothing in
the tree can see: no record says which bytes were approved, so no later
reader can tell whether the material that arrived is the material the
advisor signed for.

A registration record closes that hole. It is the machine-checkable half of
the desensitisation checklist's part D
([`../plans/LC-P4-PILOT-desensitisation-checklist.md`](../plans/LC-P4-PILOT-desensitisation-checklist.md)),
and it is written and checked by
[`../../scripts/pilot_material_registration.py`](../../scripts/pilot_material_registration.py).

**The repository holds no material.** The raw files live in the authorised
environment (`E:/trial-material/`, G0 §4), and the record carries ids,
digests, counts, paths and a name — nothing else. There is no field for a
sentence of the manuscript: the tool builds the record field by field from a
closed vocabulary, a key it does not know is a key it refuses, and the two
places where a word could go — an operator's name and a copy's file name —
are held to a name's length and a name's number of words.

## The record

One JSON file per copy, under `registrations/`, named for the material id:
`docs/pilot/registrations/pilot-paper-001.json`. The checker verifies that
the file name matches the record's `material_id`, so a record cannot be
renamed past its own content.

## The elements

The checklist's part D is the list; this is where each item lands.

| # | Item | Field | What it holds | Where the value comes from |
|---|------|-------|---------------|----------------------------|
| 1 | D-1 | `material_id` | The pilot's stable id for the copy (`pilot-paper-001`), used by every later record that points at the material | The operator's choice; it names the file |
| 2 | D-2 | `authorisation` | The grant the copy is covered by: `grant_id`, `record` (the authorisation's own file, in this repository), `subject_ref`, `scope`, `granted_by`, `granted_at`, `expires_at` | **Read out of the authorisation record the citation names**, never typed: the tool finds the grant in that file whose scope covers the copy, and copies its six fields. The checker re-reads the file and reports a record whose grant has changed |
| 3 | D-3 | `metadata` | `page_count`, `word_count`, `figure_count`, `table_count`, `comment_count`, `revision_mark_count`, `heading_count`, `heading_outline_sha256` — counts and a digest, no content | The counts are the operator's measurements; the outline's digest and the heading count are measured by the tool |
| 4 | D-4 | `copy.sha256`, `copy.byte_size`, `copy.origin_sha256`, `copy.origin_byte_size` | The fingerprint of the desensitised copy and of the original it was derived from | **Measured by the tool**, from the bytes, at write time |
| 5 | D-5 | `storage.root`, `storage.relative_path` | Where the copy lives, in the authorised environment | The copy's own path, relative to the root; the checker requires the root to be an authorised one and the path to stay inside it |
| 6 | D-6 | `checklist` | The document the result applies to, the digest the result applies to (`applies_to_sha256`), and the result itself: `date`, `operator`, `items` (every checklist item, `pass` or `fail`) | **The owner's.** `create` writes it empty |
| 7 | — | `record_type`, `record_version`, `registered_at`, `registered_by`, `copy.file_name`, `copy.format` | What the record is, when it was written, who wrote it, and what the copy is called | The tool's own constants, its own timestamp, the operator's name from the command line, the copy's own name and the declared format |

`registered_at` is written by the tool and is never typed by hand.

## Usage

`create` assembles the record from the paths and the counts the operator
supplies, measures the digests itself, writes the record and checks it:

```
python scripts/pilot_material_registration.py create \
  --material-id pilot-paper-001 \
  --copy "E:/trial-material/pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-001.docx" \
  --original "E:/trial-material/source/original.docx" \
  --outline "E:/trial-material/pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-001.outline.txt" \
  --format docx \
  --pages 42 --words 12345 --figures 7 --tables 3 \
  --comments 18 --revision-marks 25 \
  --operator "advisor" \
  --grant-record "docs/acceptance/LC-P4-PILOT-providers-config.md" \
```

The outline is a plain file the operator exports from the copy — one heading
per line. The tool measures it and keeps the digest and the heading count;
the headings themselves stay in the authorised environment.

**The grant is not typed.** `--grant-record` names the authorisation record
in this repository, and the tool reads the grant out of it: the one whose
`scope` covers the copy's path. A scope typed on the command line would be
the operator's claim about the grant; a scope read out of the record is the
grant. That is why the command line has no `--grant-scope` — the check
cannot be satisfied by a claim.

`check` measures one record and names everything wrong with it, not just the
first problem:

```
python scripts/pilot_material_registration.py check \
  docs/pilot/registrations/pilot-paper-001.json \
  --copy "E:/trial-material/pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-001.docx"
```

With `--copy` it re-measures the material and compares: **a record whose
digest does not match the copy fails the check**. The `--copy` has to be
the copy the record registers — the tool refuses a path that is not the
registered one, because a check that measured some other file could not
say whether the material sitting at the registered path is the material
that was approved. `--require-signed` adds the owner's signature to the
things that must be there — that is the gate the import step runs.

## What the tool refuses

* a copy **inside the repository** — the material's bytes never enter it,
  and neither does anything that carries them;
* a copy **outside an authorised root** (`E:/trial-material` by default;
  the `LABCAIRN_MATERIAL_ROOTS` environment variable names others, with a
  semicolon between them);
* a copy whose path **no grant in the cited authorisation record covers** —
  the copy has to live where the grant reaches, or the grant has to be
  signed again;
* a material id that **already has a record**, unless `--force` is passed —
  and `--force` does not erase the owner's signature either: a signed
  record has to be removed by hand;
* a record written inside the repository **outside** `registrations/`, or
  under a name that is not the material id's;
* a declared format the copy's **bytes disagree with**;
* an operator's name, a copy's file name or a heading outline that is not
  a name at all — a sentence does not fit in any of them;
* a negative count, an id that is not an id, a name the record cannot hold.

## Who signs

`create` writes the checklist result **empty**. The result — the date, the
operator and the per-item pass/fail for every item the checklist lists — is
the owner's, and `sign` is the act that fills it:

```
python scripts/pilot_material_registration.py sign \
  docs/pilot/registrations/pilot-paper-001.json \
  --copy "E:/trial-material/pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-001.docx" \
  --operator owner --date 2026-11-26 --items items.json
```

`items.json` maps every checklist item id to `pass` or `fail`. The tool
reads the item ids out of the checklist itself, so a checklist that grows
an item makes the signature cover it; it refuses a set that misses an item,
one that carries an item the checklist does not have, and one that marks an
item anything other than `pass` or `fail`. **The copy is measured, not
trusted**: `--copy` names the material the signature is made against, it
has to be the copy the record registers, and the tool refuses to sign a
record whose digest does not match it. So a signature cannot drift onto a
different copy (C-4's single-pass rule), and it cannot be given to bytes
nobody looked at. The result is stamped with the digest of the copy that is
registered. A record that already carries a result is not signed again
unless `--force` is passed — a signature is replaced deliberately, the way a
record is.

## Measured, not carried forward

A number or digest in a registration is **measured when the record is
written**. The copy's digest is computed from the copy's bytes, the
original's from the original's bytes, the outline's from the outline file,
and `registered_at` is written by the tool. The counts are the operator's
own measurements of that copy, made in the same session — they are not
read from an older record, and the record says who registered it. A
registration that carries a previous copy's numbers describes a copy that
is not there.

## The copy that is not chosen yet

The record format is copy-agnostic: it registers whichever copy the owner
picks. G0 §4 names the standing candidate — the Phase 3 trial's
advisor-annotated working sample, sha256 `a7a38132…`, 8,871,367 B,
measured 2026-11-21/22 against the T1 supply receipt — and the pilot's
final material choice is the owner's. The standing candidate is the natural
default and nothing more; a record for it is written when the owner says
which copy it is.
