/**
 * The npm side of NOTICE, watched against the lockfile.
 *
 * **Why this file exists.** §5.2's licence audit resolves the *Python* closure
 * with `uv export` and never opens `shell/`, and `dependency-surface.test.mjs`
 * watches *which packages are locked* without ever asking what NOTICE says about
 * them. So the claim "every package this shell resolves travels under a licence
 * this repository records" had no witness on either side: a package could enter
 * the lock (that half is watched) while NOTICE stayed silent about it, and
 * NOTICE's own figures could drift from the lock with nothing noticing. That is
 * exactly what happened between the 2026-11-11 §2.4 (13 packages) and T08 landing
 * the electron-builder closure (268 packages) — 13 was a true measurement of the
 * earlier lock and stayed printed after the lock moved. This file is the witness
 * for the pairing: the NOTICE text on one side, the lock read by
 * `.github/shell-lockfile-keys.mjs` on the other, equalities in both directions.
 *
 * **What is compared.**
 *   1. Every `name@version` the lock pins has a §2.4 row, and every `name@version`
 *      §2.4 names is in the lock. An adoption nobody recorded reddens it, and so
 *      does a row for a package that left the lock.
 *   2. The surface NOTICE's table prints (keys, distinct packages, closures) is
 *      what the reader measures — label by label, so a renamed label reddens it
 *      rather than silently dropping out of the comparison.
 *   3. The split NOTICE names (§2.4.1 runtime, §2.4.3 build-only) is the split the
 *      lock's own `importers:` and resolved maps give.
 *   4. Every package carries a licence class, §2.4.2's class table adds up to
 *      §2.4.3's rows, and no copyleft identifier appears on either side.
 *
 * **The controls feed mutated text through these same functions**, not through a
 * copy of them — the `dependency-surface.test.mjs` precedent. A mutation control
 * that re-implements the check proves nothing about the check that runs.
 *
 * **What this file does not claim.** It does not read the registry or fetch a
 * tarball: the licence identifiers it compares are the ones NOTICE records, whose
 * provenance §5.3's commands state. It witnesses *the record against the lock*,
 * not the record against the registry.
 */

import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { lockfileKeys } from '../../.github/shell-lockfile-keys.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SHELL_ROOT = path.resolve(HERE, '..')
const REPO_ROOT = path.resolve(SHELL_ROOT, '..')
const LOCK_PATH = path.join(SHELL_ROOT, 'pnpm-lock.yaml')
const NOTICE_PATH = path.join(REPO_ROOT, 'NOTICE')

/**
 * `  name  version  licence  Copyright …` — one §2.4.1 row.
 *
 * The gaps are `+`, not a fixed count: the table pads each column, so a short
 * version like `4.4.3` is followed by six spaces and `MIT` by ten. A pattern
 * that allowed only four matched none of the 13 rows and reported "§2.4.1 names
 * no package" — a read that finds nothing when the table is present is the
 * failure this project's rules call the dangerous kind.
 */
const RUNTIME_ROW = /^  (\S+) +(\S+) +(\S+) +Copyright/
/** `  MIT  (190)` — one §2.4.3 group heading. */
const GROUP_HEADING = /^  (\S.*?) {1,2}\((\d+)\)$/
/** `    @electron/asar@3.4.1` — one §2.4.3 row. */
const DETAIL_ROW = /^    (\S+)$/
/** `  MIT                190` — one §2.4.2 class-table row. */
const CLASS_ROW = /^  (\S.*?\S) +(\d+)$/
/** `  keys in packages:                 268` — one §2.4 surface-table row. */
const SURFACE_ROW = /^  ([a-z][a-z @_-]*): +(\d+)$/

const COPYLEFT = /\b(?:AGPL|LGPL|GNU GPL|GPL-\d|GPLv\d|CPAL|QPL|EUPL)\b/i

/**
 * One numbered subsection of NOTICE, by its heading.
 *
 * The heading is matched at column zero and the slice stops at the next heading
 * or at a section rule, so a subsection that is renamed disappears loudly (the
 * reader throws) instead of silently returning the rest of the file.
 */
