/**
 * NOTICE read as data, shared by the four distribution-surface witnesses.
 *
 * **Why this file exists.** NOTICE's §0.1 table names four surfaces a LabCairn
 * distribution carries, and each has its own section recording what travels
 * under what terms: §2.2/§2.3 the python closure, §2.4 the shell's npm tree,
 * §2.5 the installer's binaries, §2.6 the web tree. Each of those sections is a
 * table with a shape, and four witnesses have to read those shapes. A pattern
 * written out four times is four chances to read the table wrongly, and a read
 * that silently matches nothing reports "no problems found".
 *
 * **This is not a second copy of the existing readers.** `notice-licences.test.mjs`
 * and `notice-scope.test.mjs` keep their own readers: they are the pieces those
 * witnesses mutate through to show that they fail for the property, and moving
 * their patterns here would put the mutation controls of a landed witness on top
 * of a new file's changes. What is shared here is the reading the *new*
 * witnesses need against the *artefacts* — the rows, counts and per-binary
 * records they compare against a lock, an installed tree, a bundle or an
 * installed distribution.
 *
 * Every function here throws rather than returning an empty result when the
 * section it names is not present or holds nothing: a reader that finds nothing
 * in a section that exists is the failure mode `CLAUDE.md` calls the dangerous
 * kind, because the witness above it then reports clean.
 */

import fs from 'node:fs'
import path from 'node:path'

export const NOTICE_PATH = path.resolve(import.meta.dirname, '..', 'NOTICE')

/** A numbered heading at column zero, with a title after two spaces. */
const HEADING = /^\d+(\.\d+)*\.?  \S/
/** `  StdUtils.dll — 102,400 bytes` — one §2.5 binary block heading. */
const BINARY_HEADING = /^ {2}([A-Za-z0-9_.-]+\.(?:dll|exe)) — ([\d,]+) bytes$/
/** `    sha256   b72e9013…` — one field of a §2.5 binary block. */
const BINARY_FIELD = /^ {4}(path|sha256|bundle|licence|holder|where)\s{2,}(\S.*)$/
/** A wrapped §2.5 field value's continuation line. */
const BINARY_CONTINUATION = /^ {11}\S/
/** `  MIT               207` — one licence-class row in §2.4.2 or §2.6. */
const CLASS_ROW = /^ {2}(\S.*?\S) {2,}(\d+)$/
/** `  electron  45.2.3  MIT  Copyright …` — one §2.4.1 runtime row. */
const RUNTIME_ROW = /^  (\S+) +(\S+) +(\S+) +Copyright/
/** `  MIT                190` — one §2.4.3 group heading. */
const GROUP_HEADING = /^  (\S.*?) {1,2}\((\d+)\)$/
/** `    @electron/asar@3.4.1` — one §2.4.3 package row. */
const DETAIL_ROW = /^    (\S+)$/
/** `  266  lock keys in the lockfile's packages: section …` — one §2.6 denominator. */
const DENOMINATOR_ROW = /^ {2}(\d+)  (\S.*?)$/
/**
 * The §0.1 surface table row: surface, item count, and the rest of the row.
 *
 * The columns after the count are split on a run of two or more spaces rather
 * than by regex groups, because the terms column can itself hold a section
 * reference: the python row reads
 *
 *     python dependency closure          171  MPL-2.0, LGPL, GPL-3.0       §2.2, §2.3
 *
 * and a pattern that took the last `§` reference as the section and everything
 * before it as the terms swallowed `§2.2,` into the terms column — where a
 * copyleft-column comparison would then read it as a licence term.
 */
const SCOPE_ROW = /^  (\S.*?\S) +(\d+) +(\S.*\S)$/
/**
 * The NSIS distribution's `COPYING` as §2.5 states it.
 *
 * The hash is on the following line and inside backticks in the tree as printed:
 *
 *     `COPYING` (15,488 bytes, sha256
 *     `3c8de989f6504d52f5f8dfafedb6668cd47201f5d01f1319570727c091425dd6`) licenses
 *
 * A pattern that required the hash on the same line matched nothing and the
 * reader threw — which is the loud failure, but a version of it that would have
 * looked like "NOTICE changed its wording" rather than "this reader cannot read
 * the wording it has always had".
 */
const COPYING_CLAIM = /`COPYING` \(([\d,]+) bytes, sha256\s+`?([0-9a-f]{64})`?\)/

export function readNotice(noticePath = NOTICE_PATH) {
  return fs.readFileSync(noticePath, 'utf8')
}

