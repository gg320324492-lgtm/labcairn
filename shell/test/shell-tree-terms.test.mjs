/**
 * NOTICE §2.4's per-package licence classes, watched against each package's own terms.
 *
 * **Why this file exists.** `shell/test/notice-licences.test.mjs` already watches
 * §2.4 hard: every `name@version` the lock pins has a §2.4 row and vice versa, the
 * twelve surface figures are what the lock measures, the runtime/build split is the
 * split the lock's own closure walk gives, and §2.4.2's class table agrees with
 * §2.4.3's rows. Read those checks together and every one of them is satisfied by a
 * NOTICE whose classes are *wrong about the packages*. `classCounts` and `buildRows`
 * are both readers of the same file: the class table matching the rows means the
 * file agrees with itself. And "no copyleft term" is checked against the licence
 * strings §2.4 itself wrote. A package moved from `MPL-2.0` to `MIT` in §2.4.3, with
 * its §2.4.2 row adjusted to match, keeps all seven cases green.
 *
 * **What this file adds.** The package's own terms. §2.4 says where its figures came
 * from — "from each package's own record at `https://registry.npmjs.org`, and from
 * each package's own published tarball" — so the claim is checkable against the
 * registry record of the exact `name@version` the lock pins, bound to the lock's own
 * `sha512` for those bytes. Measured on this tree at `6cd8446`: 268/268 keys bound,
 * 3.3 s, and the recorded classes agree 268/268 with the published licences. That
 * agreement is the property; it has never been watched.
 *
 * **What it does not do.** It does not re-check the pairing §2.4 has with the lock,
 * the surface figures, or the closure split — `notice-licences.test.mjs` does those
 * and this file leaves them alone. It does not check the licence-document census
 * (§2.4's "252 of the 268 packages publish one, 259 documents in all, 16 publishing
 * no licence document"): that is a statement about the contents of 268 published
 * tarballs, and reading them is a download of every package in the tree.
 */

import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { licenceClassTable, readNotice, runtimeRows, buildGroups } from '../../.github/notice-readers.mjs'
import {
  classTable,
  classTableProblems,
  COPYLEFT,
  installedTerms,
  lockIntegrities,
  lockTerms,
  readRecord,
  registryTerms,
  retryDelay,
  SOURCE_AVAILABLE,
  termDisagreements,
  termFamilies,
  UNRESOLVED_TERMS,
} from '../../.github/npm-terms.mjs'
import { lockfileKeys } from '../../.github/shell-lockfile-keys.mjs'
import { installedPackages, resolveFromInstalled } from '../../.github/web-lockfile-keys.mjs'
import { shellPaths } from '../scripts/lib/shell-paths.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SHELL_ROOT = path.resolve(HERE, '..')
const REPO_ROOT = path.resolve(SHELL_ROOT, '..')
// The artefact paths, with an override each: a witness that can only be shown to
// fail by mutating a tracked file is a witness whose mutation checks leave the tree
// dirty, and §5.4's reproduction commands are run against copies outside the
// checkout anyway.
const LOCK_PATH = process.env.LABCAIRN_LICENCE_SHELL_LOCK ?? path.join(SHELL_ROOT, 'pnpm-lock.yaml')
const NOTICE_PATH = process.env.LABCAIRN_LICENCE_NOTICE ?? undefined

const NOTICE_TEXT = readNotice(NOTICE_PATH)
const LOCK_TEXT = fs.readFileSync(LOCK_PATH, 'utf8')
const MEASURED = lockfileKeys(LOCK_TEXT)

function shellStoreDir() {
  const candidates = [
    process.env.LABCAIRN_LICENCE_SHELL_STORE ?? '',
    path.join(SHELL_ROOT, 'node_modules', '.pnpm'),
    path.join(shellPaths({ here: HERE }).checkoutRoot, 'shell', 'node_modules', '.pnpm'),
  ].filter((entry) => entry && fs.existsSync(entry))
  return candidates[0] ?? null
}

const SHELL_INSTALLED = installedTerms(LOCK_TEXT, shellStoreDir() ?? '', {
  readRecords: (storeDir) => installedPackages(storeDir),
  resolveInstalled: (text, records) => resolveFromInstalled(lockfileKeys(text).all_entries, records),
})

const RUN_LOG = []
function ran(what) { RUN_LOG.push(`RAN ${what}`) }
function notRun(what, reason) { RUN_LOG.push(`NOT RUN ${what}: ${reason}`) }

