/**
 * NOTICE §2.5's eight installer binaries, watched against the bundles they come from.
 *
 * **Why this file exists.** §2.5 records eight binaries — seven NSIS plug-ins
 * the installer carries in `$PLUGINSDIR` and `elevate.exe` in the payload's
 * `resources/` — each with a byte count, a sha256, the bundle it came from, a
 * licence and a holder. The only watch on it, `notice-scope.test.mjs`'s
 * `binaryLicenceProblems`, reads those records **against each other**: it asks
 * whether each entry has a sha256 and a licence, and it says so in its own
 * header. §2.5.2 records the owner's 2026-11-12 decision that a watcher which
 * catches *a ninth binary entering the archive* does not exist. Nothing compared
 * §2.5's hashes to the bytes the build actually downloads. A plug-in replaced by
 * a different build — same name, same size, different terms — would have left
 * every sentence in §2.5 true and every check green.
 *
 * **Where the reader comes from.** NOTICE §5.4 names the artefacts: the two
 * electron-builder caches the NSIS target downloads
 * (`${ELECTRON_BUILDER_CACHE}/nsis-3.0.4.1`, `…/nsis-resources-3.4.1`) and the
 * installer extract. This file hashes the real bytes in those bundles and
 * compares. A third source is `app-builder-lib`'s own `getBinFromUrl` declaration
 * — the bundle names and checksums the build asks its downloader to verify —
 * which is what ties "the bundle §2.5 names" to "the bundle this version of
 * electron-builder fetches": bump `electron-builder` and the plug-ins move to a
 * newer bundle, and the declaration changes.
 *
 * **What it does not do.** It draws no licence conclusion from a binary's bytes.
 * §2.5 records that the compiled binaries carry no licence text, and §2.5.1
 * measures it; the terms come from the bundle that carries them, and the only
 * statement drawn from bytes here is §2.5.1's own — that a licence statement is
 * *absent* from them — which is checked by looking for what would falsify it.
 *
 * **What is NOT RUN, and why that is said out loud.** `shell.yml` installs no
 * `node_modules` and builds no installer
 * (`tests/test_shell_ci.py::test_the_test_step_runs_inside_the_shell_and_names_the_runner_temp`
 * refuses a `pnpm install` step), and a GitHub runner has no electron-builder
 * cache. On such a machine the arms that need the artefacts report `NOT RUN`
 * with the reason, and the last case checks that they said it — a record that
 * reads as a pass over an arm that never ran is the failure mode `CLAUDE.md`
 * calls the dangerous kind, and the reason the repository prints a sentinel for
 * an unmeasured value rather than a zero.
 */

import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test, { after } from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  binaryRecords,
  copyingClaim,
  noticeSubsection,
  readNotice,
} from '../../.github/notice-readers.mjs'
import {
  binaryCarriesLicenceStatement,
  binaryRecordProblems,
  bundleFiles,
  bundleNamedFromRecord,
  defaultCacheDir,
  extractMembers,
  findCacheBundles,
  fingerprint,
  isLicenceDocument,
  licenceDocumentKind,
  licenceDocumentsIn,
  memberRecordProblems,
  storeDirectoryFor,
  toolchainDeclarations,
  toolchainRecordProblems,
} from '../../.github/installer-binaries.mjs'
import { lockfileKeys } from '../../.github/shell-lockfile-keys.mjs'
import { shellPaths } from '../scripts/lib/shell-paths.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SHELL_ROOT = path.resolve(HERE, '..')
const REPO_ROOT = path.resolve(SHELL_ROOT, '..')

const NOTICE_TEXT = readNotice()
const RECORDS = binaryRecords(NOTICE_TEXT)
const COPYING = copyingClaim(NOTICE_TEXT)

/**
 * The artefact locations, resolved the way `shell/scripts/lib/shell-paths.mjs`
 * resolves its own: an explicit override first, then the default that names the
 * scratch root this project keeps outside the checkout.
 */
const CACHE_DIR = process.env.LABCAIRN_LICENCE_NSIS_CACHE ?? defaultCacheDir()
const EXTRACT_DIRS = (process.env.LABCAIRN_LICENCE_INSTALLER_EXTRACT ?? '')
  .split(path.delimiter)
  .filter((entry) => entry.length > 0 && fs.existsSync(entry))

const CACHE = findCacheBundles(CACHE_DIR)

/**
 * Where an installed `app-builder-lib` could be found, in the order tried.
 *
 * A worktree checkout has no `node_modules` of its own and the tree it was
 * cloned from does, which is the same problem `shell/scripts/lib/shell-paths.mjs`
 * solves for the CLI the drain witness spawns — so the same resolution is used
 * here rather than a second copy of the rule.
 */
