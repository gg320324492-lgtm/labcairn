/**
 * NOTICE §2.6, watched against the terms the web tree's packages actually carry.
 *
 * **Why this file exists.** §2.6 prints a licence-class table over the web lock's
 * 266 keys (MIT 207, Apache-2.0 19, **MPL-2.0 12**, ISC 11, BSD-2-Clause 8,
 * BSD-3-Clause 3, MIT-0 2, BlueOak-1.0.0 2, **CC-BY-4.0 1**, CC0-1.0 1), three
 * denominators that are all true and not interchangeable (266 lock keys, 241
 * installed `name@version`, 624 installed `package.json` records), and two named
 * entries — the twelve-key `lightningcss` family and `caniuse-lite@1.0.30001816`.
 * `shell/test/notice-scope.test.mjs` checks that §2.6's class table **adds up to
 * the key count the section claims**: a drifted class count cannot hide inside a
 * correct total. That is a check of the table against itself. Nothing compared
 * any row of it to what the packages declare. A package reclassified from
 * MPL-2.0 to MIT, or a thirteenth MPL variant arriving with the twelve rows
 * unchanged, would keep §2.6 internally consistent, keep `notice-scope.test.mjs`
 * green, and make §2.6 wrong about the distribution.
 *
 * **Where the terms come from.** The lock carries none — §2.6 states the count of
 * `licen` occurrences in `web/pnpm-lock.yaml` as **0**, and this file checks that
 * claim rather than trusting it. So the terms come from the published registry
 * record for each pinned `name@version`, bound to the lock's own `sha512`
 * integrity for the same bytes: measured on this tree, 266/266 keys are bound and
 * the read takes 4.4 s. Where an installed tree is present it is a second reader,
 * and the two agreeing is itself watched — `web.yml` runs `pnpm install
 * --frozen-lockfile` and so has the tree, and the installed-tree figures §2.6
 * prints (241 distinct, 624 records, 25 unanswered keys) are watched there.
 *
 * **What it does not do.** It does not re-check the shell's tree — that is
 * `shell-tree-terms.test.mjs` — and it does not re-implement the reach claims
 * (`lightningcss` under `vite`, `caniuse-lite` under `browserslist`) that
 * `notice-scope.test.mjs`'s `webReachProblems` already watches against the lock's
 * dependency maps.
 */

import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test, { after } from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  entryClaimedKeys,
  licenceClassTable,
  lockLicenceFieldClaim,
  nonPermissiveEntries,
  readNotice,
  webDenominators,
} from '../../.github/notice-readers.mjs'
import {
  classTable,
  classTableProblems,
  COPYLEFT,
  familyListProblems,
  installedTerms,
  keysInFamily,
  lockCoverageKeys,
  lockIntegrities,
  lockTerms,
  SOURCE_AVAILABLE,
  termDisagreements,
  termFamilies,
  UNRESOLVED_TERMS,
} from '../../.github/npm-terms.mjs'
import { installedPackages, resolveFromInstalled, webLockKeys } from '../../.github/web-lockfile-keys.mjs'
import { shellPaths } from '../scripts/lib/shell-paths.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SHELL_ROOT = path.resolve(HERE, '..')
const REPO_ROOT = path.resolve(SHELL_ROOT, '..')
const WEB_ROOT = path.join(REPO_ROOT, 'web')
// The artefact paths, with an override each. The override exists for the mutation
// checks — a witness that can only be shown to fail by mutating a file in the tree
// is a witness whose mutation checks leave the tree dirty — and because §5.4's
// reproduction commands are run against copies outside the checkout.
const WEB_LOCK_PATH = process.env.LABCAIRN_LICENCE_WEB_LOCK ?? path.join(WEB_ROOT, 'pnpm-lock.yaml')
const NOTICE_PATH = process.env.LABCAIRN_LICENCE_NOTICE ?? undefined

const NOTICE_TEXT = readNotice(NOTICE_PATH)
const LOCK_TEXT = fs.readFileSync(WEB_LOCK_PATH, 'utf8')
const COVERAGE_KEYS = lockCoverageKeys(LOCK_TEXT, { readers: { packagesEntries: (text) => webLockKeys(text).packages_entries } })

/**
 * Where an installed web tree could be found: this checkout's, or the tree a
 * worktree was cloned from. `shellPaths` is the resolution the shell's live
 * witnesses already use for exactly this, and `shell.yml` installs none.
 */
