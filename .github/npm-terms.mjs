/**
 * The terms a pinned npm tree travels under, read from what carries them.
 *
 * **Why this file exists.** A pnpm lockfileVersion 9 file pins identity and
 * never terms: the case-insensitive substring `licen` occurs **0** times in
 * `web/pnpm-lock.yaml` and 0 times in `shell/pnpm-lock.yaml` (measured at this
 * tree, and stated in NOTICE §2.4 and §2.6). So the claims "no package among the
 * shell tree's 268 is copyleft" and "MPL-2.0 — 12 of the 266 keys" cannot be
 * checked against the lock. They have to be checked against something that
 * carries terms, and there are exactly two: the published registry record for the
 * pinned `name@version`, and the installed `package.json` of that same pinned
 * version.
 *
 * **Why the registry is the source the gate can use.** `shell.yml` installs no
 * `node_modules` — `tests/test_shell_ci.py::test_the_test_step_runs_inside_the_shell_and_names_the_runner_temp`
 * refuses a `pnpm install` step there — so on the runner the installed tree does
 * not exist, while the registry does. The abbreviated packument is not used
 * because it carries **no** `license` field per version (measured: `undefined`
 * for react, vite, lightningcss-win32-x64-msvc, caniuse-lite), and a whole
 * packument of react is a ~3 MB document for one field. The version-scoped
 * packument answers one question per request.
 *
 * **Why the integrity field is part of the read.** `packages:` names each key
 * with a `sha512` integrity. The registry's `dist.integrity` for that
 * `name@version` is the hash of the same archive. Comparing them is what makes
 * "the licence I read is the licence of the bytes this lock pins" a statement
 * rather than a hope — and it is the check that keeps a registry read from being
 * a read of *whatever the registry says today* about a name.
 *
 * **Where the installed tree fits.** It is the second reader, and the agreement
 * between the two is itself a watched property: a package whose published record
 * and installed declaration state different terms is a real disagreement about
 * what travels, whichever side NOTICE happens to agree with.
 *
 * **The comparisons are functions that take data.** A witness that compares the
 * artefacts it opened inside its own test body cannot be shown to fail for the
 * property: the only way to hand it a broken value is to break the artefact. Each
 * `*Problems` function here takes what NOTICE states and what the sources present,
 * and answers with the problems. The witness feeds them real bytes; the controls
 * feed them records with one value changed. Same code both ways —
 * `shell/test/dependency-surface.test.mjs`'s precedent.
 *
 * **The terms vocabulary is here, not in each witness.** `COPYLEFT`,
 * `ATTRIBUTION` and `UNRESOLVED_TERMS` are the three families the witnesses ask
 * about. A witness carrying its own copy of a vocabulary can be widened in one
 * file while another stays narrow.
 */

import fs from 'node:fs'
import path from 'node:path'

import { bareKey } from './shell-lockfile-keys.mjs'

/** Copyleft terms: a distributor of a covered file or covered library owes something. */
export const COPYLEFT = /\b(?:AGPL|LGPL|GNU GPL|GPL-\d|GPLv\d|CPAL|QPL|EUPL|MPL|CDDL|EPL|SSPL)\b/i

/** Terms that ask for credit rather than source (§2.6's CC-BY-4.0 is one). */
export const ATTRIBUTION = /\bCC-BY\b/i

/** A licence the publisher did not name: npm's own vocabulary for that. */
export const UNRESOLVED_TERMS = /\b(?:UNLICENSED|SEE LICENSE IN)\b/i

/** `name@version` → `{ name, version }`, splitting where the version's `@` is. */
export function splitKey(key) {
  const at = key.lastIndexOf('@')
  if (at <= 0) throw new Error(`not a name@version key: ${key}`)
  return { name: key.slice(0, at), version: key.slice(at + 1) }
}