function toolchainSearchDirs() {
  return [
    process.env.LABCAIRN_LICENCE_APP_BUILDER_LIB ?? '',
    path.join(SHELL_ROOT, 'node_modules', '.pnpm'),
    path.join(shellPaths({ here: HERE }).checkoutRoot, 'shell', 'node_modules', '.pnpm'),
  ].filter((entry) => entry && fs.existsSync(entry))
}

/**
 * The files each bundle holds, keyed by lower-cased file name.
 *
 * Built once per bundle rather than once per record: the comparison §2.5 needs
 * is "is this hash one of the hashes this bundle actually presents", and a
 * lookup that re-walks the bundle per record reports a different set of
 * candidates depending on which record asked.
 */
function filesByName(bundleName) {
  const byName = new Map()
  for (const dir of CACHE.bundles.get(bundleName) ?? []) {
    for (const file of bundleFiles(dir)) {
      const key = path.basename(file).toLowerCase()
      if (!byName.has(key)) byName.set(key, [])
      byName.get(key).push(fingerprint(file))
    }
  }
  return byName
}

/** The §2.5 records, grouped by the bundle each one names. */
function recordsByBundle() {
  const grouped = new Map()
  for (const record of RECORDS) {
    const bundleName = bundleNamedFromRecord(record)
    if (!bundleName) continue
    if (!grouped.has(bundleName)) grouped.set(bundleName, [])
    grouped.get(bundleName).push(record)
  }
  return grouped
}

const RUN_LOG = []

// The log is the point of the sentinel. A witness that reports NOT RUN into a
// list nobody reads has produced the one thing this project must not produce:
// a transcript that shows passing tests and no hint that some of them
// measured nothing. So the log is written out when the run ends, and every
// entry says which arm it belongs to.
after(() => {
  for (const entry of RUN_LOG) process.stdout.write(`${entry}\n`)
})
function ran(what) {
  RUN_LOG.push(`RAN ${what}`)
}
function notRun(what, reason) {
  RUN_LOG.push(`NOT RUN ${what}: ${reason}`)
}

const CACHE_REASON = `no electron-builder cache at ${CACHE_DIR} (LABCAIRN_LICENCE_NSIS_CACHE names it; shell.yml downloads no toolchain)`
const EXTRACT_REASON = `no installer extract (LABCAIRN_LICENCE_INSTALLER_EXTRACT names one; shell.yml builds no installer)`

// ---------------------------------------------------------------------------
// 1. Each §2.5 hash and size is the real bytes in the bundle it names.
// ---------------------------------------------------------------------------
test('every §2.5 binary hash and size is the byte count and hash of the real file in the bundle it names', () => {
  if (!CACHE.available) {
    notRun('§2.5 hashes against the bundle bytes', CACHE_REASON)
    return
  }
  ran('§2.5 hashes against the bundle bytes')
  const problems = []
  for (const [bundleName, records] of recordsByBundle()) {
    if (!CACHE.bundles.has(bundleName)) {
      problems.push(
        `§2.5 records ${records.length} binaries from ${bundleName}, which the cache at ${CACHE_DIR} does not hold (it holds: ${[...CACHE.bundles.keys()].join(', ') || 'nothing'})`,
      )
      continue
    }
    problems.push(...binaryRecordProblems(records, filesByName(bundleName)))
  }
  for (const record of RECORDS) {
    if (!bundleNamedFromRecord(record)) {
      problems.push(`${record.name}: §2.5 names no recognisable bundle in ${JSON.stringify(record.fields.bundle)}`)
    }
  }
  assert.deepEqual(problems, [], problems.join('; '))
})