function webStoreDir() {
  const candidates = [
    process.env.LABCAIRN_LICENCE_WEB_STORE ?? '',
    path.join(WEB_ROOT, 'node_modules', '.pnpm'),
    path.join(shellPaths({ here: HERE }).checkoutRoot, 'web', 'node_modules', '.pnpm'),
  ].filter((entry) => entry && fs.existsSync(entry))
  return candidates[0] ?? null
}

const RUN_LOG = []

// The log is the point of the sentinel: a reader of the transcript must be
// able to see which arms measured and which could not look, rather than
// seeing only that every case passed.
after(() => {
  for (const entry of RUN_LOG) process.stdout.write(`${entry}\n`)
})
function ran(what) {
  RUN_LOG.push(`RAN ${what}`)
}
function notRun(what, reason) {
  RUN_LOG.push(`NOT RUN ${what}: ${reason}`)
}

/** The published terms, read once for the whole file. */
let published = null
let publishedError = null
async function publishedTerms() {
  if (published === null && publishedError === null) {
    try {
      published = await lockTerms(LOCK_TEXT, COVERAGE_KEYS, { concurrency: 24 })
    } catch (error) {
      publishedError = String(error?.message ?? error)
    }
  }
  if (publishedError !== null) return null
  return published
}

const WEB_INSTALLED = installedTerms(LOCK_TEXT, webStoreDir() ?? '', {
  readRecords: (storeDir) => installedPackages(storeDir),
  resolveInstalled: (text, records) => resolveFromInstalled(webLockKeys(text).packages_entries, records),
})

const PUBLISHED_REASON = 'the npm registry could not be read (published terms come from registry.npmjs.org, which an offline run cannot reach)'

// ---------------------------------------------------------------------------
// 1. The lock carries no licence field — §2.6's own stated count, measured.
// ---------------------------------------------------------------------------
test('§2.6 states how many licence fields the web lock carries, and the lock carries that many', () => {
  const stated = lockLicenceFieldClaim(NOTICE_TEXT)
  const actual = (LOCK_TEXT.match(/licen/gi) ?? []).length
  assert.equal(
    actual,
    stated,
    `§2.6 states the substring \`licen\` occurs ${stated} times in web/pnpm-lock.yaml; it occurs ${actual}. A lock that began carrying licence fields changes where §2.6's terms have to be read from, and the section has to say so`,
  )
  ran('the lock\'s own licence-field count')
})

// ---------------------------------------------------------------------------
// 2. The class table against the terms the packages declare.
// ---------------------------------------------------------------------------
test('§2.6\'s licence classes are the classes the packages in the web tree actually declare', async () => {
  const terms = await publishedTerms()
  if (terms === null) {
    notRun('§2.6\'s class table against the published terms', PUBLISHED_REASON)
    return
  }
  ran('§2.6\'s class table against the published terms')

  assert.equal(
    terms.bytesDisagree.length,
    0,
    `§2.6's terms are read from the published record of each pinned package, and ${terms.bytesDisagree.length} of those records do not match the lock's own integrity: ${terms.bytesDisagree.slice(0, 4).map((f) => `${f.key} ${f.reason}`).join('; ')} — the terms read are not terms of the bytes this lock pins`,
  )
  assert.deepEqual(
    terms.failures,
    [],
    `${terms.failures.length} pinned keys were not answered by the registry (${terms.failures.slice(0, 4).map((f) => f.key).join(', ')}), so the class table below is a census of a tree that was only partly read`,
  )

  const computed = classTable(terms.terms)
  const recorded = licenceClassTable(NOTICE_TEXT, '2.6')
  const problems = classTableProblems(recorded, computed)
  assert.deepEqual(problems, [], problems.join('; '))

  const coverage = webLockKeys(LOCK_TEXT)
  assert.equal(
    terms.terms.size,
    coverage.packages_keys,
    `the terms were read for ${terms.terms.size} keys while §2.6's denominator is ${coverage.packages_keys} lock keys — the census and the denominator are of different sets`,
  )
})