let published = null
let publishedError = null
async function publishedTerms() {
  if (published === null && publishedError === null) {
    try {
      published = await lockTerms(LOCK_TEXT, MEASURED.all_entries, { concurrency: 24 })
    } catch (error) {
      publishedError = String(error?.message ?? error)
    }
  }
  return publishedError !== null ? null : published
}

const PUBLISHED_REASON = 'the npm registry could not be read (each package\'s terms come from registry.npmjs.org, which an offline run cannot reach)'

/**
 * The licence class §2.4 records for each package, from both halves of the section.
 *
 * §2.4.1's thirteen runtime rows carry the class in a column; §2.4.3 groups the 255
 * build-only packages under class headings. A key the two halves disagree about is
 * itself a problem, and it is reported here rather than resolved by preferring one.
 *
 * `runtimeKeys` and `buildOnlyKeys` come from the lock's own closure walk — the two
 * sets §2.4's surface table prints and `notice-licences.test.mjs` already checks
 * §2.4.1 against. The recorded sets are compared with those, so a package listed in
 * both halves (or in neither) reddens this rather than being smoothed over: the two
 * halves are supposed to cover the 268 without overlap, and a §2.4 that overlaps
 * them has two places a class can be stated and only one of them watched.
 */
export function recordedClasses(noticeText, { runtimeKeys, buildOnlyKeys }) {
  const recorded = new Map()
  const problems = []
  const runtime = runtimeRows(noticeText)
  const build = buildGroups(noticeText)

  const runtimeNamed = [...runtime.keys()]
  for (const key of runtimeNamed) recorded.set(key, runtime.get(key).licence)
  for (const key of runtimeNamed.filter((key) => !runtimeKeys.includes(key))) {
    problems.push(`§2.4.1 names ${key}, which the lock's electron closure does not resolve`)
  }
  const runtimeMissing = runtimeKeys.filter((key) => !runtime.has(key))
  if (runtimeMissing.length) problems.push(`§2.4.1 names none of: ${runtimeMissing.join(', ')}`)

  for (const [licence, keys] of build) {
    for (const key of keys) {
      if (!buildOnlyKeys.includes(key)) {
        problems.push(`§2.4.3 lists ${key} under ${licence}, which is not a build-only entry of the lock`)
        continue
      }
      if (runtime.has(key)) {
        problems.push(`${key} is listed in both §2.4.1 (as ${runtime.get(key).licence}) and §2.4.3 (under ${licence})`)
      }
      // Recorded even when it is also in §2.4.1: the overlap is one problem, and
      // skipping the record would add a second, wrong one ("§2.4.3 lists none
      // of") for a row that is plainly there.
      recorded.set(key, licence)
    }
  }
  const buildMissing = buildOnlyKeys.filter((key) => !recorded.has(key))
  if (buildMissing.length) problems.push(`§2.4.3 lists none of: ${buildMissing.join(', ')}`)

  return { recorded, problems }
}

/**
 * §2.4's recorded classes against the published licences, both directions.
 *
 * `recorded` maps `name@version` → the class §2.4 states; `published` is the key →
 * record map from the registry. A class that is not what the package states, a
 * package no class is recorded for, and a class held for a package the tree no
 * longer pins are three different defects.
 */
export function recordedClassProblems(recorded, published) {
  const problems = []
  for (const [key, licence] of published) {
    const stated = recorded.get(key)
    if (stated === undefined) {
      problems.push(`${key} publishes ${JSON.stringify(licence.licence)} and §2.4 records no class for it`)
      continue
    }
    if (stated !== (licence.licence ?? null)) {
      problems.push(`${key}: §2.4 records ${JSON.stringify(stated)}, the published record states ${JSON.stringify(licence.licence)}`)
    }
  }
  for (const key of recorded.keys()) {
    if (!published.has(key)) problems.push(`§2.4 records a class for ${key}, which the tree does not pin`)
  }
  return problems.sort()
}