// ---------------------------------------------------------------------------
// 2. No binary enters the artefact that §2.5 does not name.
// ---------------------------------------------------------------------------
test('the binaries the installer actually carries are exactly the eight §2.5 records — no ninth binary', () => {
  if (EXTRACT_DIRS.length === 0) {
    notRun('the extract\'s binaries against §2.5\'s eight names', EXTRACT_REASON)
    return
  }
  ran('the extract\'s binaries against §2.5\'s eight names')

  // §2.5.2 records the owner's 2026-11-12 decision on this exact point: "a
  // per-binary licence census of the installer binaries, witnessed by a test —
  // … a watcher that would catch a ninth binary entering the archive does not
  // exist." This is that watcher, over the scope §2.5 itself defines: every
  // §2.5 record's `path` field names either `$PLUGINSDIR\…` or `resources\…`,
  // so those two member groups are the ones §2.5 claims to enumerate in full.
  //
  // It is the *artefact* that is enumerated, not the bundles: the bundles ship
  // every plug-in electron-builder could pick (AdvSplash, Math, nsisunz, INetC
  // …) and the installer carries a subset, so a comparison against the bundles
  // would report plug-ins that never travel. And it is not the Electron payload
  // either: `ffmpeg.dll` and the rest of the runtime are §2.4.1's surface, whose
  // terms travel in `LICENSES.chromium.html`, and §2.5 says so.
  const members = extractMembers(EXTRACT_DIRS)
  const inScope = members.filter((member) => /^\$PLUGINSDIR\/|^resources\//.test(member.member))
  const binaries = inScope.filter((member) => /\.(dll|exe)$/i.test(member.member))
  const { unrecorded, missing } = memberRecordProblems(binaries, RECORDS)

  assert.deepEqual(
    unrecorded,
    [],
    `the installer carries ${unrecorded.length} binary(ies) §2.5 records nothing about: ${unrecorded.join(', ')} — a binary that enters the artefact under a licence this file does not name is the defect §2.5.2 says no watcher exists for`,
  )

  assert.deepEqual(
    missing,
    [],
    `§2.5 records ${missing.join(', ')} but the installer carries none of them — §2.5 is describing an artefact that no longer contains it`,
  )
})

// ---------------------------------------------------------------------------
// 3. The terms §2.5 states come from a bundle that states them.
// ---------------------------------------------------------------------------
test('the zlib/libpng terms §2.5 records for four binaries are stated by the COPYING §2.5 names, byte-for-byte', () => {
  if (!CACHE.available) {
    notRun('the NSIS COPYING against §2.5\'s claim', CACHE_REASON)
    return
  }
  ran('the NSIS COPYING against §2.5\'s claim')
  const dirs = CACHE.bundles.get('nsis-3.0.4.1')
  assert.ok(dirs?.length, `the cache holds no nsis-3.0.4.1 bundle; §2.5 records four binaries as coming from it (cache dirs found: ${[...CACHE.bundles.keys()].join(', ') || 'none'})`)

  const copying = dirs
    .flatMap((dir) => bundleFiles(dir))
    .find((file) => path.basename(file) === 'COPYING')
  assert.ok(copying, 'nsis-3.0.4.1 carries no COPYING file, which §2.5 names as the licence document for four of the eight binaries')

  const print = fingerprint(copying)
  assert.equal(print.sha256, COPYING.sha256, `§2.5 states the NSIS COPYING is sha256 ${COPYING.sha256} but the file the build downloaded is ${print.sha256}`)
  assert.equal(print.bytes, COPYING.bytes, `§2.5 states the NSIS COPYING is ${COPYING.bytes} bytes; the real file is ${print.bytes}`)

  const text = fs.readFileSync(copying, 'utf8')
  assert.match(
    text,
    /plug-ins[\s\S]{0,200}?zlib\/libpng/i,
    'the COPYING §2.5 names does not license the plug-ins under zlib/libpng, so the four §2.5 records that cite it are citing a document that does not say that',
  )
})

test('the two §2.5 records it calls unresolved are unresolved because their bundle states no terms at all', () => {
  if (!CACHE.available) {
    notRun('nsis-resources-3.4.1\'s absence of a licence document', CACHE_REASON)
    return
  }
  ran('nsis-resources-3.4.1\'s absence of a licence document')
  const dirs = CACHE.bundles.get('nsis-resources-3.4.1')
  assert.ok(dirs?.length, `the cache holds no nsis-resources-3.4.1 bundle (found: ${[...CACHE.bundles.keys()].join(', ') || 'none'})`)

  const documents = dirs.flatMap((dir) => licenceDocumentsIn(dir))
  const recordedUnresolved = RECORDS.filter((record) => /unresolved/i.test(record.fields.licence ?? ''))
  if (documents.length > 0) {
    assert.ok(
      recordedUnresolved.length === 0,
      `nsis-resources-3.4.1 carries ${documents.length} licence document(s) (${documents.map((f) => path.basename(f)).join(', ')}), but §2.5 still records ${recordedUnresolved.length} binary/binaries as unresolved and §2.5 says the bundle "carries no licence file at all"`,
    )
    return
  }
  // No document: the records that state a *specific* licence for a binary from
  // this bundle are the ones that need a source, and §2.5 gives one for the two
  // LGPL entries (the plug-in's own source header, the 7-Zip terms) while
  // naming the other two as unresolved.
  const specific = RECORDS.filter(
    (record) => bundleNamedFromRecord(record) === 'nsis-resources-3.4.1' && !/unresolved/i.test(record.fields.licence ?? ''),
  )
  assert.equal(
    specific.length,
    2,
    `§2.5 records ${specific.length} binaries from nsis-resources-3.4.1 with a named licence; with no licence document in that bundle, only the two whose grant comes from elsewhere (StdUtils' own source header, 7-Zip's terms) can be recorded, and ${specific.map((s) => s.name).join(', ')} would need a source`,
  )
})

// ---------------------------------------------------------------------------
// 4. The bundle §2.5 names is the bundle the build's own toolchain fetches.
// ---------------------------------------------------------------------------
test('the NSIS bundles §2.5 names are the bundles the pinned electron-builder declares, with the checksums it pins', () => {
  const lockText = fs.readFileSync(path.join(SHELL_ROOT, 'pnpm-lock.yaml'), 'utf8')
  const direct = lockfileKeys(lockText)
  const pinnedBuilder = direct.all_entries.filter((key) => /^electron-builder@/.test(key)).sort()
  assert.ok(pinnedBuilder.length > 0, 'shell/pnpm-lock.yaml pins no electron-builder, so the §2.5 toolchain claim has no pin to be about')

  // The declaration is read from the package the *lock pins*, not from whatever
  // copy the machine happens to have installed: a declaration read from a
  // different version of app-builder-lib would be a statement about a toolchain
  // this tree does not use. pnpm names each store directory `<name>@<version>`
  // plus a peer suffix, so the pinned version selects the directory.
  const appBuilderKeys = direct.all_entries.filter((key) => /^app-builder-lib@/.test(key)).sort()
  assert.equal(appBuilderKeys.length, 1, `shell/pnpm-lock.yaml pins ${appBuilderKeys.length} app-builder-lib versions (${appBuilderKeys.join(', ')}); §2.5's toolchain claim is about one`)
  const pinnedAppBuilder = appBuilderKeys[0]
  const version = pinnedAppBuilder.slice('app-builder-lib@'.length)

  const stores = toolchainSearchDirs()

  const packageDir = stores
    .map((store) => storeDirectoryFor(store, 'app-builder-lib', version))
    .find((dir) => dir !== null)

  if (packageDir === undefined || packageDir === null) {
    notRun(
      'the toolchain declaration against §2.5',
      `no installed app-builder-lib@${version} to read (searched ${stores.join(', ')}; LABCAIRN_LICENCE_APP_BUILDER_LIB names a package directory): shell.yml installs no node_modules and downloads no toolchain`,
    )
    return
  }
  ran('the toolchain declaration against §2.5')

  const declarations = toolchainDeclarations([packageDir])
  assert.ok(
    declarations.length > 0,
    `app-builder-lib@${version} at ${packageDir} declares no NSIS bundle via getBinFromUrl, so §2.5's bundle names have no toolchain to be checked against`,
  )
  // The declaration has to be the one the *lock pins*. The store directory's
  // name is not proof of that (a `node_modules` link points elsewhere), so the
  // package states it: its own manifest names itself and its version.
  const manifest = JSON.parse(fs.readFileSync(path.join(packageDir, 'package.json'), 'utf8'))
  assert.equal(manifest.name, 'app-builder-lib', `the declaration was read from ${packageDir}, whose package.json names ${manifest.name}`)
  assert.equal(manifest.version, version, `the declaration was read from app-builder-lib ${manifest.version}, but shell/pnpm-lock.yaml pins ${pinnedAppBuilder}`)

  const problems = toolchainRecordProblems(RECORDS, declarations)
  for (const problem of problems) {
    assert.fail(`${problem} (pinned ${pinnedAppBuilder} via ${pinnedBuilder.join(', ')})`)
  }

  // The archive the build keeps must be the archive the checksum it pinned says
  // it is: a bundle swapped under the same name is exactly the change §2.5's
  // per-binary records would not notice.
  const archiveProblems = []
  for (const declaration of declarations) {
    if (!CACHE.available) break
    const archives = [...CACHE.bundles.values()]
      .flat()
      .flatMap((dir) => bundleFiles(path.dirname(dir)))
      .filter((file) => path.basename(file) === declaration.archive)
    if (archives.length === 0) continue
    for (const archive of archives) {
      const print = fingerprint(archive)
      if (print.sha256 !== declaration.checksum) {
        archiveProblems.push(
          `${declaration.archive} is sha256 ${print.sha256} but electron-builder asks for ${declaration.checksum}`,
        )
      }
    }
  }
  assert.deepEqual(archiveProblems, [], archiveProblems.join('; '))
})

// ---------------------------------------------------------------------------
// 5. The obligation record and the artefact agree about what the artefact carries.
// ---------------------------------------------------------------------------
test('§2.5.1\'s record of what the installer carries matches what the extract carries', () => {
  if (EXTRACT_DIRS.length === 0) {
    notRun('the installer extract against §2.5.1', EXTRACT_REASON)
    return
  }
  ran('the installer extract against §2.5.1')

  const members = extractMembers(EXTRACT_DIRS)
  assert.ok(members.length > 0, `the extract at ${EXTRACT_DIRS.join(', ')} holds no members`)

  const section = noticeSubsection(NOTICE_TEXT, '2.5.1').join('\n')
  const claimsCarry = /\*\*The licence text and the notice \(§1, §6\) — DONE\.\*\*/.test(section)
  const claimsAbsent = /The licence text and the notice \(§1, §6\) — NOT DONE/.test(section)
  assert.ok(
    claimsCarry !== claimsAbsent,
    '§2.5.1 states neither "the licence text and the notice — DONE" nor "— NOT DONE", so there is no recorded state to compare the artefact with',
  )

  const licenceMembers = members.filter((member) => isLicenceDocument(member))
  const lgplRecords = RECORDS.filter((record) => /LGPL/i.test(record.fields.licence ?? ''))
  assert.equal(lgplRecords.length, 2, `§2.5 records ${lgplRecords.length} LGPL binaries; §2.5.1's obligations are written for two`)

  const carryingLicenceText = licenceMembers.length > 0
  if (claimsCarry) {
    assert.ok(
      carryingLicenceText,
      '§2.5.1 records the licence-text obligation as DONE, but the extract carries no licence document — the record claims something the artefact does not',
    )
    const texts = licenceMembers.map((member) => fs.readFileSync(member.path, 'utf8'))
    for (const record of lgplRecords) {
      assert.ok(
        texts.some((text) => /GNU LESSER GENERAL PUBLIC LICENSE/i.test(text)),
        `§2.5.1 records the licence text as carried, but no carried document is the GNU LGPL text §2.5.1 quotes (§2.5.1's obligations are for ${lgplRecords.map((r) => r.name).join(' and ')})`,
      )
    }
  } else {
    assert.equal(
      licenceMembers.length,
      0,
      `§2.5.1 records the licence-text obligation as NOT DONE, but the extract carries ${licenceMembers.length} licence document(s): ${licenceMembers.map((m) => m.member).join(', ')} — the record is behind the artefact, and §2.5.1 has to be re-measured against it`,
    )
  }

  // §2.5.1's own member census: "the NSIS archive lists ten members and none of
  // them is a licence document". Watched against the extract §5.4 produces.
  // §2.5.1's own member census, watched against the extract §5.4 produces:
  // "the NSIS archive lists **ten** members … the seven plug-in DLLs,
  // `modern-wizard.bmp` and `app-64.7z` under `$PLUGINSDIR`, plus the
  // uninstaller executable at `$R0`". The extract §5.4 step 3 produces is the
  // archive's members, so the $PLUGINSDIR count is checkable and the eight
  // §2.5 binaries have to be among them.
  const pluginsdir = members.filter((member) => member.member.startsWith('$PLUGINSDIR/'))
  const pluginDlls = pluginsdir.filter((member) => /\.dll$/i.test(member.member))
  assert.equal(
    pluginDlls.length,
    7,
    `§2.5.1 counts seven plug-in DLLs under $PLUGINSDIR; the extract presents ${pluginDlls.length} (${pluginDlls.map((m) => path.basename(m.member)).join(', ')})`,
  )
  assert.equal(
    pluginsdir.length,
    10 - 1,
    `§2.5.1 counts ten members for the NSIS archive (the seven plug-ins, modern-wizard.bmp and app-64.7z under $PLUGINSDIR, plus the uninstaller at $R0); the extract's $PLUGINSDIR holds ${pluginsdir.length} members (${pluginsdir.map((m) => path.basename(m.member)).join(', ')})`,
  )
  assert.deepEqual(
    pluginsdir.filter((member) => isLicenceDocument(member)).map((member) => member.member),
    [],
    'a licence document sits under $PLUGINSDIR while §2.5.1 records that none of the archive\'s members is one — the record and the artefact disagree about what the installer carries',
  )

  // The binaries §2.5 names are really inside the extract, with the bytes §2.5 records.
  const mismatches = []
  for (const record of RECORDS) {
    const member = members.find(
      (candidate) => path.basename(candidate.member).toLowerCase() === record.name.toLowerCase(),
    )
    if (!member) {
      mismatches.push(`${record.name} is in §2.5 but not in the extract`)
      continue
    }
    if (member.sha256 !== record.fields.sha256) {
      mismatches.push(`${record.name}: the extract's copy is ${member.sha256.slice(0, 16)}… and §2.5 records ${record.fields.sha256?.slice(0, 16)}…`)
    }
  }
  assert.deepEqual(mismatches, [], mismatches.join('; '))

  // The binaries carry no licence statement, which is what §2.5's `where` field
  // says and what makes the obligation land on the distributor rather than on
  // the file. Checked by looking for what would falsify it.
  const withStatements = []
  for (const record of lgplRecords) {
    const member = members.find(
      (candidate) => path.basename(candidate.member).toLowerCase() === record.name.toLowerCase(),
    )
    if (!member) continue
    const hits = binaryCarriesLicenceStatement(member.path, ['lgpl', 'lesser general public', 'gnu general public', 'LoRd_MuldeR'])
    if (hits.length > 0) withStatements.push(`${record.name} carries ${hits.join(', ')}`)
  }
  assert.deepEqual(
    withStatements,
    [],
    `${withStatements.join('; ')} — §2.5 says "the compiled binary carries no licence text" and §2.5.1 measures it; a binary that does carry one changes where the obligation lands`,
  )
})

// ---------------------------------------------------------------------------
// 6. The unmeasured arms say so.
// ---------------------------------------------------------------------------
test('an arm that could not look says NOT RUN with a reason, and the sentinel is the probe\'s own answer', () => {
  assert.ok(RUN_LOG.length > 0, 'no arm reported anything, so this file measured nothing at all')
  const silent = RUN_LOG.filter((entry) => !entry.startsWith('RAN ') && !entry.startsWith('NOT RUN '))
  assert.deepEqual(silent, [], `these arms reported a state that is neither RAN nor NOT RUN: ${silent.join('; ')}`)
  const unexplained = RUN_LOG.filter((entry) => entry.startsWith('NOT RUN ') && !entry.includes(': '))
  assert.deepEqual(unexplained, [], `these arms say NOT RUN without naming a reason: ${unexplained.join('; ')}`)

  // The sentinel is not a sentence this file writes about itself: it is what the
  // probe answers when there is nothing to read, and this case asks the probe.
  // A `NOT RUN` no probe would produce is a sentence, and a sentence a witness
  // asserts about itself is the kind that survives the probe being switched off.
  const absent = findCacheBundles(path.join(os.tmpdir(), `labcairn-no-such-cache-${process.pid}`))
  assert.equal(absent.available, false, 'findCacheBundles reported a cache where there is none')
  assert.equal(absent.bundles.size, 0, 'a missing cache reported bundles it could not have read')
  const absentToolchain = toolchainDeclarations([path.join(os.tmpdir(), `labcairn-no-such-package-${process.pid}`)])
  assert.deepEqual(absentToolchain, [], 'the toolchain reader found a declaration in a directory that does not exist')

  // An arm whose probe answered "nothing there" must not also be logged as RAN.
  const ranWithoutEvidence = RUN_LOG.filter((entry) => entry.startsWith('RAN ')).filter((entry) => {
    if (/bundle bytes|bundle\'s|bundles|NSIS COPYING|unresolved/.test(entry)) return !CACHE.available
    if (/extract/.test(entry)) return EXTRACT_DIRS.length === 0
    return false
  })
  assert.deepEqual(
    ranWithoutEvidence,
    [],
    `these arms logged RAN while their probe had nothing to read: ${ranWithoutEvidence.join('; ')}`,
  )
})

// ---------------------------------------------------------------------------
// The controls: the properties this file watches, broken on copies of the data.
// ---------------------------------------------------------------------------
test('the controls fail for the properties: a swapped binary, a drifted size, an unrecorded binary, a bundle the toolchain does not fetch', () => {
  // The controls hand the *same comparison functions the tests above use* data
  // with one value changed. The fixture is built here rather than read from an
  // artefact, which is what makes the controls runnable on a machine the
  // artefacts do not exist on — and a control that only runs where the artefact
  // does is a control that never runs on the gate. The fixture is the eight
  // §2.5 records' own hashes and sizes, which stands for "the artefact is
  // exactly as §2.5 records it": the state the witness passes in, so a control
  // that reddens it reddens the property and not the fixture's shape.
  const artefact = new Map(
    RECORDS.map((record) => [
      record.name.toLowerCase(),
      [{ path: record.name, bytes: record.bytes, sha256: record.fields.sha256 }],
    ]),
  )

  // (a) A plug-in replaced by another build: the name and the size survive, the
  //     bytes do not. This is the change §2.5's own records would not notice.
  const swapped = structuredClone(RECORDS)
  const target = swapped.find((record) => record.name === 'StdUtils.dll')
  assert.ok(target, '§2.5 records no StdUtils.dll, so this control has nothing to swap')
  const clean = binaryRecordProblems(structuredClone(RECORDS), artefact)
  assert.deepEqual(clean, [], 'the unmutated records already fail the comparison, so this control proves nothing')
  target.fields.sha256 = 'f'.repeat(64)
  const afterSwap = binaryRecordProblems(swapped, artefact)
  assert.equal(afterSwap.length, 1, `a swapped sha256 produced ${afterSwap.length} problems, not 1: ${afterSwap.join('; ')}`)
  assert.match(afterSwap[0], /StdUtils\.dll/, `the problem names the wrong binary: ${afterSwap[0]}`)
  // The size still matches, which is the point: only the hash can see this change.
  assert.equal(afterSwap[0].includes('bytes'), false, `the swapped-hash problem talks about bytes: ${afterSwap[0]}`)

  // (a2) A plug-in §2.5 records that the bundle does not hold at all.
  const absentBundle = new Map(artefact)
  absentBundle.delete('stdutils.dll')
  const afterAbsence = binaryRecordProblems(structuredClone(RECORDS), absentBundle)
  assert.equal(afterAbsence.length, 1, `a missing binary produced ${afterAbsence.length} problems: ${afterAbsence.join('; ')}`)
  assert.match(afterAbsence[0], /holds no file of that name/, afterAbsence[0])

  // (b) A byte count that drifted from the real file.
  const drifted = structuredClone(RECORDS)
  const sized = drifted.find((record) => record.name === 'nsis7z.dll')
  assert.ok(sized, '§2.5 records no nsis7z.dll')
  const realBytes = sized.bytes
  sized.bytes = realBytes + 1
  const afterSize = binaryRecordProblems(drifted, artefact)
  assert.equal(afterSize.length, 1, `a drifted byte count produced ${afterSize.length} problems, not 1: ${afterSize.join('; ')}`)
  assert.match(
    afterSize[0],
    new RegExp(`${sized.bytes} bytes but the real file is ${realBytes}`),
    `the size problem does not name both numbers: ${afterSize[0]}`,
  )

  // (c) A binary carried by the artefact that no record names, and a record
  //     naming a binary the artefact does not carry.
  const stdUtilsSha = artefact.get('stdutils.dll')[0].sha256
  const members = [
    { member: '$PLUGINSDIR/StdUtils.dll', sha256: stdUtilsSha },
    { member: '$PLUGINSDIR/Intruder.dll', sha256: 'a'.repeat(64) },
  ]
  const carried = memberRecordProblems(members, structuredClone(RECORDS))
  assert.deepEqual(carried.unrecorded, ['intruder.dll'], `an unrecorded binary was not reported: ${JSON.stringify(carried)}`)
  // The other side of the same comparison: an artefact that carries two of the
  // eight makes the other seven records name binaries the artefact does not
  // carry. Both directions are the property, and a function that only reported
  // one of them would let a §2.5 that grew past the artefact, or an artefact that
  // shrank past §2.5, pass.
  assert.deepEqual(
    carried.missing,
    RECORDS.map((record) => record.name.toLowerCase()).filter((name) => name !== 'stdutils.dll').sort(),
    `the "§2.5 records a binary the artefact does not carry" side reported the wrong set: ${carried.missing.join(', ')}`,
  )
  const complete = memberRecordProblems(
    RECORDS.map((record) => ({ member: `$PLUGINSDIR/${record.name}`, sha256: artefact.get(record.name.toLowerCase())[0].sha256 })),
    structuredClone(RECORDS),
  )
  assert.deepEqual(complete, { unrecorded: [], missing: [] }, 'the unmutated artefact/record pair did not compare clean, so these controls prove nothing')

  // A record dropped from §2.5 while the artefact still carries the binary: the
  // artefact side reports it as unrecorded, which is m03's shape.
  const dropped = structuredClone(RECORDS).filter((record) => record.name !== 'StdUtils.dll')
  const allEight = RECORDS.map((record) => ({
    member: `$PLUGINSDIR/${record.name}`,
    sha256: artefact.get(record.name.toLowerCase())[0].sha256,
  }))
  const afterDrop = memberRecordProblems(allEight, dropped)
  assert.deepEqual(afterDrop.unrecorded, ['stdutils.dll'], `a record §2.5 dropped was not reported as unrecorded: ${JSON.stringify(afterDrop)}`)
  assert.deepEqual(afterDrop.missing, [], `dropping a record made other records go missing: ${afterDrop.missing.join(', ')}`)

  // (d) §2.5 naming a bundle the toolchain does not fetch.
  const declarations = [
    { bundle: 'nsis-3.0.4.1', archive: 'nsis-3.0.4.1.7z', checksum: '9'.repeat(64), declaredIn: 'x' },
    { bundle: 'nsis-resources-3.4.1', archive: 'nsis-resources-3.4.1.7z', checksum: '8'.repeat(64), declaredIn: 'x' },
  ]
  assert.deepEqual(toolchainRecordProblems(structuredClone(RECORDS), declarations), [], 'the real records disagree with a toolchain that names both bundles')
  const renamed = structuredClone(RECORDS)
  renamed.find((record) => record.name === 'nsis7z.dll').fields.bundle = 'nsis-resources-9.9.9'
  const afterRename = toolchainRecordProblems(renamed, declarations)
  assert.equal(afterRename.length, 1, `a bundle name the toolchain does not declare produced ${afterRename.length} problems: ${afterRename.join('; ')}`)
  assert.match(afterRename[0], /nsis-resources-9\.9\.9/, `the problem does not name the bundle: ${afterRename[0]}`)

  // (e) The toolchain reader's own answer on a tree that holds nothing is an
  //     empty list, which is the only thing that makes "the toolchain declares
  //     no NSIS bundle" a measurement rather than a guess.
  const nowhere = toolchainDeclarations([path.join(os.tmpdir(), `labcairn-no-package-${process.pid}`)])
  assert.deepEqual(nowhere, [], 'the toolchain reader found a declaration in a directory that does not exist')

  // (f) The reader the controls feed is the reader the tests use, on data the
  //     real bundles produce — when the bundles are there. A control whose
  //     fixture is nothing like the real artefact proves the fixture.
  const real = findCacheBundles(CACHE_DIR)
  if (real.available) {
    const fingerprints = filesByName('nsis-resources-3.4.1')
    assert.ok(fingerprints.size > 0, 'the real nsis-resources-3.4.1 bundle presented no files')
    const recorded = RECORDS.find((record) => record.name === 'StdUtils.dll')
    const actual = fingerprints.get('stdutils.dll') ?? []
    assert.ok(
      actual.some((print) => print.sha256 === recorded.fields.sha256 && print.bytes === recorded.bytes),
      'the real bundle does not present the sha256 and size §2.5 records, so the control\'s fixture and the artefact are describing different files',
    )
  }

  // (g) A reader that cannot look reports that, rather than finding nothing and
  //     calling it clean.
  const empty = findCacheBundles(path.join(os.tmpdir(), `labcairn-no-cache-${process.pid}`))
  assert.equal(empty.available, false, 'findCacheBundles reported a cache where there is none')
  assert.equal(empty.bundles.size, 0, 'a missing cache reported bundles')

  // (e) The extract member scan finds a licence document when one is there —
  //     including one whose *name* says nothing and whose text says everything.
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'labcairn-licence-scan-'))
  try {
    fs.mkdirSync(path.join(scratch, '$PLUGINSDIR'), { recursive: true })
    fs.writeFileSync(path.join(scratch, '$PLUGINSDIR', 'System.dll'), 'not a licence')
    fs.writeFileSync(
      path.join(scratch, '$PLUGINSDIR', 'COPYING.txt'),
      'GNU LESSER GENERAL PUBLIC LICENSE — this library is licensed under the LGPL.',
    )
    // The name this project would actually ship the obligation text under.
    fs.writeFileSync(
      path.join(scratch, '$PLUGINSDIR', 'LGPL.txt'),
      'GNU LESSER GENERAL PUBLIC LICENSE\nVersion 2.1, February 1999\n',
    )
    // An innocuous name, unmistakable contents: what a name-only pattern misses.
    fs.writeFileSync(
      path.join(scratch, '$PLUGINSDIR', 'notes-341.bin.txt'),
      'GNU LESSER GENERAL PUBLIC LICENSE\nVersion 2.1, February 1999\n',
    )
    // A compiled member that mentions the phrase deeper in is not a document.
    fs.writeFileSync(
      path.join(scratch, '$PLUGINSDIR', 'blob.dll'),
      `${'A'.repeat(4200)}GNU LESSER GENERAL PUBLIC LICENSE`,
    )
    const members = extractMembers([scratch])
    assert.equal(members.length, 5, `the extract scan found ${members.length} of the 5 members it was given`)
    const documents = members.filter((member) => isLicenceDocument(member)).map((member) => member.member).sort()
    assert.deepEqual(
      documents,
      ['$PLUGINSDIR/COPYING.txt', '$PLUGINSDIR/LGPL.txt', '$PLUGINSDIR/notes-341.bin.txt'],
      'the licence-document scan did not identify the licence documents it was given, so §2.5.1\'s "none of them is a licence document" is not a measured absence',
    )
    assert.equal(
      licenceDocumentKind(path.join(scratch, '$PLUGINSDIR', 'blob.dll')),
      null,
      'the scan read a licence phrase buried 4,200 bytes into a compiled member as a licence document — the absence §2.5.1 records would be unfalsifiable and also unmeasurable',
    )
    assert.equal(
      licenceDocumentKind(path.join(scratch, '$PLUGINSDIR', 'System.dll')),
      null,
      'the scan called a member with no licence content a licence document',
    )
    assert.deepEqual(
      binaryCarriesLicenceStatement(path.join(scratch, '$PLUGINSDIR', 'COPYING.txt'), ['lgpl', 'lesser general public']),
      ['lgpl', 'lesser general public'],
      'the binary licence-statement scan missed a statement written in plain text, so §2.5.1\'s grep is not a measurement',
    )
    assert.deepEqual(
      binaryCarriesLicenceStatement(path.join(scratch, '$PLUGINSDIR', 'System.dll'), ['lgpl']),
      [],
      'the scan reported a licence statement in a file that has none — the absence §2.5 records would be unmeasurable',
    )
  } finally {
    fs.rmSync(scratch, { recursive: true, force: true })
  }
})