// ---------------------------------------------------------------------------
// 3. The two named entries, against the keys that carry those terms.
// ---------------------------------------------------------------------------
test('§2.6 names the copyleft and attribution members of the web tree, and names exactly those', async () => {
  const terms = await publishedTerms()
  if (terms === null) {
    notRun('§2.6\'s named family entries against the tree', PUBLISHED_REASON)
    return
  }
  ran('§2.6\'s named family entries against the tree')

  const entries = nonPermissiveEntries(NOTICE_TEXT, '2.6')
  assert.equal(entries.length, 2, `§2.6 names ${entries.length} non-permissive entries; the section's table and its prose name two families, MPL-2.0 and CC-BY-4.0`)

  const problems = []
  for (const entry of entries) {
    const expanded = entryClaimedKeys(entry, COVERAGE_KEYS)
    problems.push(...expanded.problems.map((problem) => `${entry.family}: ${problem}`))
    problems.push(...expanded.unmatched.map((key) => `${entry.family}: the entry names ${key}, which the lock no longer pins`))
    problems.push(...expanded.notInLock.map((key) => `${entry.family}: the entry names ${key}, which is not a lock key`))

    const computedKeys = keysInFamily(terms.terms, new RegExp(`\\b${entry.family.replace(/[.+-]/g, (c) => `\\${c}`)}\\b`, 'i'))
    problems.push(...familyListProblems(entry.family, computedKeys, expanded.claimed))

    if (computedKeys.length !== entry.count) {
      problems.push(`${entry.family}: §2.6 states ${entry.count} of the 266 keys carry it; ${computedKeys.length} published records state it`)
    }
  }
  assert.deepEqual(problems, [], problems.join('; '))

  // The families the section says are absent, checked by looking for them.
  const families = termFamilies(terms.terms)
  const unexpected = [
    ...families.unresolved.map((key) => `${key} carries ${terms.terms.get(key).licence}, an unnamed licence`),
    ...families.sourceAvailable.map((key) => `${key} carries ${terms.terms.get(key).licence}, a source-available licence`),
  ]
  assert.deepEqual(unexpected, [], `§2.6 states "No GPL-family identifier, no source-available identifier, no UNLICENSED and no SEE LICENSE IN appears anywhere in the installed web tree"; ${unexpected.join('; ')}`)

  const gpl = [...terms.terms.entries()].filter(([, record]) => /\bGPL\b|GPLv|GPL-\d/.test(record.licence ?? ''))
  assert.deepEqual(gpl.map(([key]) => key), [], `§2.6 states no GPL-family identifier appears; ${gpl.map(([key, record]) => `${key} ${record.licence}`).join('; ')}`)
})

// ---------------------------------------------------------------------------
// 4. The three denominators, where the installed tree exists to measure them.
// ---------------------------------------------------------------------------
test('§2.6 lists three denominators, and they are the numbers an installed web tree presents', () => {
  if (!WEB_INSTALLED.available) {
    notRun('§2.6\'s installed-tree denominators', `no installed web tree (searched web/node_modules/.pnpm and the checkout root's; LABCAIRN_LICENCE_WEB_STORE names one; shell.yml installs no node_modules)`)
    return
  }
  ran('§2.6\'s installed-tree denominators')

  const denominators = webDenominators(NOTICE_TEXT)
  const stated = (needle) => {
    const entry = [...denominators.entries()].find(([phrase]) => phrase.includes(needle))
    assert.ok(entry, `§2.6 prints no denominator row for "${needle}"`)
    return entry[1]
  }

  // The needle is the phrase the row prints, matched without its markup: §2.6
  // writes `distinct \`name@version\`` and \`package.json\` records\`, and a needle
  // carrying the backticks would be a needle that only matches if the file keeps
  // its formatting, which is not the number being watched.
  const distinctStated = stated('distinct ')
  const recordsStated = stated('package.json records')
  const keysStated = stated('lock keys')
  const snapshotsStated = stated('snapshots')
  const unionStated = stated('union of the two sections')

  assert.equal(
    WEB_INSTALLED.distinct,
    distinctStated,
    `§2.6 states ${distinctStated} distinct name@version installed; the store at ${WEB_INSTALLED.storeDir} presents ${WEB_INSTALLED.distinct}`,
  )
  assert.equal(
    WEB_INSTALLED.records,
    recordsStated,
    `§2.6 states ${recordsStated} package.json records in that install; the store presents ${WEB_INSTALLED.records}`,
  )

  const coverage = webLockKeys(LOCK_TEXT)
  assert.equal(coverage.packages_keys, keysStated, `§2.6's packages: denominator is ${keysStated}; the lock has ${coverage.packages_keys}`)
  assert.equal(coverage.snapshots_keys, snapshotsStated, `§2.6's snapshots: denominator is ${snapshotsStated}; the lock has ${coverage.snapshots_keys}`)
  assert.equal(coverage.union_keys, unionStated, `§2.6 states a union of ${unionStated}; the lock's is ${coverage.union_keys}`)

  // The two denominators §2.6 explains as different numbers really are different.
  assert.notEqual(
    WEB_INSTALLED.records,
    WEB_INSTALLED.distinct,
    'the installed record count and the distinct-package count came out equal, which means the walk is not presenting the peer variants §2.6 says make them different numbers',
  )
})