// ---------------------------------------------------------------------------
// 1. Every §2.4 class is the published licence of that exact pinned package.
// ---------------------------------------------------------------------------
test('every licence class §2.4 records is the licence the pinned package itself publishes', async () => {
  const terms = await publishedTerms()
  if (terms === null) {
    notRun('§2.4\'s per-package classes against the published records', PUBLISHED_REASON)
    return
  }
  ran('§2.4\'s per-package classes against the published records')

  assert.equal(
    terms.bytesDisagree.length,
    0,
    `§2.4's classes are compared with each package's published record, and ${terms.bytesDisagree.length} of those records do not match the lock's own integrity: ${terms.bytesDisagree.slice(0, 4).map((f) => `${f.key} ${f.reason}`).join('; ')} — the terms read are not terms of the bytes this lock pins`,
  )
  assert.deepEqual(
    terms.failures,
    [],
    `${terms.failures.length} pinned keys were not answered by the registry (${terms.failures.slice(0, 4).map((f) => f.key).join(', ')}), so the comparison below is of a tree that was only partly read`,
  )

  const { recorded, problems } = recordedClasses(NOTICE_TEXT, {
    runtimeKeys: MEASURED.runtime_entries,
    buildOnlyKeys: MEASURED.build_only_entries,
  })
  assert.deepEqual(problems, [], problems.join('; '))
  assert.equal(
    recorded.size,
    MEASURED.distinct_name_version,
    `§2.4 records a class for ${recorded.size} packages; the lock pins ${MEASURED.distinct_name_version}`,
  )

  const mismatches = recordedClassProblems(recorded, terms.terms)
  assert.deepEqual(mismatches, [], mismatches.join('; '))
})

// ---------------------------------------------------------------------------
// 2. §2.4.2's class table, against the classes computed over the build-only closure.
// ---------------------------------------------------------------------------
test('§2.4.2\'s class counts are the counts the build closure\'s published licences produce', async () => {
  const terms = await publishedTerms()
  if (terms === null) {
    notRun('§2.4.2\'s class counts against the published licences', PUBLISHED_REASON)
    return
  }
  ran('§2.4.2\'s class counts against the published licences')

  const buildOnly = new Map(
    MEASURED.build_only_entries
      .map((key) => [key, terms.terms.get(key)])
      .filter(([, record]) => record !== undefined),
  )
  assert.equal(
    buildOnly.size,
    MEASURED.build_only,
    `the published terms answered ${buildOnly.size} of the ${MEASURED.build_only} build-only packages §2.4.2 counts`,
  )

  const computed = classTable(buildOnly)
  const recorded = licenceClassTable(NOTICE_TEXT, '2.4.2')
  const problems = classTableProblems(recorded, computed)
  assert.deepEqual(problems, [], problems.join('; '))
})

// ---------------------------------------------------------------------------
// 3. The permissive claims §2.4 makes about the whole surface.
// ---------------------------------------------------------------------------
test('the shell tree\'s published licences contain no copyleft, source-available or unnamed term', async () => {
  const terms = await publishedTerms()
  if (terms === null) {
    notRun('the shell tree\'s copyleft absence against the published licences', PUBLISHED_REASON)
    return
  }
  ran('the shell tree\'s copyleft absence against the published licences')

  const families = termFamilies(terms.terms)
  const found = [
    ...families.copyleft.map((key) => `${key} publishes ${terms.terms.get(key).licence}, a copyleft term`),
    ...families.sourceAvailable.map((key) => `${key} publishes ${terms.terms.get(key).licence}, a source-available term`),
    ...families.unresolved.map((key) => `${key} publishes ${terms.terms.get(key).licence}, an unnamed licence`),
  ]
  assert.deepEqual(
    found,
    [],
    `§2.4 records this surface as carrying no copyleft ("No package among the shell tree's 268 is copyleft") and §2.4's re-review found 0 undeterminable; ${found.join('; ')}`,
  )
})

// ---------------------------------------------------------------------------
// 4. Where an installed tree exists, it is the second reader.
// ---------------------------------------------------------------------------
test('the installed shell tree declares the published licences, key for key', async () => {
  const terms = await publishedTerms()
  if (terms === null) {
    notRun('the published licences against the installed shell tree', PUBLISHED_REASON)
    return
  }
  if (!SHELL_INSTALLED.available) {
    notRun('the published licences against the installed shell tree', `no installed shell tree (searched shell/node_modules/.pnpm and the checkout root's; LABCAIRN_LICENCE_SHELL_STORE names one; shell.yml installs no node_modules)`)
    return
  }
  ran('the published licences against the installed shell tree')

  const disagreements = termDisagreements(terms.terms, SHELL_INSTALLED.terms)
  assert.deepEqual(
    disagreements,
    [],
    `${disagreements.length} package(s) declare different terms in the installed tree than in the published record of the same pinned version: ${disagreements.slice(0, 6).map((d) => `${d.key} published=${JSON.stringify(d.published)} installed=${JSON.stringify(d.installed)}`).join('; ')} — one of the two is not the terms the package travels under`,
  )
  assert.ok(
    SHELL_INSTALLED.terms.size > 0,
    `the installed tree at ${SHELL_INSTALLED.storeDir} answered none of the ${MEASURED.all_entries.length} lock keys, so "the installed tree declares these licences" is not a measurement`,
  )
})