/**
 * The published record of each pinned key's terms, concurrently.
 *
 * One request per key against the version-scoped packument. Measured on this
 * machine at the current web lock: 266 keys answered 266/266 in 69.2 s serially,
 * which is why the fan-out exists — a witness that reads terms for both trees
 * (534 keys) should take seconds, not two minutes.
 *
 * A key the registry will not answer lands in `failures` rather than being
 * dropped: a census built over a partial answer would print a licence table for
 * a tree it only partly read, which is the shape of a green that means nothing.
 */
export async function registryTerms(entries, { concurrency = 24, fetchImpl = globalThis.fetch, attempts = 4, wait = defaultWait } = {}) {
  const terms = new Map()
  const failures = []
  const queue = [...entries]

  async function worker() {
    for (;;) {
      const entry = queue.shift()
      if (entry === undefined) return
      const key = bareKey(entry)
      const { name, version } = splitKey(key)
      const url = `https://registry.npmjs.org/${encodeURIComponent(name)}/${encodeURIComponent(version)}`

      // A registry that answers 429 is not a registry that says the package does
      // not exist, and a witness that reports the second about the first reddens
      // for a reason that has nothing to do with the licence under watch — measured
      // here, where two witnesses run 534 keys between them and one key came back
      // unanswered at 24-way concurrency and answered 200 when fetched alone.
      // Transport failures and 429/5xx answers are retried with a backoff; a 404 is
      // an answer about the package, and it is reported as one.
      const outcome = await readRecord(url, { attempts, wait, fetchImpl })
      if (outcome.ok) {
        const record = outcome.record
        terms.set(key, {
          key,
          name,
          version,
          licence: typeof record?.license === 'string' ? record.license : null,
          licenceText: typeof record?.licenseText === 'string' ? record.licenseText : null,
          licenceFile: typeof record?.licenseFilename === 'string' ? record.licenseFilename : null,
          integrity: record?.dist?.integrity ?? null,
        })
      } else {
        failures.push({ key, reason: outcome.reason })
      }
    }
  }

  const workers = Math.max(1, Math.min(concurrency, Math.max(1, queue.length)))
  await Promise.all(Array.from({ length: workers }, worker))
  return { terms, failures }
}

/**
 * One key's published record, retried on a transport failure or a throttled answer.
 *
 * Exported because the retry policy is itself a thing that can be neutered: a
 * witness that gives up on the first 429 and a witness that never retries are the
 * same green-to-red mistake in opposite directions, and the only way to tell them
 * apart is to hand each answer to the code that has to decide what it means.
 */
export async function readRecord(url, { attempts = 4, wait = defaultWait, fetchImpl = globalThis.fetch } = {}) {
  let lastReason = 'no attempt was made'
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetchImpl(url)
      if (response.status === 404) return { ok: false, reason: 'the registry has no record of this name@version (404)' }
      if (!response.ok) throw new Error(`registry answered ${response.status}`)
      return { ok: true, record: await response.json() }
    } catch (error) {
      lastReason = String(error?.message ?? error)
      if (attempt < attempts) await wait(retryDelay(attempt, error))
    }
  }
  return { ok: false, reason: `${lastReason} (after ${attempts} attempts)` }
}

/** `Retry-After` if the answer carries one, otherwise an exponential backoff. */
export function retryDelay(attempt, response) {
  const seconds = Number(response?.headers?.get?.('retry-after'))
  if (Number.isFinite(seconds) && seconds > 0) return Math.min(seconds * 1000, 20_000)
  return Math.min(500 * 2 ** (attempt - 1), 20_000)
}

function defaultWait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * The `sha512` integrity the lock itself records for each key.
 *
 * Read straight out of the lock text rather than re-derived: the claim being
 * checked is the lock's own, and a reader that recomputes the value it compares
 * against cannot be wrong in the way the check cares about.
 */
