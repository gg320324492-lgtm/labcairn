/**
 * NOTICE's scope, watched against the surfaces it names.
 *
 * **Why this file exists.** NOTICE §2.4 records the shell's 268 npm packages
 * and §2.4.2 said of them, "Nothing in either tree is copyleft". That sentence
 * was true of the shell's two npm trees and was read as being about the
 * product. Two surfaces a LabCairn distribution actually carries were outside
 * the file entirely: the eight binaries the NSIS installer distributes, two of
 * which are LGPL-2.1, and the web tree, which carries MPL-2.0 and CC-BY-4.0.
 * `shell/test/notice-licences.test.mjs` watches the shell's packages against
 * `shell/pnpm-lock.yaml`; nothing watched the *scope*, so a file could grow two
 * copyleft surfaces and keep claiming a permissive distribution.
 *
 * **What is compared.**
 *   1. The scope table §0.1 prints names every surface, and each row's count
 *      is the count the artefact it names actually measures — the shell's row
 *      against `shell/pnpm-lock.yaml`, the web's row against
 *      `web/pnpm-lock.yaml`, the installer's row against the binaries §2.5
 *      names.
 *   2. The scope table's copyleft column is not narrower than what the file
 *      records. A table that says "none" while §2.5 records LGPL-2.1 and §2.6
 *      records MPL-2.0 is the contradiction this file exists to catch.
 *   3. No sentence in NOTICE asserts the absence of copyleft without naming
 *      the surface it is about. The old sentence named no surface; that is
 *      the shape of the defect, and it is what the third check reddens.
 *   4. §2.6's licence class table adds up to the lock-key denominator it
 *      claims, so a drifted class count cannot hide inside a correct total.
 *
 * **What it deliberately does not do.** It does not open the installer, and it
 * does not enumerate the binaries inside it: the owner deferred the per-binary
 * licence census of the installer on 2026-11-12, so the eight entries are
 * checked against each other and not against an artefact. It does not
 * investigate the Chromium payload, which is deferred as well. It reads the
 * two lockfiles in the repository and NOTICE itself; it needs no install, no
 * network and no Electron binary, which is what the `shell.yml` job provides.
 *
 * **The controls feed mutated text through these same functions**, not through
 * a copy of them — the `notice-licences.test.mjs` precedent. A mutation
 * control that re-implements the check proves nothing.
 */

import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { lockfileKeys } from '../../.github/shell-lockfile-keys.mjs'
import { webLockKeys } from '../../.github/web-lockfile-keys.mjs'

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const NOTICE_TEXT = fs.readFileSync(path.join(REPO, 'NOTICE'), 'utf8')
const SHELL_LOCK = fs.readFileSync(path.join(REPO, 'shell', 'pnpm-lock.yaml'), 'utf8')
const WEB_LOCK = fs.readFileSync(path.join(REPO, 'web', 'pnpm-lock.yaml'), 'utf8')

/**
 * The surfaces §0.1 must name, and the terms each one's row must carry.
 *
 * `none` is a value rather than a list of terms: the shell tree's row must
 * say exactly `none`, because §2.4 measured no copyleft among the 268, and a
 * row that says "no copyleft" would be a phrasing change, not a wider claim.
 */
const SURFACES = {
  'python dependency closure': ['MPL-2.0', 'LGPL'],
  'shell npm tree': ['none'],
  'installer-distributed binaries': ['LGPL-2.1'],
  'web npm tree': ['MPL-2.0', 'CC-BY-4.0'],
}

/** `  StdUtils.dll — 102,400 bytes` — one §2.5 binary block heading. */
const BINARY_HEADING = /^ {2}([A-Za-z0-9_.-]+\.(?:dll|exe)) — ([\d,]+) bytes$/
/** `    licence  LGPL-2.1-or-later` — one field of a §2.5 binary block. */
const BINARY_FIELD = /^ {4}(path|sha256|bundle|licence|holder|where)\s{2,}(\S.*)$/
/** `  MIT               207` — one §2.6 licence class row. */
const CLASS_ROW = /^ {2}(\S.*?\S) {2,}(\d+)$/

/**
 * A sentence that asserts the absence of copyleft.
 *
 * The pattern is deliberately narrow: it wants a negation, then a verb of
 * being, then the word. `no copyleft licence in this tree` is not an absence
 * claim about the *distribution* — it is a statement about one named tree,
 * and §2.4.1 makes the tree explicit. `no copyleft identifier appears in any
 * of the 268 packages'` is a statement about those packages. Only a sentence
 * that says *nothing* or *no* thing *is* copyleft is the claim that can be
 * read as being about the product.
 */