// ---------------------------------------------------------------------------
// 5. The reader's retry policy, watched.
// ---------------------------------------------------------------------------
/**
 * **Why this is a case and not a detail.** Both npm witnesses read terms over the
 * network, and the failure that actually happened here was a network failure: run
 * as one `node --test 'test/*.test.mjs'`, the two files put 534 keys through the
 * registry and `@peculiar/json-schema@1.1.12` came back unanswered, while fetching
 * that key alone answers 200. A witness that reddens on a throttled answer fails
 * for a reason that has nothing to do with the property under watch; a witness that
 * treats a throttled answer as "no such package" reports a fact the registry never
 * stated. Either way the reader has to be checked on the answers themselves, which
 * is what this case does — no network, no luck.
 */
test('the reader retries a throttled answer and reports a 404 as an answer about the package', async () => {
  const waits = []
  const wait = (ms) => {
    waits.push(ms)
  }

  // A 429 that clears: the key is answered, and the wait between attempts grows.
  let throttledCalls = 0
  const throttled = async () => {
    throttledCalls += 1
    if (throttledCalls < 3) return { status: 429, ok: false, headers: { get: () => null } }
    return { status: 200, ok: true, json: async () => ({ license: 'MIT', dist: { integrity: 'sha512-x' } }) }
  }
  const cleared = await readRecord('https://example.invalid/key', { attempts: 4, wait, fetchImpl: throttled })
  assert.equal(cleared.ok, true, `a throttled answer that cleared was not treated as answered: ${JSON.stringify(cleared)}`)
  assert.equal(throttledCalls, 3, `the reader made ${throttledCalls} attempts before the answer cleared, expected 3`)
  assert.deepEqual(waits, [500, 1000], `the backoff between attempts is not growing: ${waits.join(', ')}`)

  // A 404 is an answer about the package, not a transport failure: no retry.
  let notFoundCalls = 0
  const notFound = async () => {
    notFoundCalls += 1
    return { status: 404, ok: false, headers: { get: () => null } }
  }
  const missing = await readRecord('https://example.invalid/key', { attempts: 4, wait, fetchImpl: notFound })
  assert.equal(missing.ok, false, 'a 404 was reported as answered')
  assert.match(missing.reason, /404/, `the failure does not say the registry stated a 404: ${missing.reason}`)
  assert.equal(notFoundCalls, 1, `the reader retried a 404 ${notFoundCalls} times; a package that does not exist does not start existing`)

  // A registry that never answers is a failure that says so, with the attempts it took.
  let failingCalls = 0
  const failing = async () => {
    failingCalls += 1
    return { status: 503, ok: false, headers: { get: () => null } }
  }
  const exhausted = await readRecord('https://example.invalid/key', { attempts: 3, wait, fetchImpl: failing })
  assert.equal(exhausted.ok, false, 'a registry that answered 503 every time was reported as answered')
  assert.match(exhausted.reason, /after 3 attempts/, `the failure does not name how many attempts it took: ${exhausted.reason}`)
  assert.equal(failingCalls, 3, `the reader made ${failingCalls} attempts against a registry that never answered, expected 3`)

  // A transport exception is retried too, not just a bad status.
  let thrown = 0
  const throwing = async () => {
    thrown += 1
    if (thrown < 2) throw new Error('socket hang up')
    return { status: 200, ok: true, json: async () => ({ license: 'ISC' }) }
  }
  const recovered = await readRecord('https://example.invalid/key', { attempts: 3, wait, fetchImpl: throwing })
  assert.equal(recovered.ok, true, `a transport failure that cleared was not recovered: ${JSON.stringify(recovered)}`)

  // `Retry-After` is honoured when the answer carries one, and the wait is bounded.
  assert.equal(retryDelay(1, { headers: { get: () => '2' } }), 2000, 'a Retry-After of 2 seconds did not set a 2-second wait')
  assert.equal(retryDelay(1, { headers: { get: () => null } }), 500, 'the first backoff is not the short one it claims to be')
  assert.ok(retryDelay(9, { headers: { get: () => null } }) <= 20_000, 'the backoff is unbounded, so a witness can stall on it')
  assert.equal(retryDelay(1, { headers: { get: () => '999999' } }), 20_000, 'a huge Retry-After was followed without a ceiling')

  // The failure reaches the witness as a failure. A key that is not answered has to
  // surface in `failures`, because a class table built over a partly-read tree is a
  // table for a tree nobody read.
  const terms = await registryTerms(['anything@1.0.0'], {
    concurrency: 1,
    attempts: 2,
    wait,
    fetchImpl: async () => ({ status: 503, ok: false, headers: { get: () => null } }),
  })
  assert.equal(terms.terms.size, 0, 'a census was built over a key the registry never answered')
  assert.equal(terms.failures.length, 1, `an unanswered key produced ${terms.failures.length} reported failures`)
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

  const noStore = installedTerms(LOCK_TEXT, path.join(REPO_ROOT, 'no-such-store'), {
    readRecords: () => [],
    resolveInstalled: () => ({ licences: new Map(), unresolved: [] }),
  })
  assert.equal(noStore.available, false, 'installedTerms reported an installed tree where there is none')
})