// ---------------------------------------------------------------------------
// 5. Published record and installed declaration agree, where both exist.
// ---------------------------------------------------------------------------
test('the licences an installed web tree declares are the published licences, key for key', async () => {
  const terms = await publishedTerms()
  if (terms === null) {
    notRun('published terms against the installed tree', PUBLISHED_REASON)
    return
  }
  if (!WEB_INSTALLED.available) {
    notRun('published terms against the installed tree', `no installed web tree at ${webStoreDir() ?? '(none found)'}; web.yml installs one and a local checkout can too`)
    return
  }
  ran('published terms against the installed tree')

  const disagreements = termDisagreements(terms.terms, WEB_INSTALLED.terms)
  assert.deepEqual(
    disagreements,
    [],
    `${disagreements.length} package(s) declare different terms in the installed tree than in the published record of the same pinned version: ${disagreements.slice(0, 6).map((d) => `${d.key} published=${JSON.stringify(d.published)} installed=${JSON.stringify(d.installed)}`).join('; ')} — one of the two is not the terms the package travels under`,
  )

  assert.ok(
    WEB_INSTALLED.terms.size > 0,
    `the installed tree at ${WEB_INSTALLED.storeDir} answered none of the ${COVERAGE_KEYS.length} lock keys, so "the installed tree declares these licences" is not a measurement`,
  )
  const unanswered = WEB_INSTALLED.unanswered.length
  const lockTotal = webLockKeys(LOCK_TEXT).packages_keys
  assert.ok(
    WEB_INSTALLED.terms.size + unanswered === lockTotal,
    `the installed read answered ${WEB_INSTALLED.terms.size} keys and left ${unanswered} unanswered, which is not the ${lockTotal} keys the lock pins`,
  )
})

// ---------------------------------------------------------------------------
// 6. The sentinel says so.
// ---------------------------------------------------------------------------
test('an arm that could not look says NOT RUN with a reason, and the sentinel is the probe\'s own answer', async () => {
  await publishedTerms()
  assert.ok(RUN_LOG.length > 0, 'no arm reported anything, so this file measured nothing at all')
  const silent = RUN_LOG.filter((entry) => !entry.startsWith('RAN ') && !entry.startsWith('NOT RUN '))
  assert.deepEqual(silent, [], `these arms reported a state that is neither RAN nor NOT RUN: ${silent.join('; ')}`)
  const unexplained = RUN_LOG.filter((entry) => entry.startsWith('NOT RUN ') && !entry.includes(': '))
  assert.deepEqual(unexplained, [], `these arms say NOT RUN without naming a reason: ${unexplained.join('; ')}`)

  // The probes answer these themselves: a lock with no keys and a store that is
  // not there produce the empty answers the arms report, rather than a sentence.
  const noStore = installedTerms(LOCK_TEXT, path.join(REPO_ROOT, 'no-such-store'), {
    readRecords: () => [],
    resolveInstalled: () => ({ licences: new Map(), unresolved: [] }),
  })
  assert.equal(noStore.available, false, 'installedTerms reported an installed tree where there is none')
  const emptyLock = webLockKeys("lockfileVersion: '9.0'\n\nimporters: {}\n\npackages:\n\nsnapshots:\n")
  assert.equal(emptyLock.packages_keys, 0, 'the lock reader invented keys in an empty lock')
})