/**
 * One numbered subsection of NOTICE, by its heading.
 *
 * The slice ends at the next *heading* line, not at the next rule of dashes:
 * every heading in this file is underlined by one, so treating the underline as
 * the boundary ends the slice after the heading and its underline, and the reads
 * below would then find no table in it.
 */
export function noticeSubsection(noticeText, heading) {
  const lines = noticeText.split('\n')
  const start = lines.findIndex((line) => line.startsWith(`${heading}  `))
  if (start < 0) throw new Error(`NOTICE has no subsection ${heading}`)
  let end = lines.length
  for (let index = start + 1; index < lines.length; index += 1) {
    if (HEADING.test(lines[index])) {
      end = index
      break
    }
  }
  return lines.slice(start, end)
}

/** The §0.1 surface table: `{ surface, items, terms, sections }`, in the order printed. */
export function scopeTable(noticeText) {
  const rows = []
  for (const line of noticeSubsection(noticeText, '0.1')) {
    const match = SCOPE_ROW.exec(line)
    if (!match) continue
    const columns = match[3].split(/\s{2,}/)
    if (columns.length < 2) continue
    const sections = columns.pop()
    rows.push({
      surface: match[1],
      items: Number(match[2]),
      terms: columns.join(' '),
      sections,
    })
  }
  if (rows.length === 0) throw new Error('§0.1 prints no surface row — the read found nothing')
  return rows
}

/** The eight §2.5 binary records, each with all six fields, wrapped values joined. */
export function binaryRecords(noticeText) {
  const binaries = []
  let current = null
  let lastField = null
  for (const line of noticeSubsection(noticeText, '2.5')) {
    const heading = BINARY_HEADING.exec(line)
    if (heading) {
      current = { name: heading[1], bytes: Number(heading[2].replace(/,/g, '')), fields: {} }
      binaries.push(current)
      lastField = null
      continue
    }
    if (!current) continue
    const field = BINARY_FIELD.exec(line)
    if (field) {
      current.fields[field[1]] = field[2].trim()
      lastField = field[1]
      continue
    }
    if (BINARY_CONTINUATION.test(line) && lastField) {
      current.fields[lastField] += ' ' + line.trim()
      continue
    }
    lastField = null
  }
  if (binaries.length === 0) throw new Error('§2.5 names no binary — the read found nothing')
  return binaries
}

/** The sha256 and byte count §2.5 states for the NSIS distribution's `COPYING`. */
export function copyingClaim(noticeText) {
  const match = COPYING_CLAIM.exec(noticeText)
  if (!match) {
    throw new Error(
      '§2.5 states no sha256 for the NSIS distribution`s COPYING — the read found nothing',
    )
  }
  return { bytes: Number(match[1].replace(/,/g, '')), sha256: match[2] }
}

/**
 * A licence-class table: identifier → count.
 *
 * A `Total` row is dropped where present: it is the sum of the rows above it,
 * and counting it would make the total twice what the table claims.
 */
export function licenceClassTable(noticeText, heading) {
  const counts = new Map()
  for (const line of noticeSubsection(noticeText, heading)) {
    const row = CLASS_ROW.exec(line)
    if (!row) continue
    if (/^(total|keys)$/i.test(row[1])) continue
    counts.set(row[1], Number(row[2]))
  }
  if (counts.size === 0) throw new Error(`${heading} prints no licence-class row — the read found nothing`)
  return counts
}

/** §2.4.1's thirteen runtime rows: `name@version → { licence, version, name }`. */
export function runtimeRows(noticeText) {
  const rows = new Map()
  for (const line of noticeSubsection(noticeText, '2.4.1')) {
    const match = RUNTIME_ROW.exec(line)
    if (match) rows.set(`${match[1]}@${match[2]}`, { name: match[1], version: match[2], licence: match[3] })
  }
  if (rows.size === 0) throw new Error('§2.4.1 names no package — the read found nothing')
  return rows
}

/** §2.4.3's groups: licence class → the `name@version` rows listed under it. */
export function buildGroups(noticeText) {
  const groups = new Map()
  let current = null
  for (const line of noticeSubsection(noticeText, '2.4.3')) {
    const heading = GROUP_HEADING.exec(line)
    if (heading) {
      current = heading[1].trim()
      if (!groups.has(current)) groups.set(current, [])
      continue
    }
    const detail = DETAIL_ROW.exec(line)
    if (detail && current) groups.get(current).push(detail[1])
  }
  if (groups.size === 0) throw new Error('§2.4.3 lists no licence group — the read found nothing')
  return groups
}