export function noticeSubsection(noticeText, heading) {
  const lines = noticeText.split('\n')
  const start = lines.findIndex((line) => line.startsWith(`${heading}  `))
  if (start < 0) throw new Error(`NOTICE has no subsection ${heading}`)
  // The slice ends at the next *heading* line: a sibling subsection
  // (`2.4.3  …`) or a major section (`3.  …`). A rule line of dashes is not a
  // terminator on its own, because every heading in this file is underlined by
  // one — treating the underline as a boundary ended the slice two lines in,
  // after the heading and its rule, and the reads below found no table in it.
  const HEADING = /^\d+(\.\d+)*\.?  \S/
  let end = lines.length
  for (let index = start + 1; index < lines.length; index += 1) {
    if (HEADING.test(lines[index])) {
      end = index
      break
    }
  }
  return lines.slice(start, end)
}

/** The §2.4.1 rows: `name@version` -> licence identifier. */
export function runtimeRows(noticeText) {
  const out = new Map()
  for (const line of noticeSubsection(noticeText, '2.4.1')) {
    const match = RUNTIME_ROW.exec(line)
    if (match) out.set(`${match[1]}@${match[2]}`, match[3])
  }
  if (out.size === 0) throw new Error('§2.4.1 names no package — the read found nothing')
  return out
}

/** The §2.4.3 groups: licence identifier -> the `name@version` rows under it. */
export function buildRows(noticeText) {
  const groups = new Map()
  let current = null
  for (const line of noticeSubsection(noticeText, '2.4.3')) {
    const heading = GROUP_HEADING.exec(line)
    if (heading) {
      current = heading[1]
      groups.set(current, [])
      continue
    }
    const row = DETAIL_ROW.exec(line)
    if (row && current) groups.get(current).push(row[1])
  }
  if (groups.size === 0) throw new Error('§2.4.3 names no licence group — the read found nothing')
  return groups
}

/** The §2.4.2 class table: licence identifier -> the count NOTICE prints for it. */
export function classCounts(noticeText) {
  const out = new Map()
  for (const line of noticeSubsection(noticeText, '2.4.2')) {
    const match = CLASS_ROW.exec(line)
    if (match) out.set(match[1], Number(match[2]))
  }
  if (out.size === 0) throw new Error('§2.4.2 prints no class row — the read found nothing')
  return out
}

/** The §2.4 surface table: label -> the number NOTICE prints beside it. */
export function surfaceCounts(noticeText) {
  const out = new Map()
  for (const line of noticeSubsection(noticeText, '2.4')) {
    const match = SURFACE_ROW.exec(line)
    if (match) out.set(match[1], Number(match[2]))
  }
  if (out.size === 0) throw new Error('§2.4 prints no surface row — the read found nothing')
  return out
}

/** Every `name@version` §2.4.1 and §2.4.3 name between them. */
export function namedByNotice(noticeText) {
  const named = new Set(runtimeRows(noticeText).keys())
  for (const rows of buildRows(noticeText).values()) for (const key of rows) named.add(key)
  return named
}

/**
 * The surface table's labels, and the reader's field each one is a claim about.
 *
 * Spelled out as a table rather than inferred, so that renaming a label in NOTICE
 * reddens `the surface NOTICE prints is the surface the lock measures` — a label
 * that silently vanishes from the comparison would otherwise stop being watched.
 */
const SURFACE_LABELS = {
  'keys in packages': 'packages_keys',
  'keys in snapshots': 'snapshots_keys',
  'keys in the union': 'union_keys',
  'peer-suffixed keys': 'peer_suffixed_keys',
  'distinct name@version': 'distinct_name_version',
  'distinct names': 'distinct_names',
  'names at more than one version': 'names_at_more_than_one_version',
  'electron closure': 'runtime_closure',
  'electron-builder closure': 'build_closure',
  'in both closures': 'shared_by_both_closures',
  'build-only': 'build_only',
  'in neither closure': 'entries_in_neither_closure',
  'unresolved edges': 'unresolved_edges',
}

const lockText = fs.readFileSync(LOCK_PATH, 'utf8')
const noticeText = fs.readFileSync(NOTICE_PATH, 'utf8')

test('every package the shell lock pins is named by NOTICE §2.4, and vice versa', () => {
  const measured = lockfileKeys(lockText)
  const locked = new Set(measured.all_entries)
  assert.equal(locked.size, measured.distinct_name_version,
    `the reader's entry list holds ${locked.size} packages but it reports ${measured.distinct_name_version} distinct name@version`)

  const named = namedByNotice(noticeText)
  const missingFromNotice = [...locked].filter((key) => !named.has(key)).sort()
  const absentFromLock = [...named].filter((key) => !locked.has(key)).sort()
  assert.equal(missingFromNotice.length, 0,
    `§2.4 names no row for these locked packages: ${missingFromNotice.slice(0, 12).join(', ')}` +
    `${missingFromNotice.length > 12 ? `, …${missingFromNotice.length} in total` : ''}. ` +
    'A dependency adopted without a NOTICE row is §0 rule 4 unrecorded, which is what this witness is for.')
  assert.equal(absentFromLock.length, 0,
    `§2.4 names packages the lock does not pin: ${absentFromLock.slice(0, 12).join(', ')}`)
  assert.equal(named.size, measured.distinct_name_version,
    `§2.4 names ${named.size} packages; the lock pins ${measured.distinct_name_version} at this revision`)
})