const ABSENCE_CLAIM =
  /\b(?:nothing|no)\b[^.]{0,160}?\b(?:is|are|was|were)\s+(?:an?\s+|any\s+)?copyleft(?:-free)?\b/i

/**
 * The surfaces a sentence may name for an absence claim to be scoped.
 *
 * These are the four surfaces §0.1 lists. A sentence that says the
 * distribution carries no copyleft, and names none of them, is the defect.
 */
const SCOPE_WORDS = [/\bshell\b/i, /\binstaller\b/i, /\bweb\b/i, /\bpython\b/i]

/**
 * One numbered subsection of NOTICE, by its heading.
 *
 * The heading is matched at column zero and the slice stops at the next
 * heading line, so a subsection that is renamed disappears loudly (the reader
 * throws) instead of silently returning the rest of the file.
 */
export function noticeSubsection(noticeText, heading) {
  const lines = noticeText.split('\n')
  const start = lines.findIndex((line) => line.startsWith(`${heading}  `))
  if (start < 0) throw new Error(`NOTICE has no subsection ${heading}`)
  const HEADING = /^\d+(\.\d+)*\.?  \S/
  let end = lines.length
  for (let index = start + 1; index < lines.length; index += 1) {
    if (HEADING.test(lines[index])) {
      end = index
      break
    }
  }
  return lines.slice(start, end).join('\n')
}

/**
 * The scope table §0.1 prints, as one row per surface.
 *
 * The row is read by splitting on runs of two or more spaces, because the
 * table pads every column to its widest cell and the copyleft cell carries
 * single spaces inside it (`MPL-2.0, LGPL, GPL-3.0`). A reader that split on
 * single spaces would cut that cell into three.
 */
export function scopeRows(noticeText) {
  const rows = []
  for (const line of noticeSubsection(noticeText, '0.1').split('\n')) {
    if (!/^ {2}\S/.test(line)) continue
    const cells = line.trim().split(/ {2,}/)
    if (cells.length !== 4) continue
    if (!/^\d+$/.test(cells[1])) continue
    rows.push({
      surface: cells[0],
      items: Number(cells[1]),
      copyleft: cells[2],
      measuredIn: cells[3],
    })
  }
  if (rows.length === 0) {
    throw new Error('§0.1 prints no surface row — the read found nothing')
  }
  return rows
}

/** The binaries §2.5 names, with the fields each block records. */
export function installerBinaries(noticeText) {
  const binaries = []
  let current = null
  for (const line of noticeSubsection(noticeText, '2.5').split('\n')) {
    const heading = BINARY_HEADING.exec(line)
    if (heading) {
      current = {
        name: heading[1],
        bytes: Number(heading[2].replace(/,/g, '')),
        fields: {},
      }
      binaries.push(current)
      continue
    }
    const field = BINARY_FIELD.exec(line)
    if (field && current) current.fields[field[1]] = field[2]
  }
  if (binaries.length === 0) {
    throw new Error('§2.5 names no binary — the read found nothing')
  }
  return binaries
}

/**
 * The licence classes §2.6 prints, with their counts.
 *
 * The `Total` row is dropped: it is the sum of the rows above it, and
 * including it would make the sum twice what the table claims.
 */
export function webClassCounts(noticeText) {
  const counts = new Map()
  for (const line of noticeSubsection(noticeText, '2.6').split('\n')) {
    const row = CLASS_ROW.exec(line)
    if (!row) continue
    if (row[1].toLowerCase() === 'total') continue
    counts.set(row[1], Number(row[2]))
  }
  if (counts.size === 0) {
    throw new Error('§2.6 prints no licence class row — the read found nothing')
  }
  return counts
}

/** The non-permissive licence families a piece of text names. */
export function licenceFamilies(text) {
  const families = new Set()
  const pattern = /\b(?:CC-BY|LGPL|AGPL|MPL|GPL|CDDL|EPL)(?:[-.]?[\d.]+)?/g
  for (const match of text.matchAll(pattern)) {
    families.add(/^(?:CC-BY|LGPL|AGPL|MPL|GPL|CDDL|EPL)/.exec(match[0])[0])
  }
  return families
}

/** The sentences of NOTICE that assert the absence of copyleft. */
export function absenceClaims(noticeText) {
  return noticeText
    .split(/(?<=[.!?])\s+/)
    .filter((sentence) => ABSENCE_CLAIM.test(sentence))
}

/**
 * The scope table's counts against what the lockfiles measure.
 *
 * Both sides are read through the readers the file's own reproduction
 * commands name, so a figure cannot drift without one of the two moving.
 */