// ---------------------------------------------------------------------------
// The controls, on fixtures: the same comparison functions the tests above run,
// with one value changed. Built here rather than read from an artefact, so they
// run on a runner that installs nothing and reaches nothing.
// ---------------------------------------------------------------------------
test('the controls fail for the properties: a reclassified package, a package with no class, a class held for a departed package, two disagreeing halves', () => {
  const published = new Map([
    ['react@19.3.1', { key: 'react@19.3.1', licence: 'MIT' }],
    ['semver@7.8.6', { key: 'semver@7.8.6', licence: 'ISC' }],
    ['undici@7.30.2', { key: 'undici@7.30.2', licence: 'MIT' }],
  ])
  const recorded = new Map([['react@19.3.1', 'MIT'], ['semver@7.8.6', 'ISC'], ['undici@7.30.2', 'MIT']])
  assert.deepEqual(recordedClassProblems(recorded, published), [], 'the clean fixture did not compare clean, so these controls prove nothing')

  // A package reclassified inside NOTICE, which is the change every existing
  // §2.4 check passes: the row is still there, the class table can be adjusted to
  // match it, and no copyleft word appears in either.
  const reclassified = new Map(recorded)
  reclassified.set('semver@7.8.6', 'MIT')
  const afterReclass = recordedClassProblems(reclassified, published)
  assert.equal(afterReclass.length, 1, `a reclassified package produced ${afterReclass.length} problems: ${afterReclass.join('; ')}`)
  assert.match(afterReclass[0], /semver@7\.8\.6/, afterReclass[0])
  assert.match(afterReclass[0], /ISC/, afterReclass[0])

  // A copyleft package arriving in the lock with no row.
  const arrived = new Map(published)
  arrived.set('copyleft-thing@1.0.0', { key: 'copyleft-thing@1.0.0', licence: 'MPL-2.0' })
  const afterArrival = recordedClassProblems(recorded, arrived)
  assert.equal(afterArrival.length, 1, `an unrecorded package produced ${afterArrival.length} problems: ${afterArrival.join('; ')}`)
  assert.match(afterArrival[0], /records no class/, afterArrival[0])

  // A class held for a package the tree stopped pinning.
  const departed = new Map(recorded)
  departed.set('gone@9.9.9', 'MIT')
  const afterDeparture = recordedClassProblems(departed, published)
  assert.equal(afterDeparture.length, 1, `a stale class produced ${afterDeparture.length} problems: ${afterDeparture.join('; ')}`)
  assert.match(afterDeparture[0], /does not pin/, afterDeparture[0])

  // §2.4's two halves listing the same package, or dropping one. In the real §2.4
  // the halves are disjoint — §2.4.1's 13 plus §2.4.3's 255 make the 268 — so these
  // arms run on a synthetic §2.4 shaped like the real section (§2.4.3's headings are
  // `  MIT  (190)`: a class and a parenthesised count) against the lock's own key
  // sets, and the real §2.4 is then checked against the real lock.
  const lockSets = { runtimeKeys: ['undici@7.30.2'], buildOnlyKeys: ['undici@7.30.2', 'left-pad@1.3.0'] }
  const synthetic = [
    '2.4.1  The runtime closure, in full: 1 package',
    '-----',
    '  undici  7.30.2  MIT  Copyright (c) 2020 Ethan Arrowood',
    '',
    '2.4.3  Every build-closure package, named',
    '-----',
    '  MIT  (2)',
    '    undici@7.30.2',
    '    left-pad@1.3.0',
    '',
    '3.  Next section',
    '-----',
  ].join('\n')
  const overlapping = recordedClasses(synthetic, lockSets)
  assert.equal(
    overlapping.problems.length,
    1,
    `a package listed in both halves produced ${overlapping.problems.length} problems: ${overlapping.problems.join('; ')}`,
  )
  assert.match(overlapping.problems[0], /listed in both/, overlapping.problems[0])
  assert.match(overlapping.problems[0], /undici@7\.30\.2/, overlapping.problems[0])

  // A build-only package §2.4.3 omits, and a §2.4.3 row for a package the lock does
  // not place in the build closure.
  const dropped = recordedClasses(synthetic.replace('    left-pad@1.3.0\n', ''), lockSets)
  assert.ok(dropped.problems.some((problem) => /§2\.4\.3 lists none of/.test(problem)), dropped.problems.join('; '))
  const added = recordedClasses(synthetic.replace('    left-pad@1.3.0', '    not-in-lock@9.9.9'), lockSets)
  assert.ok(added.problems.some((problem) => /is not a build-only entry/.test(problem)), added.problems.join('; '))

  // The real §2.4 against the lock's own sets: the fixture above stands in for a
  // section that really reads.
  const real = recordedClasses(NOTICE_TEXT, {
    runtimeKeys: MEASURED.runtime_entries,
    buildOnlyKeys: MEASURED.build_only_entries,
  })
  assert.deepEqual(real.problems, [], 'the real §2.4 already disagrees with the lock about which half each package is in, so these controls prove nothing')
  assert.equal(
    real.recorded.size,
    MEASURED.distinct_name_version,
    `the real §2.4 records ${real.recorded.size} classes; the lock pins ${MEASURED.distinct_name_version} — the fixture above is not standing in for a section that reads`,
  )

  // The class counts, computed rather than transcribed.
  const buildOnly = new Map([
    ['a@1.0.0', { key: 'a@1.0.0', licence: 'MIT' }],
    ['b@1.0.0', { key: 'b@1.0.0', licence: 'MIT' }],
    ['c@1.0.0', { key: 'c@1.0.0', licence: 'ISC' }],
  ])
  assert.deepEqual(
    classTableProblems(new Map([['MIT', 2], ['ISC', 1]]), classTable(buildOnly)),
    [],
    'the clean class fixture did not compare clean',
  )
  assert.equal(
    classTableProblems(new Map([['MIT', 2], ['ISC', 1]]), classTable(new Map([['a@1.0.0', { licence: 'MIT' }], ['b@1.0.0', { licence: 'MIT' }], ['c@1.0.0', { licence: 'GPL-2.0-only' }]]))).length,
    2,
    'a copyleft class arriving in the build closure did not redden the class comparison twice (the missing row and the total)',
  )

  // The absence claims are checked by looking for what would falsify them.
  assert.match('MPL-2.0', COPYLEFT)
  assert.match('BUSL-1.1', SOURCE_AVAILABLE)
  assert.match('SEE LICENSE IN custom.txt', UNRESOLVED_TERMS)
  assert.equal(COPYLEFT.test('MIT'), false, 'the copyleft pattern matches a permissive licence, so "no copyleft among the 268" is not a measurement')
  assert.equal(SOURCE_AVAILABLE.test('BlueOak-1.0.0'), false, 'the source-available pattern matches BlueOak, which §2.4.2 names as ISC with an attribution clause')

  // The integrity read answers for the real lock and for a tampered one.
  const realIntegrities = lockIntegrities(LOCK_TEXT)
  assert.ok(realIntegrities.size >= MEASURED.distinct_name_version, `the lock integrity read found ${realIntegrities.size} of ${MEASURED.distinct_name_version} pinned keys`)
  const sampleKey = [...realIntegrities.keys()][0]
  const tampered = LOCK_TEXT.replace(realIntegrities.get(sampleKey), `sha512-${'0'.repeat(88)}`)
  assert.notEqual(lockIntegrities(tampered).get(sampleKey), realIntegrities.get(sampleKey), 'changing the lock did not change what the reader reads out of it')
})