test('the surface NOTICE prints is the surface the lock measures', () => {
  const measured = lockfileKeys(lockText)
  const printed = surfaceCounts(noticeText)
  const expected = Object.keys(SURFACE_LABELS)
  const absent = expected.filter((label) => !printed.has(label))
  assert.equal(absent.length, 0,
    `§2.4's surface table no longer prints these labels, so they are no longer compared: ${absent.join(', ')}`)
  const extra = [...printed.keys()].filter((label) => !(label in SURFACE_LABELS))
  assert.equal(extra.length, 0,
    `§2.4's surface table prints labels nothing maps to the measurement: ${extra.join(', ')}`)
  for (const [label, field] of Object.entries(SURFACE_LABELS)) {
    const measuredValue = Array.isArray(measured[field]) ? measured[field].length : measured[field]
    assert.equal(printed.get(label), measuredValue,
      `NOTICE prints ${printed.get(label)} for "${label}" while the lock measures ${measuredValue}`)
  }
  assert.equal(measured.unresolved_edges.length, 0,
    `the closure walk could not resolve ${measured.unresolved_edges.length} edges: ${measured.unresolved_edges.slice(0, 4).join('; ')}`)
})

test('the closure split NOTICE states is the split the lock gives', () => {
  const measured = lockfileKeys(lockText)
  const runtimeNamed = [...runtimeRows(noticeText).keys()].sort()
  const buildNamed = new Set()
  for (const rows of buildRows(noticeText).values()) for (const key of rows) buildNamed.add(key)

  assert.deepEqual(runtimeNamed, measured.runtime_entries,
    '§2.4.1 does not name exactly the electron closure the lock resolves')
  assert.deepEqual([...buildNamed].sort(), measured.build_only_entries,
    '§2.4.3 does not name exactly the electron-builder closure entries that are not also in the runtime closure')

  const shared = measured.runtime_entries.filter((key) => new Set(measured.build_only_entries).has(key))
  assert.equal(shared.length, 0,
    `§2.4.1 lists ${shared.length} package(s) that are also in §2.4.3: ${shared.join(', ')} — the two lists must be disjoint`)
  assert.equal(measured.shared_by_both_closures, 8,
    'the closures no longer share 8 entries; §2.4 states 8, and a change there is a change in what ships')
  assert.equal(measured.entries_in_neither_closure, 0,
    'a locked package is reachable from neither declaration — §2.4 describes two trees and this one is in neither')
})

test('the licences NOTICE records cover the whole surface and name no copyleft term', () => {
  const groups = buildRows(noticeText)
  const runtime = runtimeRows(noticeText)
  const byPackage = new Map()
  for (const [licence, rows] of groups) for (const key of rows) byPackage.set(key, licence)
  for (const [key, licence] of runtime) byPackage.set(key, licence)
  assert.equal(byPackage.size, lockfileKeys(lockText).distinct_name_version,
    `${byPackage.size} packages carry a licence class in §2.4; the lock pins ${lockfileKeys(lockText).distinct_name_version}`)

  const copyleft = [...new Set(byPackage.values())].filter((licence) => COPYLEFT.test(licence))
  assert.equal(copyleft.length, 0, `§2.4 records a copyleft licence class: ${copyleft.join(', ')}`)

  const counts = classCounts(noticeText)
  const classTotal = [...counts.values()].reduce((sum, value) => sum + value, 0)
  const rowTotal = [...groups.values()].reduce((sum, rows) => sum + rows.length, 0)
  assert.equal(classTotal, rowTotal,
    `§2.4.2's class table adds to ${classTotal} while §2.4.3 lists ${rowTotal} rows`)
  for (const [licence, rows] of groups) {
    assert.equal(counts.get(licence), rows.length,
      `§2.4.2 says ${counts.get(licence)} ${licence} while §2.4.3 lists ${rows.length} under that heading`)
  }
  assert.equal(rowTotal, lockfileKeys(lockText).build_only,
    `§2.4.3 lists ${rowTotal} build rows; the lock's build-only closure is ${lockfileKeys(lockText).build_only}`)
})