export function scopeCountProblems(noticeText, shellKeys, webKeys) {
  const rows = scopeRows(noticeText)
  const problems = []
  const shell = rows.find((row) => row.surface === 'shell npm tree')
  const web = rows.find((row) => row.surface === 'web npm tree')
  const installer = rows.find((row) => row.surface === 'installer-distributed binaries')
  if (!shell) problems.push('§0.1 names no shell npm tree row')
  else if (shell.items !== shellKeys.packages_keys) {
    problems.push(
      `§0.1's shell row says ${shell.items}; shell/pnpm-lock.yaml pins ${shellKeys.packages_keys}`,
    )
  }
  if (!web) problems.push('§0.1 names no web npm tree row')
  else if (web.items !== webKeys.packages_keys) {
    problems.push(
      `§0.1's web row says ${web.items}; web/pnpm-lock.yaml pins ${webKeys.packages_keys}`,
    )
  }
  const binaries = installerBinaries(noticeText)
  if (!installer) problems.push('§0.1 names no installer-distributed binaries row')
  else if (installer.items !== binaries.length) {
    problems.push(
      `§0.1's installer row says ${installer.items}; §2.5 names ${binaries.length} binaries`,
    )
  }
  return problems
}

/**
 * The scope table's copyleft column against what the sections record.
 *
 * The terms are read from the *data* the sections record, not from their
 * prose: §2.5's terms are the licence each binary block carries, and §2.6's
 * are the licence classes its table prints. A sentence in §2.6 that says no
 * GPL-family identifier appears is a statement about an absence, and reading
 * it as a term the section records would invert it.
 *
 * The table may be *wider* than the sections — saying more than is there is a
 * different error. What must never happen is the table being narrower: a
 * distribution that ships LGPL-2.1 and is described as shipping no copyleft.
 */
export function copyleftColumnProblems(noticeText) {
  const problems = []
  const rows = scopeRows(noticeText)
  const rowFor = (section) => rows.find((row) => row.measuredIn === section)

  const installerTerms = new Set()
  for (const binary of installerBinaries(noticeText)) {
    for (const family of licenceFamilies(binary.fields.licence ?? '')) {
      installerTerms.add(family)
    }
  }
  const webTerms = new Set()
  for (const licence of webClassCounts(noticeText).keys()) {
    for (const family of licenceFamilies(licence)) webTerms.add(family)
  }

  for (const [section, terms] of [
    ['§2.5', installerTerms],
    ['§2.6', webTerms],
  ]) {
    const row = rowFor(section)
    if (!row) {
      problems.push(`§0.1 names no row measured in ${section}`)
      continue
    }
    for (const term of terms) {
      if (!row.copyleft.includes(term)) {
        problems.push(
          `${section} records ${term}; §0.1's ${row.surface} row says "${row.copyleft}"`,
        )
      }
    }
  }

  const shell = rows.find((row) => row.surface === 'shell npm tree')
  if (shell && shell.copyleft !== 'none') {
    problems.push(
      `§0.1's shell row says "${shell.copyleft}"; §2.4 measures no copyleft among the 268`,
    )
  }
  const python = rows.find((row) => row.surface === 'python dependency closure')
  if (python && python.copyleft === 'none') {
    problems.push(
      '§0.1\'s python row says none; §2.3 records MPL-2.0 and an LGPL notice in the closure',
    )
  }
  for (const [surface, terms] of Object.entries(SURFACES)) {
    const row = rows.find((candidate) => candidate.surface === surface)
    if (!row) continue
    for (const term of terms) {
      const present = term === 'none' ? row.copyleft === 'none' : row.copyleft.includes(term)
      if (!present) {
        problems.push(
          `§0.1's ${surface} row says "${row.copyleft}"; it must name ${term}`,
        )
      }
    }
  }
  return problems
}

/** The sentences that assert an absence of copyleft without naming a surface. */
export function unscopedAbsenceClaims(noticeText) {
  return absenceClaims(noticeText).filter(
    (sentence) => !SCOPE_WORDS.some((word) => word.test(sentence)),
  )
}

/** §2.6's class table against the lock-key denominator it claims. */
export function webClassProblems(noticeText, webKeys) {
  const counts = webClassCounts(noticeText)
  const total = [...counts.values()].reduce((sum, count) => sum + count, 0)
  const problems = []
  if (total !== webKeys.packages_keys) {
    problems.push(
      `§2.6's licence classes add up to ${total}; web/pnpm-lock.yaml pins ${webKeys.packages_keys} keys`,
    )
  }
  return problems
}