// ---------------------------------------------------------------------------
// The controls, on fixtures: the same comparison functions the tests above run,
// with one value changed. Fixtures are built here rather than read from an
// artefact, so the controls run wherever the file runs.
// ---------------------------------------------------------------------------
test('the controls fail for the properties: a wrong class count, a missing class, a renamed class, a family list off by one key', () => {
  const recorded = new Map([['MIT', 3], ['MPL-2.0', 1], ['CC-BY-4.0', 1]])
  const computed = new Map([['MIT', 3], ['MPL-2.0', 1], ['CC-BY-4.0', 1]])
  assert.deepEqual(classTableProblems(recorded, computed), [], 'the clean fixture did not compare clean, so these controls prove nothing')

  // A class count that drifted, while the total stays right — the exact shape
  // `notice-scope.test.mjs` cannot see because it only checks the total.
  const drifted = new Map([['MIT', 4], ['MPL-2.0', 0], ['CC-BY-4.0', 1]])
  const afterDrift = classTableProblems(recorded, drifted)
  assert.equal(afterDrift.length, 2, `a moved count produced ${afterDrift.length} problems: ${afterDrift.join('; ')}`)
  assert.ok(afterDrift.some((p) => /MIT/.test(p)) && afterDrift.some((p) => /MPL-2\.0/.test(p)), afterDrift.join('; '))
  const recordedTotal = [...recorded.values()].reduce((sum, v) => sum + v, 0)
  const driftedTotal = [...drifted.values()].reduce((sum, v) => sum + v, 0)
  assert.equal(recordedTotal, driftedTotal, 'the control moved a count and changed the total too, so it does not test the shape it claims')

  // A copyleft class arriving that the record names no row for. Two problems,
  // and both are wanted: the row is missing, and the record's rows no longer add
  // up to what the tree presents. A function that reported only the total would
  // let a renamed class pass; one that reported only the missing row would let a
  // total drift pass.
  const arrived = new Map([['MIT', 3], ['MPL-2.0', 1], ['CC-BY-4.0', 1], ['GPL-3.0-only', 1]])
  const afterArrival = classTableProblems(recorded, arrived)
  assert.equal(afterArrival.length, 2, `an unrecorded class produced ${afterArrival.length} problems: ${afterArrival.join('; ')}`)
  assert.ok(afterArrival.some((problem) => /GPL-3\.0-only/.test(problem)), afterArrival.join('; '))
  assert.ok(afterArrival.some((problem) => /add to 5/.test(problem)), afterArrival.join('; '))

  // A package reclassified out of a named family, and a family gaining a member.
  const familyKeys = ['lightningcss@1.33.0', 'lightningcss-linux-x64-gnu@1.33.0']
  const oneFewer = ['lightningcss@1.33.0']
  assert.deepEqual(familyListProblems('MPL-2.0', familyKeys, familyKeys), [], 'the clean family did not compare clean')
  const dropped = familyListProblems('MPL-2.0', oneFewer, familyKeys)
  assert.equal(dropped.length, 1, `a family member the tree no longer carries was not reported: ${dropped.join('; ')}`)
  const gained = familyListProblems('MPL-2.0', [...familyKeys, 'lightningcss-win32-arm64-msvc@1.33.0'], familyKeys)
  assert.equal(gained.length, 1, `a family member the record does not name was not reported: ${gained.join('; ')}`)

  // A §2.6 entry whose suffix expansion names a variant the lock stopped pinning.
  const entry = { family: 'MPL-2.0', count: 2, explicit: ['lightningcss@1.33.0'], suffixes: ['-linux-x64-gnu', '-gone-away'] }
  const expanded = entryClaimedKeys(entry, ['lightningcss@1.33.0', 'lightningcss-linux-x64-gnu@1.33.0'])
  assert.deepEqual(expanded.unmatched, ['lightningcss-gone-away@1.33.0'], `a suffix the lock does not pin was not reported: ${JSON.stringify(expanded)}`)

  // The terms-vocabulary patterns are the reader's, and they answer for known
  // strings: a source-available licence is not copyleft, and an unnamed licence
  // is not permissive.
  assert.match('BUSL-1.1', SOURCE_AVAILABLE)
  assert.equal(SOURCE_AVAILABLE.test('MIT'), false, 'the source-available pattern matches a permissive licence, so "no source-available identifier" is not a measurement')
  assert.equal(COPYLEFT.test('BUSL-1.1'), false, 'the copyleft pattern matches a source-available licence, which is a different obligation than §2.6 describes')
  assert.match('SEE LICENSE IN custom.txt', UNRESOLVED_TERMS)
  assert.equal(UNRESOLVED_TERMS.test('MIT'), false)

  // A published record and an installed declaration that disagree.
  const published = new Map([['react@19.3.1', { key: 'react@19.3.1', licence: 'MIT' }]])
  const installed = new Map([['react@19.3.1', 'MIT-0']])
  const disagree = termDisagreements(published, installed)
  assert.equal(disagree.length, 1, `a published/installed licence disagreement was not reported: ${JSON.stringify(disagree)}`)
  assert.deepEqual(termDisagreements(published, new Map([['react@19.3.1', 'MIT']])), [], 'agreeing sources were reported as disagreeing')

  // The lock's own integrity read: it is what binds a licence to pinned bytes,
  // and it has to answer for a real lock and for a tampered one.
  const realIntegrities = lockIntegrities(LOCK_TEXT)
  assert.ok(realIntegrities.size > 0, 'the lock integrity read found nothing in the real lock')
  const sampleKey = [...realIntegrities.keys()][0]
  const tampered = LOCK_TEXT.replace(realIntegrities.get(sampleKey), 'sha512-' + '0'.repeat(88))
  const afterTamper = lockIntegrities(tampered)
  assert.notEqual(afterTamper.get(sampleKey), realIntegrities.get(sampleKey), 'changing the lock did not change what the reader reads out of it')
})