export function lockIntegrities(lockText) {
  const integrity = new Map()
  let current = null
  for (const line of lockText.split('\n')) {
    const key = /^ {2}'?([^'"\s][^:]*?)'?:\s*(?:\{.*)?$/.exec(line)
    if (key) {
      // A `packages:` key is a `name@version`; the `importers:` section's root
      // entry is the single character `.`, and a peer-suffixed key needs
      // `bareKey` to become one. A line naming neither is not a package and
      // carries nothing this reader cares about.
      try {
        current = bareKey(key[1])
      } catch {
        current = null
      }
    }
    if (current === null) continue
    const value = /\bintegrity: (sha512-[^',}]+)/.exec(line)
    if (value) integrity.set(current, value[1])
  }
  return integrity
}

/**
 * The published terms for a lock, bound to the lock's own integrity for each key.
 *
 * `bound` is the set of keys whose lock `sha512` is the registry's `sha512` for
 * those bytes; `bytesDisagree` is everything else — a lock whose integrity the
 * registry does not confirm, or a registry record that states no integrity at
 * all. A licence read about an unconfirmed archive is a licence read about
 * something other than what this lock pins, so the terms map only carries keys
 * that are bound, and the rest are reported.
 */
export async function lockTerms(lockText, entries, options = {}) {
  const registry = await registryTerms(entries, options)
  const lock = lockIntegrities(lockText)
  const terms = new Map()
  const bytesDisagree = []
  for (const [key, record] of registry.terms) {
    const pinned = lock.get(key)
    if (!pinned) {
      bytesDisagree.push({ key, reason: 'the lock records no integrity for this key' })
      continue
    }
    if (!record.integrity) {
      bytesDisagree.push({ key, reason: 'the registry record carries no integrity' })
      continue
    }
    if (pinned !== record.integrity) {
      bytesDisagree.push({
        key,
        reason: `lock ${pinned.slice(0, 20)}… is not the registry's ${record.integrity.slice(0, 20)}…`,
      })
      continue
    }
    terms.set(key, record)
  }
  return { terms, failures: registry.failures, bytesDisagree, bound: terms.size }
}

/** The installed tree's declared terms for the same keys. */
export function installedTerms(lockText, storeDir, { readRecords, resolveInstalled }) {
  if (!fs.existsSync(storeDir)) return { available: false, storeDir, terms: new Map(), records: 0 }
  const records = readRecords(storeDir)
  const resolved = resolveInstalled(lockText, records)
  return {
    available: true,
    storeDir,
    records: records.length,
    distinct: new Set(records.map((record) => `${record.name}@${record.version}`)).size,
    terms: new Map(resolved.licences),
    unanswered: resolved.unresolved,
  }
}

/** The licence classes over a terms map, most common first. */
export function classTable(terms) {
  const counts = new Map()
  for (const record of terms.values()) {
    const key = record.licence ?? '(none declared)'
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return new Map([...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])))
}

/** The keys whose terms fall in a family. */
export function keysInFamily(terms, pattern) {
  return [...terms.entries()]
    .filter(([, record]) => pattern.test(record.licence ?? ''))
    .map(([key]) => key)
    .sort()
}

/**
 * A licence-class table against the classes actually computed, both directions.
 *
 * A class the computation finds that the table omits, a count that disagrees, and
 * a class the table prints that nothing produced are three different defects and
 * all three are reported. Checking only "the table adds up to the total" lets a
 * copyleft class move into a permissive row while the total stays right.
 */
export function classTableProblems(recorded, computed) {
  const problems = []
  for (const [licence, count] of recorded) {
    const actual = computed.get(licence)
    if (actual === undefined) {
      problems.push(`the record names ${count} ${licence} but nothing in the tree declares that licence`)
      continue
    }
    if (actual !== count) {
      problems.push(`the record names ${count} ${licence}; ${actual} declare it`)
    }
  }
  for (const [licence, count] of computed) {
    if (!recorded.has(licence)) {
      problems.push(`${count} packages declare ${licence}, which the record names no row for`)
    }
  }
  const recordedTotal = [...recorded.values()].reduce((sum, value) => sum + value, 0)
  const computedTotal = [...computed.values()].reduce((sum, value) => sum + value, 0)
  if (recordedTotal !== computedTotal) {
    problems.push(`the record's class rows add to ${recordedTotal}; the tree presents ${computedTotal}`)
  }
  return problems
}

/**
 * A named package list against the keys that actually carry that family.
 *
 * Both directions, because the defect has two shapes: a family that gains a
 * member the record does not name, and a record that names a package whose terms
 * have moved. The names are compared as `name@version`, which is what both sides
 * state.
 */
export function familyListProblems(family, computedKeys, recordedKeys) {
  const problems = []
  const computedSet = new Set(computedKeys)
  const recordedSet = new Set(recordedKeys)
  for (const key of [...computedSet].filter((key) => !recordedSet.has(key)).sort()) {
    problems.push(`${key} is under ${family} in the tree, and the record names no ${family} entry for it`)
  }
  for (const key of [...recordedSet].filter((key) => !computedSet.has(key)).sort()) {
    problems.push(`the record names ${key} as ${family}, and its published terms are not ${family}`)
  }
  return problems
}

/**
 * A licence that is neither permissive nor copyleft: source-available terms.
 *
 * §2.4 and §2.6 both claim none of the tree's packages carries one, and
 * "source-available" is a family a copyleft pattern misses: BUSL, Elastic-2.0
 * and Commons Clause all restrict *offering the software as a service* rather
 * than redistributing source, so they are neither permissive-and-done nor a
 * redistribution obligation.
 */
export const SOURCE_AVAILABLE =
  /\b(?:BUSL-1[.\d]*|BSL-1[.\d]*|Elastic-2\.0|Server Side Public|SSPL|Commons Clause|CommonsClause|Fair-?Source|Source Available|PolyForm|Business Source)\b/i

/**
 * Every key whose published terms and installed declaration disagree.
 *
 * `published` is a key → record map from `lockTerms`; `installed` is a key →
 * licence-string map from an installed tree. Compared on the declared string as
 * each source states it: the watched claim is "the package this lock pins
 * travels under the terms the record names", and a normalisation applied before
 * comparing hides a real difference behind a spelling.
 */
export function termDisagreements(published, installed) {
  const disagreements = []
  for (const [key, record] of published) {
    if (!installed.has(key)) continue
    const other = installed.get(key) ?? null
    if ((record.licence ?? null) !== (other ?? null)) {
      disagreements.push({ key, published: record.licence ?? null, installed: other ?? null })
    }
  }
  return disagreements.sort((a, b) => a.key.localeCompare(b.key))
}

/** Keys whose terms are copyleft, attribution-conditioned, source-available, or unnamed. */
export function termFamilies(terms) {
  return {
    copyleft: keysInFamily(terms, COPYLEFT),
    attribution: keysInFamily(terms, ATTRIBUTION),
    sourceAvailable: keysInFamily(terms, SOURCE_AVAILABLE),
    unresolved: keysInFamily(terms, UNRESOLVED_TERMS),
  }
}

/**
 * The packages the tree names against the packages the record names, both ways.
 *
 * The per-package half of a licence record: a key present in the tree with no
 * recorded class, and a recorded class for a key the tree no longer names.
 */
export function termsUnrecordedProblems(terms, recorded) {
  const unrecorded = [...terms.keys()].filter((key) => !recorded.has(key)).sort()
  const stale = [...recorded.keys()].filter((key) => !terms.has(key)).sort()
  return [...unrecorded.map((key) => `${key} carries terms no record names`), ...stale.map((key) => `a record names ${key}, which the tree does not name`)]
}

/** The default virtual store for a tree. */
export function storeDirFor(repoRoot, which) {
  return path.join(repoRoot, which, 'node_modules', '.pnpm')
}

/**
 * The lock's `packages:` keys — the coverage denominator both §2.4 and §2.6 use.
 *
 * The two trees are read by the readers that already read them
 * (`.github/web-lockfile-keys.mjs` and `.github/shell-lockfile-keys.mjs`), not by
 * a third parser here: a second copy of the lockfile grammar is a second thing
 * that can stop reading the lock, and the failure would look like a licence that
 * changed.
 */
export function lockCoverageKeys(lockText, { readers }) {
  return readers.packagesEntries(lockText)
}