/**
 * §2.6's denominators, as the section states them.
 *
 * `266 lock keys`, `241 distinct name@version installed`, `624 package.json
 * records`: three different numbers that are all true, and a witness that
 * compared only one of them would let the other two drift. Each is keyed by the
 * phrase the row prints, with the markup stripped and the sentence's tail cut at
 * the clause boundary — the row reads
 *
 *     624  `package.json` records in that install — a peer variant installs the
 *
 * so a key that kept the backticks would match only while the file keeps its
 * formatting, which is not the number being watched. The key is still the
 * row's own words, so renaming a denominator reddens it instead of dropping it
 * out of the comparison.
 */
export function webDenominators(noticeText) {
  const found = new Map()
  for (const line of noticeSubsection(noticeText, '2.6')) {
    const row = DENOMINATOR_ROW.exec(line)
    if (!row) continue
    const phrase = row[2].replace(/`/g, '').split(/[—-] /)[0].trim()
    if (!phrase) continue
    if (!found.has(phrase)) found.set(phrase, Number(row[1]))
  }
  if (found.size === 0) throw new Error('§2.6 prints no denominator row — the read found nothing')
  return found
}

/**
 * §2.6's non-permissive entries: the family, the count it states, and the keys.
 *
 * The section lists them as bullets —
 *
 *     * **MPL-2.0 — 12 of the 266 keys.** The `lightningcss@1.33.0` family:
 *       `lightningcss@1.33.0` itself, `lightningcss-win32-x64-msvc@1.33.0`, and
 *       ten further platform variants — `-android-arm64`, … `-win32-arm64-msvc`.
 *     * **CC-BY-4.0 — 1 of the 266 keys.** `caniuse-lite@1.0.30001816`, …
 *
 * — and the platform variants are named as *suffixes* on the base package rather
 * than as lock keys. Both forms are returned separately, because the witness has
 * to expand the suffixes against the lock's own keys to know what the entry
 * claims: the count is a claim about keys, and a read that collected only the
 * two explicit keys would report the entry as naming 2 of 266 and then "prove"
 * the entry is wrong.
 */
export function nonPermissiveEntries(noticeText, heading) {
  const section = noticeSubsection(noticeText, heading)
  const BULLET = /^ {2}\* \*\*([A-Za-z0-9.+-]+) [\xc2\xa7—-] (\d+) of\b/
  const ENTRIES = []
  let current = null
  for (const line of section) {
    const bullet = BULLET.exec(line)
    if (bullet) {
      current = { family: bullet[1], count: Number(bullet[2]), explicit: [], suffixes: [] }
      ENTRIES.push(current)
    }
    // Not `continue`: the CC-BY entry's only key sits on the bullet line itself
    // (`* **CC-BY-4.0 — 1 of the 266 keys.** \`caniuse-lite@1.0.30001816\`, which`),
    // and skipping the bullet line collected no key for it.
    if (!current) continue
    // A blank line ends the entry's paragraph. Without that boundary the last
    // bullet's body runs on into the prose below it, and §2.6's next paragraph
    // names `@license`, `@preserve` and `@copyright` — strings that look like
    // package references to a backtick collector and are not.
    if (line.trim() === '') {
      current = null
      continue
    }
    for (const token of line.matchAll(/`([^`]+)`/g)) {
      const value = token[1]
      if (/^-[A-Za-z0-9-]+$/.test(value)) {
        current.suffixes.push(value)
        continue
      }
      // A `name@version`: something before the last `@`, and a version after it.
      // `@license` fails this, and so does a bare package name with no version.
      const at = value.lastIndexOf('@')
      if (at > 0 && /^\d/.test(value.slice(at + 1))) current.explicit.push(value)
    }
  }
  if (ENTRIES.length === 0) {
    throw new Error(`${heading} names no non-permissive entry — the read found nothing`)
  }
  return ENTRIES
}

/**
 * The keys a §2.6 entry claims, with its suffix variants expanded against the lock.
 *
 * A suffix entry expands onto the base package's name and version: `-linux-x64-gnu`
 * on the base `lightningcss@1.33.0` is the key `lightningcss-linux-x64-gnu@1.33.0`.
 * A suffix that matches no lock key is returned in `unmatched` rather than
 * dropped — an entry naming a variant the lock stopped pinning is a record that
 * went stale, and dropping it would hide that.
 */
export function entryClaimedKeys(entry, lockKeys) {
  const base = entry.explicit.find((key) => !entry.suffixes.some((suffix) => key.includes(suffix)))
  const problems = []
  if (!base) problems.push('the entry names no base package to expand its suffixes onto')
  const [baseName, baseVersion] = base ? [base.slice(0, base.lastIndexOf('@')), base.slice(base.lastIndexOf('@') + 1)] : ['', '']
  const claimed = new Set(entry.explicit)
  const unmatched = []
  for (const suffix of entry.suffixes) {
    const expanded = `${baseName}${suffix}@${baseVersion}`
    if (!lockKeys.includes(expanded)) {
      unmatched.push(expanded)
      continue
    }
    claimed.add(expanded)
  }
  const notInLock = [...claimed].filter((key) => !lockKeys.includes(key))
  return { claimed: [...claimed].sort(), unmatched, notInLock, problems }
}

/** The §2.6 sentence claiming the lock carries no licence field, with the count it states. */
export function lockLicenceFieldClaim(noticeText) {
  const section = noticeSubsection(noticeText, '2.6').join('\n')
  const match = /substring `licen` occurs \*\*(\d+)\*\* times in `web\/pnpm-lock\.yaml`/.exec(section)
  if (!match) {
    throw new Error(
      '§2.6 states no count for the `licen` occurrences in web/pnpm-lock.yaml — the read found nothing',
    )
  }
  return Number(match[1])
}

/**
 * The §2.2 closure counts: the total and each platform figure, as printed.
 *
 * The section prints them in prose — "resolves 171 requirement lines across
 * platforms: 167 on Linux, 165 on macOS, 168 on Windows" and "Their union is
 * 170" — so the read names each figure by the word that identifies it and
 * fails when one of those five is missing rather than comparing an incomplete
 * set.
 */
export function closureCounts(noticeText) {
  const section = noticeSubsection(noticeText, '2.2').join(' ')
  const wanted = [
    { key: 'total', pattern: /resolves (\d+) requirement lines/ },
    { key: 'linux', pattern: /(\d+) on Linux/ },
    { key: 'macos', pattern: /(\d+) on macOS/ },
    { key: 'windows', pattern: /(\d+) on Windows/ },
    { key: 'union', pattern: /union is (\d+)/ },
  ]
  const counts = {}
  const missing = []
  for (const { key, pattern } of wanted) {
    const match = pattern.exec(section)
    if (match) counts[key] = Number(match[1])
    else missing.push(key)
  }
  if (missing.length) throw new Error(`§2.2 prints no closure count for: ${missing.join(', ')}`)
  return counts
}

/**
 * §2.3's entries: the package name, the version the section names, and the
 * distribution-relative licence file paths it names.
 *
 * The paths are what the section states literally
 * (`numpy-2.5.4.dist-info/licenses/LICENSE.txt`,
 * `pywin32-312.dist-info/licenses/adodbapi/license.txt`, …) and they are what a
 * witness can open. A version is taken from the entry's own text
 * (`numpy 2.5.4`, `Pillow 13.0.0`, `pywin32 312`), because the claim "this file
 * is there" is only a claim when it is about a named version.
 */
export function bundledLicenceEntries(noticeText) {
  const section = noticeSubsection(noticeText, '2.3').join('\n')
  const entries = []
  const bulletStarts = [...section.matchAll(/^ {2}\* (.*)$/gm)]
  for (let index = 0; index < bulletStarts.length; index += 1) {
    const start = bulletStarts[index].index
    const end = index + 1 < bulletStarts.length ? bulletStarts[index + 1].index : section.length
    const body = section.slice(start, end)
    const name = /\b([A-Za-z][A-Za-z0-9_.-]*) (\d[\w.-]*)\b/.exec(body)
    const paths = [...body.matchAll(/([A-Za-z0-9_.-]+\.dist-info\/[A-Za-z0-9_./-]+)/g)].map((m) => m[1])
    const licenceFamily = /^ {2}\* ([A-Z][A-Za-z0-9.+-]*)/.exec(body)?.[1] ?? null
    entries.push({
      opening: bulletStarts[index][1].slice(0, 60),
      package: name ? name[1] : null,
      version: name ? name[2] : null,
      licenceFamily,
      paths,
      text: body,
    })
  }
  if (entries.length === 0) throw new Error('§2.3 names no entry — the read found nothing')
  return entries
}