// ------------------------------------------------------------------ the controls
test('a package arriving in the lock with no §2.4 row, and a §2.4 row with no lock entry, both redden the read', () => {
  // (a) the lock gains a package nothing recorded.
  const mutatedLock = lockText.replace('packages:\n', "packages:\n\n  'unheard-of-dependency@9.9.9': {}\n")
  assert.notEqual(mutatedLock, lockText, 'the control did not mutate the lock text')
  const mutated = lockfileKeys(mutatedLock)
  assert.equal(mutated.distinct_name_version, 269, 'the mutated lock does not carry the extra package')
  const named = namedByNotice(noticeText)
  const missing = mutated.all_entries.filter((key) => !named.has(key))
  assert.ok(missing.includes('unheard-of-dependency@9.9.9'),
    'the coverage read did not notice a package that arrived in the lock and in nothing else')

  // (b) NOTICE names a package the lock does not pin.
  const mutatedNotice = noticeText.replace('    node-abi@4.40.0', '    node-abi@999.999.999')
  assert.notEqual(mutatedNotice, noticeText, 'the control did not mutate the NOTICE text')
  const absent = [...namedByNotice(mutatedNotice)].filter((key) => !mutated.all_entries.includes(key))
  assert.ok(absent.includes('node-abi@999.999.999'),
    'the coverage read did not notice a §2.4.3 row for a package the lock does not name')
})

test('a drifted count, a copyleft class, or a package moved between the closures all redden the read', () => {
  const drifted = noticeText.replace('  distinct name@version:            268',
    '  distinct name@version:            260')
  assert.notEqual(drifted, noticeText, 'the control did not mutate the NOTICE text')
  const printed = surfaceCounts(drifted).get('distinct name@version')
  assert.notEqual(printed, lockfileKeys(lockText).distinct_name_version,
    'a drifted surface count survived the comparison — the count read is not looking at what it claims')

  const copylefted = noticeText.replace('  WTFPL                1', '  GPL-3.0-or-later    1')
  assert.notEqual(copylefted, noticeText, 'the control did not mutate the NOTICE text')
  const flagged = [...classCounts(copylefted).keys()].filter((licence) => COPYLEFT.test(licence))
  assert.ok(flagged.includes('GPL-3.0-or-later'),
    'a copyleft class written into §2.4.2 was not flagged')

  // A §2.4.3 package written instead as a §2.4.1 runtime row must disagree with
  // the lock's own closure, because the split is measured, not restated.
  const moved = noticeText
    .replace('    node-abi@4.40.0\n', '')
    .replace('  electron                        45.2.3    MIT          Copyright (c) Electron contributors',
      '  electron                        45.2.3    MIT          Copyright (c) Electron contributors\n  node-abi                        4.40.0     MIT          Copyright (c) nobody')
  assert.notEqual(moved, noticeText, 'the control did not mutate the NOTICE text')
  const movedRuntime = [...runtimeRows(moved).keys()].sort()
  assert.ok(movedRuntime.includes('node-abi@4.40.0'), 'the moved row was not read as a runtime row')
  assert.notDeepEqual(movedRuntime, lockfileKeys(lockText).runtime_entries,
    'a package moved from the build closure into §2.4.1 was not noticed against the lock')
})

test('the reader these checks use is the one §5.3 names, and it is not a second copy', () => {
  const readerPath = path.join(REPO_ROOT, '.github', 'shell-lockfile-keys.mjs')
  assert.ok(fs.existsSync(readerPath), `${readerPath} is gone, so §5.3's lead command names nothing`)
  const readerText = fs.readFileSync(readerPath, 'utf8')
  assert.ok(readerText.includes('export function lockfileKeys'),
    'the reader exports no entry point, so a witness would have to re-implement it')
  assert.ok(readerText.includes('export function closureOf'),
    'the closure walk is not exported, so no witness could feed it mutated text')
  const counts = lockfileKeys(lockText)
  assert.equal(counts.union_keys, 273, `the reader counts ${counts.union_keys} keys; 273 were measured at this revision`)
  assert.equal(counts.packages_keys, 268, `packages: holds ${counts.packages_keys} keys; 268 were measured`)
  assert.equal(counts.snapshots_keys, 268, `snapshots: holds ${counts.snapshots_keys} keys; 268 were measured`)
  assert.equal(counts.all_entries.length, 268, 'the reader names no complete entry list to compare against')
})