/** What §2.5 records about each binary it names. */
export function binaryLicenceProblems(noticeText) {
  const problems = []
  const binaries = installerBinaries(noticeText)
  for (const binary of binaries) {
    if (!binary.fields.licence) {
      problems.push(`§2.5 names ${binary.name} but records no licence for it`)
    }
    if (!/^[0-9a-f]{64}$/.test(binary.fields.sha256 ?? '')) {
      problems.push(`§2.5 names ${binary.name} but records no sha256 for it`)
    }
  }
  const lgpl = binaries.filter((binary) => (binary.fields.licence ?? '').startsWith('LGPL'))
  if (lgpl.length !== 2) {
    problems.push(`§2.5 records ${lgpl.length} LGPL binaries; two of the eight are LGPL-2.1`)
  }
  return problems
}

test('the scope table names every surface a LabCairn distribution carries', () => {
  const rows = scopeRows(NOTICE_TEXT)
  const named = rows.map((row) => row.surface)
  for (const surface of Object.keys(SURFACES)) {
    assert.ok(
      named.includes(surface),
      `§0.1 names no ${surface} row; it names ${named.join(', ')}`,
    )
  }
  assert.equal(
    named.length,
    Object.keys(SURFACES).length,
    `§0.1 names ${named.length} surfaces; the record names ${Object.keys(SURFACES).length}: ${named.join(', ')}`,
  )
})

test('the scope table counts are what the artefacts it names measure', () => {
  const shellKeys = lockfileKeys(SHELL_LOCK)
  const webKeys = webLockKeys(WEB_LOCK)
  const problems = scopeCountProblems(NOTICE_TEXT, shellKeys, webKeys)
  assert.deepEqual(problems, [], problems.join('; '))
})

test('the scope table copyleft column is not narrower than what the file records', () => {
  const problems = copyleftColumnProblems(NOTICE_TEXT)
  assert.deepEqual(problems, [], problems.join('; '))
})

test('no sentence asserts the absence of copyleft without naming a surface', () => {
  const claims = unscopedAbsenceClaims(NOTICE_TEXT)
  assert.deepEqual(
    claims,
    [],
    `these sentences say that something is not copyleft without naming which surface they are about: ${claims.join(' | ')}`,
  )
})

test("§2.6's licence classes add up to the lock keys they cover", () => {
  const webKeys = webLockKeys(WEB_LOCK)
  const problems = webClassProblems(NOTICE_TEXT, webKeys)
  assert.deepEqual(problems, [], problems.join('; '))
})

test('every binary §2.5 names carries a licence and a hash', () => {
  const problems = binaryLicenceProblems(NOTICE_TEXT)
  assert.deepEqual(problems, [], problems.join('; '))
})

test('the controls fail for the properties they guard', () => {
  const shellKeys = lockfileKeys(SHELL_LOCK)
  const webKeys = webLockKeys(WEB_LOCK)

  // A drifted count in the scope table.
  const drifted = NOTICE_TEXT.replace(
    /^ {2}web npm tree {2,}266 /m,
    '  web npm tree                       260 ',
  )
  assert.notEqual(drifted, NOTICE_TEXT, 'the control did not change the file')
  assert.ok(
    scopeCountProblems(drifted, shellKeys, webKeys).length > 0,
    'a drifted web count did not redden the scope count check',
  )

  // A scope table that says "none" where the sections record copyleft.
  const narrowed = NOTICE_TEXT.replace(
    /^ {2}installer-distributed binaries {2,}8 {2,}LGPL-2\.1/m,
    '  installer-distributed binaries        8  none                ',
  )
  assert.notEqual(narrowed, NOTICE_TEXT, 'the control did not change the file')
  assert.ok(
    copyleftColumnProblems(narrowed).length > 0,
    'a narrowed copyleft column did not redden the copyleft column check',
  )

  // The old blanket claim, put back.
  const blanket = NOTICE_TEXT.replace(
    "**No package among the shell tree's 268 is copyleft.**",
    'Nothing in either tree is copyleft.',
  )
  assert.notEqual(blanket, NOTICE_TEXT, 'the control did not change the file')
  assert.ok(
    unscopedAbsenceClaims(blanket).length > 0,
    'the blanket claim did not redden the absence claim check',
  )

  // A drifted class count in §2.6.
  const driftedClass = NOTICE_TEXT.replace(/^ {2}MIT {2,}207$/m, '  MIT               200')
  assert.notEqual(driftedClass, NOTICE_TEXT, 'the control did not change the file')
  assert.ok(
    webClassProblems(driftedClass, webKeys).length > 0,
    'a drifted licence class count did not redden the class table check',
  )

  // A binary whose licence line is gone.
  const stripped = NOTICE_TEXT.replace(/^ {4}licence {2,}LGPL-2\.1-or-later$/m, '')
  assert.notEqual(stripped, NOTICE_TEXT, 'the control did not change the file')
  assert.ok(
    binaryLicenceProblems(stripped).length > 0,
    'a binary without a licence line did not redden the binary licence check',
  )
})
