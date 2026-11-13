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
 * (`${ELECTRON_BUILDER_CACHE}/nsis-3.0.4.1`, `…/nsis-resources-3.4.1`), the
 * installer's `7z l` member list, and — where one can be produced — an extract.
 * This file hashes the real bytes in those bundles and compares. A third source
 * is `app-builder-lib`'s own `getBinFromUrl` declaration — the bundle names and
 * checksums the build asks its downloader to verify — which is what ties "the
 * bundle §2.5 names" to "the bundle this version of electron-builder fetches":
 * bump `electron-builder` and the plug-ins move to a newer bundle, and the
 * declaration changes.
 *
 * **The listing is the source the installer arms actually use.** `$PLUGINSDIR` is
 * an installation-time temporary directory, and 7-Zip's NSIS handler lists its
 * members without extracting them: a re-review measured a plain `7za x`, `-spf`
 * and `e '$PLUGINSDIR\*'` against the 2026-11-11 build, and none produced those
 * plug-ins. The first version of this witness waited for an extract, so two arms
 * could only ever report `NOT RUN`. A `7z l` of the installer gives the member
 * names, their compressed sizes (the numbers §5.4 step 2 prints) and the absence
 * or presence of a licence-document name -- everything §2.5.1's ten-member census
 * and its licence-text obligation need. The 7-Zip version matters: 26.02 (x64)
 * reports `Type = Nsis` and lists the plug-ins; the 24.09 (x86) binary
 * electron-builder caches reports `Type = 7z` and lists only the outer payload.
 * An extract, where one exists, is an optional strengthening: it adds the
 * per-member sha256 and compiled-binary statement arms.
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
import { spawnSync } from 'node:child_process'
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
  extractCoverage,
  extractMembers,
  findCacheBundles,
  fingerprint,
  isLicenceDocument,
  licenceDocumentKind,
  licenceDocumentsIn,
  carriedLicenceTextProblems,
  compressedSizeTable,
  licenceTextClaims,
  licenceTextCountClaim,
  licenceTextFileProblems,
  listedCensusProblems,
  listedLicenceDocuments,
  listedSizeProblems,
  obligationStates,
  memberRecordProblems,
  termsSourceProblems,
  termsSources,
  upstreamHashProblems,
  parseInstallerListing,
  recordLayer,
  storeDirectoryFor,
  toolchainDeclarations,
  toolchainRecordProblems,
} from '../../.github/installer-binaries.mjs'
import { lockfileKeys } from '../../.github/shell-lockfile-keys.mjs'
import { shellPaths } from '../scripts/lib/shell-paths.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SHELL_ROOT = path.resolve(HERE, '..')
const REPO_ROOT = path.resolve(SHELL_ROOT, '..')

// The override exists for the mutation checks: a witness that can only be shown
// to fail by editing a tracked file is a witness whose mutation checks leave the
// tree dirty. Every §2.5 reader in this file reads NOTICE_TEXT, so one override
// moves the whole record while the artefacts stay untouched.
const NOTICE_TEXT = readNotice(process.env.LABCAIRN_LICENCE_NOTICE ?? undefined)
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

/**
 * The installer's own `7z l` listing, the third source.
 *
 * `$PLUGINSDIR` is an installation-time temporary directory: 7-Zip's NSIS handler
 * can list its members but does not extract them. Measured here with three `7za`
 * invocations against the 2026-11-11 build: a plain `x` yields only the payload,
 * `-spf` the same, and `e '$PLUGINSDIR\*'` reports `Files: 0`. So an extract of
 * those plug-ins is not an artefact any machine can produce by unpacking, and a
 * witness that waits for one has arms that can never run. The **listing** is
 * obtainable wherever the installer is, and it carries the member names, the
 * compressed sizes and the absence/presence of licence documents -- which is
 * exactly what §2.5.1's ten-member census and obligation record need.
 *
 * `LABCAIRN_LICENCE_INSTALLER_LISTING` names one or more saved `7z l` outputs
 * (`path.delimiter`-separated, the same shape as the extract variable): typically
 * one of the NSIS installer itself and one of its payload. A caller with a live
 * installer but no saved log can run §5.4 step 2 (`7z l "<installer>"`) and name
 * the result. An explicit `LABCAIRN_LICENCE_INSTALLER` names the exe and the
 * witness runs `7za l` itself, where a 7za is findable.
 */
const LISTING_PATHS = (process.env.LABCAIRN_LICENCE_INSTALLER_LISTING ?? '')
  .split(path.delimiter)
  .filter((entry) => entry.length > 0 && fs.existsSync(entry))

/**
 * The 7-Zip binaries worth trying when given a live installer.
 *
 * The version matters: system 7-Zip 26.02 (x64) reports `Type = Nsis` and lists
 * the nine `$PLUGINSDIR` members plus the uninstaller, while the 24.09 (x86)
 * binary electron-builder caches reports `Type = 7z` and lists only the outer
 * payload. `parseInstallerListing` returns the type with the members, so a
 * listing of the wrong layer is reported rather than mistaken for a short
 * installer. The environment variable is first because this machine's
 * `ELECTRON_BUILDER_CACHE` points at a different cache tree than the one the
 * evidence directories were built from.
 */
function sevenZipCandidates() {
  const roots = [
    process.env.LABCAIRN_LICENCE_7Z ?? '',
    process.env.ELECTRON_BUILDER_CACHE ?? '',
    path.join(shellPaths({ here: HERE }).checkoutRoot, '.local', 'cache', 'electron-builder'),
    'C:\\Program Files\\7-Zip',
    'E:\\labcairn-local\\cache\\electron-builder',
  ].filter(Boolean)
  const candidates = []
  for (const root of roots) {
    const direct = path.join(root, '7z.exe')
    if (fs.existsSync(direct)) candidates.push(direct)
    const sevenZipDir = path.join(root, '7zip@1.0.0')
    if (!fs.existsSync(sevenZipDir)) continue
    for (const entry of fs.readdirSync(sevenZipDir, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue
      for (const name of ['7za.exe', '7z.exe']) {
        const file = path.join(sevenZipDir, entry.name, 'bin', name)
        if (fs.existsSync(file)) candidates.push(file)
      }
    }
  }
  return [...new Set(candidates)]
}

/**
 * Read every available listing, from saved logs and — when an installer is named
 * — from `7za l` run here. `spawnSync` is the shape this file already uses for
 * nothing else, but a listing is a read-only command with no side effects and its
 * stdout is the artefact; a failed invocation is reported in `failures` rather
 * than silently shrinking the member set.
 */
function installerListings() {
  const texts = []
  const failures = []
  for (const file of LISTING_PATHS) {
    try {
      texts.push({ source: file, text: fs.readFileSync(file, 'utf8') })
    } catch (error) {
      failures.push(`${file}: ${String(error?.message ?? error)}`)
    }
  }
  const exe = process.env.LABCAIRN_LICENCE_INSTALLER
  if (exe && fs.existsSync(exe)) {
    const tried = []
    let produced = false
    for (const sevenZip of sevenZipCandidates()) {
      const result = spawnSync(sevenZip, ['l', exe], { encoding: 'utf8', timeout: 120_000 })
      const parsed = result.stdout ? parseInstallerListing(result.stdout) : null
      const isNsis = parsed?.type?.toLowerCase() === 'nsis'
        && parsed.members.some((member) => member.member.startsWith('$PLUGINSDIR/'))
      tried.push(`${sevenZip} status=${result.status ?? result.error?.message} type=${parsed?.type ?? 'none'}`)
      if (result.status === 0 && result.stdout) {
        texts.push({ source: `${sevenZip} l ${exe}`, text: result.stdout })
        // The outer 7z payload is a listing too, and §2.5 names `elevate.exe`
        // inside it, so both layers are kept. But only an NSIS-layer listing
        // satisfies the installer itself: a 24.09 (x86) 7za that reports
        // `Type = 7z` has not listed the plug-ins, and the next candidate must
        // be tried rather than accepted as a short installer.
        if (isNsis) produced = true
        if (isNsis && parsed.members.some((member) => member.member.startsWith('resources/'))) break
      }
    }
    if (!produced) {
      failures.push(`no 7za produced an NSIS-layer listing for ${exe}; tried ${tried.join(' | ') || 'no 7za found'}`)
    }
  }
  const parsed = texts.map(({ source, text }) => ({ source, ...parseInstallerListing(text) }))
  return { listings: parsed, failures }
}

const INSTALLER = installerListings()

/** The NSIS-layer listings: those whose archive type is Nsis and which name the plug-ins. */
function nsisListings() {
  return INSTALLER.listings.filter(
    (listing) => listing.type?.toLowerCase() === 'nsis'
      && listing.members.some((member) => member.member.startsWith('$PLUGINSDIR/')),
  )
}

/** All archived members, from every layer, deduplicated by member name. */
function listedMembers() {
  const found = new Map()
  for (const listing of INSTALLER.listings) {
    for (const member of listing.members) {
      if (!found.has(member.member.toLowerCase())) found.set(member.member.toLowerCase(), member)
    }
  }
  return [...found.values()]
}

const CACHE = findCacheBundles(CACHE_DIR)

/**
 * Where the *upstream* provenance lives, as distinct from the bundle the build
 * downloads. `nsis-resources-3.4.1` carries no licence document; the terms for
 * UAC.dll and WinShell.dll come from NSIS 3.13's `LICENSES` tree and from the
 * upstream release archives themselves. §2.5 quotes short sha256 values for
 * both, and this is the source that can confirm those bytes.
 *
 * `LABCAIRN_LICENCE_UPSTREAM_DIR` names one or more directories, separated by
 * `path.delimiter`. It is an override like the other artefact variables: the
 * upstream release is not part of the checkout, and a runner that has none of it
 * reports the hash arm as NOT RUN rather than pretending to have measured it.
 */
const UPSTREAM_DIRS = (process.env.LABCAIRN_LICENCE_UPSTREAM_DIR ?? '')
  .split(path.delimiter)
  .filter((entry) => entry.length > 0 && fs.existsSync(entry))

const NO_LISTING_REASON =
  'no installer listing or extract (LABCAIRN_LICENCE_INSTALLER_LISTING names saved `7z l` '
  + 'output, LABCAIRN_LICENCE_INSTALLER names the exe to list, and '
  + 'LABCAIRN_LICENCE_INSTALLER_EXTRACT names an unpacked extract)'

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
  // The listing is the source that is actually obtainable: `$PLUGINSDIR` is an
  // installation-time temporary directory, and 7-Zip's NSIS handler lists its
  // members without extracting them. An extract, when one exists, is an optional
  // strengthening -- it adds the sha256 arm below -- not a prerequisite. Waiting
  // for one left this case NOT RUN on every machine, which is the gap a re-review
  // found and this change closes.
  const listings = nsisListings()
  const listed = listedMembers()
  const extracted = EXTRACT_DIRS.length ? extractMembers(EXTRACT_DIRS) : []
  const COVERAGE = extractCoverage(extracted)
  // Any layer is evidence. A caller with only the payload's `7z l` output can
  // still measure §2.5's `elevate.exe` record; requiring the NSIS layer here was
  // the last shape of "an arm that could not look" -- it reported no source at all
  // while a real listing named the member it needed. The per-layer sentinel below
  // says which layer was not measured.
  if (listed.length === 0 && extracted.length === 0) {
    notRun('the installer\'s binaries against §2.5\'s eight names', NO_LISTING_REASON)
    return
  }
  ran(`the installer's binaries against §2.5's eight names (${listed.length} listed member(s), ${extracted.length} extracted member(s))`)

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
  const inScope = [
    ...listed.filter((member) => /^\$PLUGINSDIR\/|^resources\//.test(member.member)),
    ...extracted.filter((member) => /^\$PLUGINSDIR\/|^resources\//.test(member.member)),
  ]
  const binaries = inScope
    .filter((member) => /\.(dll|exe)$/i.test(member.member))
    // The payload's Electron runtime DLLs (ffmpeg.dll, d3dcompiler_47.dll, …)
    // are §2.4.1's surface, and §2.5 says so. §2.5 claims to enumerate the
    // seven plug-ins in `$PLUGINSDIR` and `elevate.exe` in `resources/`, so only
    // those two groups are in scope.
    .filter((member) => /^\$PLUGINSDIR\/[^/]+\.(dll|exe)$|^resources\/[^/]+\.(dll|exe)$/i.test(member.member))

  // §2.5's eight records span two different archives: seven plug-ins in the NSIS
  // installer's `$PLUGINSDIR`, and `elevate.exe` inside the payload. A `7z l` of
  // the installer lists the first layer only; the payload needs its own listing or
  // extract. Comparing all eight records against a single-layer listing reports
  // `elevate.exe` as missing -- a false red about NOTICE caused by an absent
  // source. Only the layers a source was actually available for are compared, and
  // the other one is reported as NOT RUN rather than called a finding.
  const layers = new Set()
  // A layer is measured when the source presents that layer's *binaries*. An
  // extract of `$PLUGINSDIR\licenses\` alone holds six licence texts and no
  // plug-in; counting it as evidence about the plug-ins would report that the
  // installer carries none of them.
  if (listings.length > 0 || COVERAGE.coversPlugins) layers.add('plugins')
  if (listings.some((listing) => listing.members.some((member) => member.member.startsWith('resources/')))
    || COVERAGE.coversPayload) layers.add('payload')
  const { unrecorded, missing } = memberRecordProblems(binaries, RECORDS, [...layers])
  for (const layer of ['plugins', 'payload']) {
    if (!layers.has(layer)) {
      notRun(`the installer's ${layer} layer against §2.5`, `no ${layer} listing or extract (§2.5 records ${layer === 'plugins' ? 'seven plug-ins in $PLUGINSDIR, named by an NSIS-layer 7z l' : 'elevate.exe in resources/, named by a payload-layer 7z l'}; the two are different archives)`)
    }
  }

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

  // The optional strengthening: where an extract really holds a member's bytes,
  // §2.5's sha256 has to be that member's hash. A listing has names and sizes but
  // no bytes, so this arm says what it did not measure if the extract is absent.
  if (extracted.length === 0) {
    notRun('the installer extract\'s per-member sha256 arm', 'no extract (a 7z listing names the members but does not carry their bytes; LABCAIRN_LICENCE_INSTALLER_EXTRACT names one)')
    return
  }
  ran('the installer extract\'s per-member sha256 arm')
  const mismatches = []
  for (const record of RECORDS) {
    const member = extracted.find(
      (candidate) => path.basename(candidate.member).toLowerCase() === record.name.toLowerCase(),
    )
    if (member && member.sha256 !== record.fields.sha256) {
      mismatches.push(`${record.name}: extract ${String(member.sha256).slice(0, 16)}… vs §2.5 ${record.fields.sha256?.slice(0, 16)}…`)
    }
  }
  assert.deepEqual(mismatches, [], mismatches.join('; '))
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

test('every named licence in the licence-less bundle names where its terms come from', () => {
  // **The invariant, not the count.** §2.5's four records from
  // `nsis-resources-3.4.1` all name a licence now: StdUtils through its own source
  // header, nsis7z through 7-Zip's terms, and UAC/WinShell through upstream NSIS
  // 3.13's `LICENSES` tree. A previous version of this case asserted "exactly
  // two", which went red the moment the record became more accurate. The number
  // is a measurement that may grow as upstream provenance is found; what must
  // hold is that a record naming a licence also names *where that licence comes
  // from*, and that the source is an upstream artefact rather than the bundle
  // itself -- which carries no licence file at all.
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

  const fromBundle = RECORDS.filter((record) => bundleNamedFromRecord(record) === 'nsis-resources-3.4.1')
  assert.ok(fromBundle.length > 0, '§2.5 names no binary from nsis-resources-3.4.1, so the source requirement has nothing to watch')

  // Every named licence records a source. `unresolved`, if any remain, is allowed
  // to have none -- that is what the word means.
  ran('§2.5\'s named licences against their stated sources')
  const sourceCheck = termsSourceProblems(fromBundle)
  assert.deepEqual(sourceCheck.problems, [], sourceCheck.problems.join('; '))
  assert.equal(sourceCheck.named, fromBundle.length - recordedUnresolved.length,
    `§2.5 names ${sourceCheck.named} licences and ${recordedUnresolved.length} unresolved entries; the two must account for every record from this bundle`)

  // The sources are two different artefacts and must not be conflated: the bundle
  // electron-builder downloads carries no licence document, while the NSIS 3.13
  // release tree does. A `where` field that pointed at the downloaded bundle for
  // UAC/WinShell would be citing a document this arm has just shown is absent.
  const nsis313 = fromBundle.filter((record) => /LICENSES|upstream NSIS/i.test(termsSources(record).text))
  assert.ok(nsis313.length > 0, 'no §2.5 record names upstream NSIS 3.13\'s LICENSES tree as a source; the UAC/WinShell grants have nowhere to be checked')
  for (const record of nsis313) {
    assert.doesNotMatch(
      termsSources(record).text,
      /nsis-resources-3\.4\.1[^\n]*\b(COPYING|LICENSE|licence document)\b/i,
      `${record.name}: §2.5 cites the downloaded bundle for its terms, but the bundle carries no licence document -- the two sources are different artefacts`,
    )
  }

  // The quoted short hashes, checked against the real upstream files where the
  // provenance tree is available. Where it is not, the arm says exactly what it
  // did not measure: the source-path requirement above still ran.
  const upstream = upstreamHashProblems(fromBundle, UPSTREAM_DIRS)
  if (!upstream.available) {
    notRun('§2.5\'s quoted upstream sha256 values against the real files',
      `no upstream NSIS 3.13 LICENSES tree or release archives (LABCAIRN_LICENCE_UPSTREAM_DIR names one, path.delimiter-separated); ${upstream.unmeasured.length} quoted hash(es) were not measured here: ${upstream.unmeasured.join(', ') || 'none'}`)
    return
  }
  ran('§2.5\'s quoted upstream sha256 values against the real files')
  assert.deepEqual(upstream.problems, [], upstream.problems.join('; '))
  assert.ok(upstream.matched.length > 0, 'the upstream tree was found but none of §2.5\'s quoted hashes were checked, so the hash arm measured nothing')
  const quoted = fromBundle.flatMap((record) => termsSources(record).hashes)
  assert.equal(upstream.matched.length, quoted.length,
    `§2.5 quotes ${quoted.length} short hash(es) and ${upstream.matched.length} were bound to real files upstream`)
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
test('§2.5.1\'s record of what the installer carries matches what the artefact carries', () => {
  // §2.5.1's member census and its licence-text obligation are claims about what
  // the *archive holds*: ten members, seven plug-in DLLs, and none of them a
  // licence document. 7-Zip's NSIS listing states all three (member names, their
  // compressed sizes, and the absence/presence of licence names), and it is the
  // source obtainable wherever the installer is. An extract -- which 7-Zip's NSIS
  // handler cannot produce for `$PLUGINSDIR` -- is an optional strengthening: it
  // adds the per-member sha256 and compiled-binary statement arms below.
  const nsis = nsisListings()
  const listed = listedMembers()
  const extracted = EXTRACT_DIRS.length ? extractMembers(EXTRACT_DIRS) : []
  const COVERAGE = extractCoverage(extracted)
  if (nsis.length === 0 && extracted.length === 0) {
    // A payload-only listing cannot check §2.5.1's NSIS-archive census: that
    // section is about the installer's own ten members, and the outer 7z payload
    // is a different archive. The reason says so rather than reporting no source.
    notRun('the installer listing against §2.5.1', listed.length > 0
      ? `no NSIS-layer listing (the ${listed.length} listed member(s) are from a \`Type = 7z\` payload listing, which is a different archive from the NSIS installer §2.5.1 counts)`
      : NO_LISTING_REASON)
    return
  }
  ran(`the installer listing against §2.5.1 (${nsis.length} NSIS listing(s), ${extracted.length} extracted member(s))`)

  const section = noticeSubsection(NOTICE_TEXT, '2.5.1').join('\n')
  // §2.5.1 is **three** separate obligation states, not one. The §1 text-and-
  // notice state is DONE or NOT DONE; the §4 corresponding-source state is
  // PARTLY DONE, NOT YET POINTED AT; replaceability is NOT MEASURED. Reading
  // `DONE`/`NOT DONE` across the whole section would let one bullet's word decide
  // an arm that is about the other bullet. The state is read from its own bullet,
  // and the other two are required to be present so the shape itself is watched.
  const states = obligationStates(NOTICE_TEXT)
  assert.ok(
    states.textAndNotice === 'DONE' || states.textAndNotice === 'NOT DONE',
    '§2.5.1 states neither "the licence text and the notice — DONE" nor "— NOT DONE" in its §1 bullet, so there is no recorded state to compare the artefact with',
  )
  assert.ok(
    states.correspondingSource && states.replaceability,
    '§2.5.1 no longer separates the §4 corresponding-source (PARTLY DONE) and §6(b) replaceability (NOT MEASURED) states from the §1 text-and-notice state; the three must not be read as one',
  )
  const claimsCarry = states.textAndNotice === 'DONE'
  const recordedTexts = licenceTextCountClaim(NOTICE_TEXT)
  assert.ok(
    recordedTexts !== null,
    '§2.5.1 states no count of licence texts for the NSIS archive ("six of them are the licence texts" / "none of them is a licence document"), so its text claim has nothing to compare with the listing',
  )
  // §2.5.1 writes the number out ("lists **ten** members"), not as a digit. A
  // pattern that asked for `\d+` read nothing out of a section that states its
  // census plainly, and the whole listing arm then reported itself as unreadable.
  // §2.5.1 wraps between the count and the word "members":
  //   "the NSIS archive lists **ten**\n    members and none of them …"
  // so the two words have to be allowed to sit on different lines.
  const census = /the NSIS archive lists \*\*(\w+)\*\*\s+members/.exec(section)
  assert.ok(census, '§2.5.1 states no member count for the NSIS archive, so its census has nothing to compare with')
  const MEMBER_COUNT_WORDS = {
    eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12, thirteen: 13,
    fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18,
    nineteen: 19, twenty: 20,
  }
  const recordedCensus = MEMBER_COUNT_WORDS[census[1].toLowerCase()]
  assert.ok(
    Number.isInteger(recordedCensus),
    `§2.5.1 states its archive has "**${census[1]}**" members, which is not a count this reader can compare: add the word to the vocabulary rather than guessing a number`,
  )

  const lgplRecords = RECORDS.filter((record) => /LGPL/i.test(record.fields.licence ?? ''))
  assert.equal(lgplRecords.length, 2, `§2.5 records ${lgplRecords.length} LGPL binaries; §2.5.1's obligations are written for two`)

  // The listing is the primary reader. Its `type` is part of the answer: an outer
  // `Type = 7z` payload listing (what a 24.09 x86 7za gives) is not the NSIS
  // archive §2.5.1 counts, and reporting it as such would turn a tooling
  // difference into a false ten-member discrepancy.
  if (nsis.length > 0) {
    ran('§2.5.1\'s census against the NSIS listing')
    const censusMembers = [
      ...nsis.flatMap((listing) => listing.members),
      ...listed.filter((member) => member.member.startsWith('resources/')),
    ]
    const seen = new Set()
    const unique = censusMembers.filter((member) => {
      const key = member.member.toLowerCase()
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    const documents = listedLicenceDocuments(unique)
    const problems = listedCensusProblems(unique, recordedCensus, claimsCarry, documents, recordedTexts)
    assert.deepEqual(problems, [], problems.join('; '))
    // §5.4's seven compressed sizes are a second statement about the same
    // archive, and `Packed Size` in the listing is the artefact's answer. They
    // are not §2.5's unpacked sizes, which is why the two must not be compared.
    ran('§5.4\'s compressed sizes against the NSIS listing')
    const sizes = compressedSizeTable(NOTICE_TEXT)
    assert.ok(sizes.size >= 7, `§5.4 prints ${sizes.size} compressed sizes; the section names seven plug-ins`)
    const sizeProblems = listedSizeProblems(unique, sizes)
    assert.deepEqual(sizeProblems, [], sizeProblems.join('; '))
  } else {
    notRun('§2.5.1\'s census against the NSIS listing', 'no NSIS-layer listing (the saved log is a `Type = 7z` payload listing, or none was named); the extract arm below is the only source')
  }

  // Where an extract really exists, its own member census agrees with the same
  // record, and the documents it holds are the ones the listing named.
  //
  // An extract is not the installer: it is whatever was unpacked. The 2026-11-12
  // build's `extract3` holds only `$PLUGINSDIR\licenses\` -- six texts and no
  // plug-in -- so the census arm below is measurable from it and the plug-in
  // census is not. Each arm says which.
  if (extracted.length > 0 && COVERAGE.coversPlugins) {
    ran('§2.5.1\'s census against the installer extract')
    const pluginsdir = extracted.filter((member) => member.member.startsWith('$PLUGINSDIR/'))
    const pluginDlls = pluginsdir.filter((member) => /\.dll$/i.test(member.member))
    assert.equal(
      pluginDlls.length,
      7,
      `§2.5.1 counts seven plug-in DLLs under $PLUGINSDIR; the extract presents ${pluginDlls.length} (${pluginDlls.map((m) => path.basename(m.member)).join(', ')})`,
    )
    assert.equal(
      pluginsdir.length,
      recordedCensus - 1,
      `§2.5.1 counts ${recordedCensus} NSIS-archive members: ${recordedCensus - 1} under $PLUGINSDIR plus the uninstaller at $R0. The extract's $PLUGINSDIR holds ${pluginsdir.length} — a member arriving there is either an unrecorded binary or a licence document the record has to speak about`,
    )
  } else if (extracted.length > 0) {
    notRun('§2.5.1\'s census against the installer extract', `the extract holds no plug-in binary (${COVERAGE.summary}), so §2.5.1's member census is not measurable from it`)
  } else {
    notRun('§2.5.1\'s census against the installer extract', 'no extract (a 7z listing names the members but does not carry their bytes)')
  }

  const licenceMembers = extracted.filter((member) => isLicenceDocument(member))
  if (licenceMembers.length > 0) {
    ran('§2.5.1\'s licence-text state against the installer extract')
    if (claimsCarry) {
      assert.ok(
        licenceMembers.length > 0,
        '§2.5.1 records the licence-text obligation as DONE, but the extract carries no licence document',
      )
      assert.equal(
        licenceMembers.length,
        recordedTexts,
        `§2.5.1 states ${recordedTexts} licence text(s) in the NSIS archive; the extract carries ${licenceMembers.length} (${licenceMembers.map((m) => path.basename(m.member)).join(', ')})`,
      )
      const texts = licenceMembers.map((member) => fs.readFileSync(member.path, 'utf8'))
      assert.ok(
        texts.some((text) => /GNU LESSER GENERAL PUBLIC LICENSE/i.test(text)),
        `§2.5.1 records the licence text as carried, but no carried document is the GNU LGPL text §2.5.1 quotes (obligations for ${lgplRecords.map((r) => r.name).join(' and ')})`,
      )
    } else {
      assert.equal(
        licenceMembers.length,
        0,
        `§2.5.1 records the licence-text obligation as NOT DONE, but the extract carries ${licenceMembers.length} licence document(s): ${licenceMembers.map((m) => m.member).join(', ')} — the record is behind the artefact, and §2.5.1 has to be re-measured against it`,
      )
    }
  } else {
    notRun('§2.5.1\'s licence-text state against the installer extract', 'no extract carrying licence texts (a 7z listing names the members but does not carry their bytes)')
  }

  // The optional byte-level arms: only where an extract holds the real bytes.
  if (extracted.length > 0 && COVERAGE.coversPlugins) {
    ran('the installer extract\'s per-member sha256 and compiled-binary statement arms')
    const mismatches = []
    const withStatements = []
    for (const record of RECORDS) {
      const member = extracted.find(
        (candidate) => path.basename(candidate.member).toLowerCase() === record.name.toLowerCase(),
      )
      if (!member) {
        mismatches.push(`${record.name} is in §2.5 but not in the extract`)
        continue
      }
      if (member.sha256 !== record.fields.sha256) {
        mismatches.push(`${record.name}: the extract's copy is ${member.sha256.slice(0, 16)}… and §2.5 records ${record.fields.sha256?.slice(0, 16)}…`)
      }
      if (/LGPL/i.test(record.fields.licence ?? '')) {
        const hits = binaryCarriesLicenceStatement(member.path, ['lgpl', 'lesser general public', 'gnu general public', 'LoRd_MuldeR'])
        if (hits.length > 0) withStatements.push(`${record.name} carries ${hits.join(', ')}`)
      }
    }
    assert.deepEqual(mismatches, [], mismatches.join('; '))
    assert.deepEqual(
      withStatements,
      [],
      `${withStatements.join('; ')} — §2.5 says "the compiled binary carries no licence text" and §2.5.1 measures it`,
    )
  } else {
    notRun('the installer extract\'s per-member sha256 and compiled-binary statement arms', extracted.length > 0
      ? `the extract holds no plug-in binary (${COVERAGE.summary}), so §2.5's eight binaries are not measurable from it`
      : 'no extract (a 7z listing carries names and sizes, not bytes)')
  }
})

// ---------------------------------------------------------------------------
// 6. The licence texts the installer carries are the repository's own files.
// ---------------------------------------------------------------------------
test('the licence texts the installer carries are the repository\'s own files, byte for byte', () => {
  // **What §2.5.1 claims.** "Extracting the archive and hashing the six members
  // gives the sha256s of the repository's six files -- five of the six are
  // recorded in `shell/licenses/`'s `README.txt`, the sixth being that README
  // itself, which cannot record its own hash."
  //
  // That is a claim about bytes, and it is the claim that discharges §1: the text
  // travelling with `StdUtils.dll` has to be *this tree's* text. Naming the six
  // files is not enough, and a count is not enough either.
  //
  // **Two arms, and the first one needs no artefact.** The repository's own
  // README records five hashes; the files in `shell/licenses/` must match them,
  // so a text edited without its README entry updated is caught even with no
  // installer on the machine. The second arm compares the bytes the artefact
  // carries with those files, and reports itself as not run where there is no
  // extract. `LABCAIRN_LICENCE_TEXT_DIR` names a different directory for the
  // mutation checks, so they can edit a copy instead of a tracked file.
  const LICENCES_DIR = process.env.LABCAIRN_LICENCE_TEXT_DIR ?? path.join(REPO_ROOT, 'shell', 'licenses')
  assert.ok(fs.existsSync(LICENCES_DIR), `the tree holds no shell/licenses/ directory, so the licence texts §2.5.1 names have no source here`)

  ran('shell/licenses/README.txt\'s recorded hashes against the files it names')
  const readmeText = fs.readFileSync(path.join(LICENCES_DIR, 'README.txt'), 'utf8')
  const claims = licenceTextClaims(readmeText)
  assert.ok(claims.size > 0, 'shell/licenses/README.txt records no hash for any file, so its entries are unchecked')
  const fileProblems = licenceTextFileProblems(claims, LICENCES_DIR)
  assert.deepEqual(fileProblems, [], fileProblems.join('; '))

  // §2.5.1 says five of the six are recorded and the sixth is the README itself,
  // which cannot record its own hash. A README that recorded nothing, or that
  // recorded only some, would leave files travelling without a stated hash.
  const repositoryFiles = fs.readdirSync(LICENCES_DIR).filter((name) => fs.statSync(path.join(LICENCES_DIR, name)).isFile())
  assert.equal(
    claims.size,
    repositoryFiles.length - 1,
    `shell/licenses/ holds ${repositoryFiles.length} file(s) and its README records ${claims.size} hash(es); §2.5.1 says five of the six are recorded and the sixth is the README itself, which cannot record its own hash`,
  )

  const extracted = EXTRACT_DIRS.length ? extractMembers(EXTRACT_DIRS) : []
  const carried = extracted.filter((member) => isLicenceDocument(member))
  if (carried.length === 0) {
    notRun('the carried licence texts against the repository\'s files', 'no extract carrying licence texts (LABCAIRN_LICENCE_INSTALLER_EXTRACT names one; the 2026-11-12 build writes them to $PLUGINSDIR\\licenses\\)')
    return
  }
  ran('the carried licence texts against the repository\'s files')
  const carriedProblems = carriedLicenceTextProblems(carried, LICENCES_DIR)
  assert.deepEqual(carriedProblems, [], carriedProblems.join('; '))
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
  // The probe for the two installer arms is now *either* an NSIS-layer listing or
  // an extract, not the extract alone: treating the listing as no evidence would
  // call a real measurement NOT RUN, which is the same class of mistake the
  // sibling re-review found in the original witness.
  const hasInstallerEvidence = listedMembers().length > 0 || EXTRACT_DIRS.length > 0
  const ranWithoutEvidence = RUN_LOG.filter((entry) => entry.startsWith('RAN ')).filter((entry) => {
    if (/bundle bytes|bundle\'s|bundles|NSIS COPYING|unresolved/.test(entry)) return !CACHE.available
    if (/installer listing|installer\'s binaries/.test(entry)) return !hasInstallerEvidence
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
  // Both members are in `$PLUGINSDIR`, so this is a plugins-layer-only source:
  // §2.5's `elevate.exe` record (payload layer) has no evidence here and must not
  // be reported as missing.
  const carried = memberRecordProblems(members, structuredClone(RECORDS), ['plugins'])
  assert.deepEqual(carried.unrecorded, ['intruder.dll'], `an unrecorded binary was not reported: ${JSON.stringify(carried)}`)
  // The other side of the same comparison: two of the seven plugin records are
  // carried, so the other five name binaries the artefact does not. Both
  // directions are the property, and a function that only reported one of them
  // would let a §2.5 that grew past the artefact, or an artefact that shrank past
  // §2.5, pass.
  assert.deepEqual(
    carried.missing,
    RECORDS.filter((record) => recordLayer(record) === 'plugins')
      .map((record) => record.name.toLowerCase()).filter((name) => name !== 'stdutils.dll').sort(),
    `the "§2.5 records a binary the artefact does not carry" side reported the wrong set: ${carried.missing.join(', ')}`,
  )
  // The fixture's members have to be in the layer §2.5's own `path` field names
  // for each record: seven plug-ins under `$PLUGINSDIR`, and `elevate.exe` under
  // `resources/`. Putting all eight in one layer is the false-red shape that a
  // single-layer 7z listing exposed, and the comparison now refuses it.
  const memberPath = (record) => `${recordLayer(record) === 'payload' ? 'resources' : '$PLUGINSDIR'}/${record.name}`
  const complete = memberRecordProblems(
    RECORDS.map((record) => ({ member: memberPath(record), sha256: artefact.get(record.name.toLowerCase())[0].sha256 })),
    structuredClone(RECORDS),
  )
  assert.deepEqual(complete, { unrecorded: [], missing: [], measuredLayers: ['payload', 'plugins'] }, 'the unmutated artefact/record pair did not compare clean, so these controls prove nothing')

  // A single-layer source (an installer `7z l` with no payload listing) measures
  // the plug-ins and reports the payload layer as not run, rather than calling
  // §2.5's `elevate.exe` record wrong.
  const pluginsOnly = memberRecordProblems(
    RECORDS.filter((record) => recordLayer(record) === 'plugins').map((record) => ({
      member: memberPath(record), sha256: artefact.get(record.name.toLowerCase())[0].sha256,
    })),
    structuredClone(RECORDS),
    ['plugins'],
  )
  assert.deepEqual(pluginsOnly.unrecorded, [], `a plugins-only listing invented an unrecorded binary: ${JSON.stringify(pluginsOnly)}`)
  assert.deepEqual(pluginsOnly.missing, [], `a plugins-only listing reported §2.5's elevate.exe record as missing: ${JSON.stringify(pluginsOnly)}`)
  assert.deepEqual(pluginsOnly.measuredLayers, ['plugins'], 'the comparison claimed a layer no source was available for')

  // A record dropped from §2.5 while the artefact still carries the binary: the
  // artefact side reports it as unrecorded, which is m03's shape.
  const dropped = structuredClone(RECORDS).filter((record) => record.name !== 'StdUtils.dll')
  const allEight = RECORDS.map((record) => ({
    member: memberPath(record),
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

  // (h) The 7z-listing reader itself. A parser that found nothing would make the
  //     census arm's "0 members" a *finding* rather than an empty read, and a
  //     parser that swallowed a licence-document name would hide exactly the
  //     obligation the sibling batch discharges. Both shapes are put to it, on
  //     the same text the real 7-Zip 26.02 prints (CRLF included), and on `-slt`.
  const plain = [
    '7-Zip 26.02 (x64) : Copyright (c) 1999-2026 Igor Pavlov : 2026-06-25',
    'Path = the-installer.exe',
    'Type = Nsis',
    '   Date      Time    Attr         Size   Compressed  Name',
    '                    .....                      6931  $PLUGINSDIR\\System.dll',
    '                    .....                      8018  $PLUGINSDIR\\UAC.dll',
    '                    .....                     45608  $PLUGINSDIR\\StdUtils.dll',
    '                    .....                      4684  $PLUGINSDIR\\nsDialogs.dll',
    '                    .....                      1899  $PLUGINSDIR\\modern-wizard.bmp',
    '                    .....                      3299  $PLUGINSDIR\\nsExec.dll',
    '                    .....                    123968060  $PLUGINSDIR\\app-64.7z',
    '                    .....                    242382  $PLUGINSDIR\\nsis7z.dll',
    '                    .....                      1080  $PLUGINSDIR\\WinShell.dll',
    '                    .....                      146493  $R0\\Uninstall LabCairn.exe',
    '                    ....A       107520        49588  resources\\elevate.exe',
  ].join('\r\n')
  const parsedPlain = parseInstallerListing(plain)
  assert.equal(parsedPlain.type, 'Nsis', 'the listing reader did not read the archive type, so a payload-only 7z listing could pass as an NSIS one')
  assert.equal(parsedPlain.members.length, 11, `the listing reader found ${parsedPlain.members.length} of the 11 members it was given`)
  assert.equal(
    parsedPlain.members.find((member) => member.name === 'system.dll')?.packedSize,
    6931,
    'the listing reader did not read a member\'s compressed size, which is the number §5.4 says the listing prints',
  )
  // The obligation state is an **equivalence**, not a rule requiring one word.
  // `NOT DONE` + no licence texts and `DONE` + the stated texts must both pass;
  // either direction of disagreement must fail. The old witness kept only one
  // direction in mind because the record used to say NOT DONE.
  assert.deepEqual(
    listedCensusProblems(parsedPlain.members, 10, false, listedLicenceDocuments(parsedPlain.members), 0),
    [],
    'the consistent NOT DONE / no-texts state failed, so the equivalence is not symmetric',
  )
  const sixTexts = [
    '$PLUGINSDIR/licences/LGPL-2.1.txt',
    '$PLUGINSDIR/licences/STDOUTILS-NOTICE.txt',
    '$PLUGINSDIR/licences/STDOUTILS-LGPL-CLARIFICATION.txt',
    '$PLUGINSDIR/licences/NSIS7Z-LICENSE.txt',
    '$PLUGINSDIR/licences/7ZIP-LICENSE.txt',
    '$PLUGINSDIR/licences/README.txt',
  ].map((member) => ({ member, name: path.posix.basename(member), packedSize: 9316 }))
  const carriedBuild = [...parsedPlain.members, ...sixTexts]
  assert.deepEqual(
    listedCensusProblems(carriedBuild, 16, true, listedLicenceDocuments(carriedBuild), 6),
    [],
    'the consistent DONE / six-texts state failed, so the equivalence is not symmetric',
  )
  // §2.5.1's stated *count* is a claim about the artefact: DONE with five texts,
  // or NOT DONE with one, must both redden even though the state word is right.
  const fiveTexts = listedCensusProblems(carriedBuild, 16, true, listedLicenceDocuments(carriedBuild), 5)
  assert.ok(
    fiveTexts.some((problem) => /states 5 licence text/.test(problem)),
    `DONE with five texts while the listing names six produced: ${fiveTexts.join('; ')}`,
  )
  const unstatedTexts = listedCensusProblems(carriedBuild, 16, true, listedLicenceDocuments(carriedBuild), null)
  assert.ok(
    unstatedTexts.some((problem) => /states no count of licence texts/.test(problem)),
    `a §2.5.1 with no text count was compared as zero instead of reported: ${unstatedTexts.join('; ')}`,
  )

  // A ninth plug-in DLL arriving in the archive: the census reports it.
  const withNinth = [...parsedPlain.members, { member: '$PLUGINSDIR/Intruder.dll', name: 'intruder.dll', packedSize: 4096 }]
  const ninthProblems = listedCensusProblems(withNinth, 10, false, listedLicenceDocuments(withNinth), 0)
  assert.ok(
    ninthProblems.some((problem) => /counts 10 members/.test(problem) && /counts seven plug-in DLLs/.test(problem)) || ninthProblems.length >= 2,
    `a ninth plug-in DLL in the listing produced: ${ninthProblems.join('; ')}`,
  )

  // A licence document arriving while §2.5.1 still records NOT DONE: one of the
  // two mismatch directions, and the reason the arm is an equivalence.
  const withLicence = [...parsedPlain.members, { member: '$PLUGINSDIR/licences/LGPL-2.1.txt', name: 'lgpl-2.1.txt', packedSize: 9316 }]
  const licenceProblems = listedCensusProblems(withLicence, 10, false, listedLicenceDocuments(withLicence), 0)
  assert.ok(
    licenceProblems.some((problem) => /NOT DONE/.test(problem) && /LGPL-2\.1\.txt/.test(problem)),
    `a licence document in the listing while §2.5.1 says NOT DONE produced: ${licenceProblems.join('; ')}`,
  )

  // The other mismatch direction: DONE while the listing names no document.
  const doneProblems = listedCensusProblems(parsedPlain.members, 10, true, [], 0)
  assert.ok(
    doneProblems.some((problem) => /DONE/.test(problem)),
    `§2.5.1 claiming DONE over a listing with no licence document produced: ${doneProblems.join('; ')}`,
  )

  // The three states are read from their own bullets, not from a whole-section
  // `DONE` scan: §4 is PARTLY DONE and §6(b) is NOT MEASURED while §1 states
  // whichever of DONE / NOT DONE this NOTICE copy is in. Asserting a fixed
  // `DONE` here would make the controls case itself fail when the witness is fed
  // a doctored NOTICE that consistently records NOT DONE -- a red about the
  // fixture, not about the property. Both directions are put to the reader.
  const states = obligationStates(NOTICE_TEXT)
  assert.ok(
    states.textAndNotice === 'DONE' || states.textAndNotice === 'NOT DONE',
    'the §1 text-and-notice state was not read from its own bullet',
  )
  assert.equal(states.correspondingSource, true, 'the §4 PARTLY DONE state was not read')
  assert.equal(states.replaceability, true, 'the §6(b) replaceability state was not read (NOT MEASURED before 2026-11-13, MEASURED with its date since)')
  const statedTexts = licenceTextCountClaim(NOTICE_TEXT)
  assert.ok(statedTexts !== null, '§2.5.1\'s licence-text count was not read')
  assert.equal(
    statedTexts,
    states.textAndNotice === 'DONE' ? 6 : 0,
    '§2.5.1 states a licence-text count that disagrees with its own §1 state',
  )
  // Flip the §1 state in a copy: the reader must answer differently, or a
  // witness could be pinned to whichever word the current tree happens to print.
  const flippedState = NOTICE_TEXT.replace(
    'The licence text and the notice (§1, §6) — DONE.',
    'The licence text and the notice (§1, §6) — NOT DONE.',
  ).replace(
    'The licence text and the notice (§1, §6) — NOT DONE.',
    'The licence text and the notice (§1, §6) — DONE.',
  )
  if (flippedState !== NOTICE_TEXT) {
    assert.notEqual(
      obligationStates(flippedState).textAndNotice,
      states.textAndNotice,
      'flipping §2.5.1\'s §1 state did not change what the reader reads, so the state arm is pinned to a word',
    )
  }
  const driftedCount = NOTICE_TEXT.replace('six of them are', 'five of them are')
  if (driftedCount !== NOTICE_TEXT) {
    assert.equal(licenceTextCountClaim(driftedCount), 5, 'changing §2.5.1\'s stated text count did not change the read')
  }

  // `-slt` shape: `Path = …` / `Packed Size = …` blocks, with CRLF and the
  // archive header's own `Path =` line, which is not a member.
  const slt = [
    'Path = the-installer.exe',
    'Type = Nsis',
    '----------',
    'Path = $PLUGINSDIR\\System.dll',
    'Packed Size = 6931',
    '----------',
    'Path = $PLUGINSDIR\\StdUtils.dll',
    'Packed Size = 45608',
    '----------',
    'Path = $R0\\Uninstall LabCairn.exe',
    'Packed Size = 146493',
  ].join('\r\n')
  const parsedSlt = parseInstallerListing(slt)
  assert.deepEqual(
    parsedSlt.members.map((member) => member.member),
    ['$PLUGINSDIR/System.dll', '$PLUGINSDIR/StdUtils.dll', '$R0/Uninstall LabCairn.exe'],
    `the -slt reader read the archive header as a member or lost a block: ${JSON.stringify(parsedSlt.members)}`,
  )
  assert.equal(parsedSlt.members[1].packedSize, 45608, 'the -slt reader did not read the block\'s Packed Size')

  // A payload-only listing (the 24.09 x86 7za's `Type = 7z` output) is not an
  // NSIS listing, and the witness must not mistake it for a short installer.
  const payloadOnly = parseInstallerListing('Type = 7z\r\n                    ....A       107520        49588  resources\\elevate.exe\r\n')
  assert.equal(payloadOnly.type, '7z', 'a payload-only listing was reported as an NSIS one')
  assert.equal(
    payloadOnly.members.filter((member) => member.member.startsWith('$PLUGINSDIR/')).length,
    0,
    'a payload-only listing invented $PLUGINSDIR members',
  )

  // (i) §5.4's compressed-size table, read from NOTICE and compared with a
  //     listing. The same function the arm above runs, with one value changed.
  const sizes = compressedSizeTable(NOTICE_TEXT)
  assert.ok(sizes.size >= 7, `§5.4 prints ${sizes.size} compressed sizes; it names seven plug-ins`)
  assert.deepEqual(
    listedSizeProblems(parsedPlain.members, sizes),
    [],
    '§5.4\'s compressed sizes disagreed with the clean NSIS listing, so the controls below prove nothing',
  )
  const driftedSize = new Map(sizes)
  const firstSize = [...driftedSize.keys()][0]
  driftedSize.set(firstSize, driftedSize.get(firstSize) + 1)
  const sizeDrift = listedSizeProblems(parsedPlain.members, driftedSize)
  assert.equal(sizeDrift.length, 1, `one compressed size off by one produced: ${sizeDrift.join('; ')}`)
  assert.match(sizeDrift[0], /compressed bytes for/, sizeDrift[0])

  const missingSize = new Map(sizes)
  missingSize.set('not-a-plugin.dll', 4096)
  const sizeMissing = listedSizeProblems(parsedPlain.members, missingSize)
  assert.ok(
    sizeMissing.some((problem) => /not-a-plugin\.dll/.test(problem) && /does not name/.test(problem)),
    `a §5.4 row for a plug-in not in the listing produced: ${sizeMissing.join('; ')}`,
  )
  const noSize = parsedPlain.members.map((member) =>
    member.name === firstSize ? { ...member, packedSize: null } : member,
  )
  const unmeasured = listedSizeProblems(noSize, sizes)
  assert.ok(
    unmeasured.some((problem) => /gives no Packed Size/.test(problem)),
    `a listing with no Packed Size was compared as zero rather than reported: ${unmeasured.join('; ')}`,
  )
  assert.equal(
    unmeasured.some((problem) => /gives 0\b/.test(problem)),
    false,
    `an unmeasured size was printed as zero: ${unmeasured.join('; ')}`,
  )

  // (j) The source-of-terms invariant, on the same functions the case above
  //     runs. The record became *more* accurate (four named licences instead of
  //     two); what must redden is a named licence with no source, not the count.
  const fromBundle = structuredClone(RECORDS).filter(
    (record) => bundleNamedFromRecord(record) === 'nsis-resources-3.4.1',
  )
  assert.equal(fromBundle.length, 4, `§2.5 names ${fromBundle.length} binaries from this bundle; the fixture that follows is stale`)
  const cleanSources = termsSourceProblems(fromBundle)
  assert.deepEqual(cleanSources.problems, [], 'the unmutated records already fail the source requirement, so these controls prove nothing')

  // A fifth plug-in whose terms are resolved upstream: the invariant still holds.
  // This is the shape that made the old "exactly 2" assertion go red.
  const grown = [...fromBundle, {
    name: 'Fifth.dll',
    bytes: 1,
    fields: {
      licence: 'MIT',
      where: 'upstream NSIS\'s `LICENSES` tree names the source as `Fifth.zip` (sha256 abcdef12…)',
      bundle: 'nsis-resources-3.4.1',
    },
  }]
  assert.deepEqual(termsSourceProblems(grown).problems, [], 'adding a properly sourced record reddened the invariant, which is watching the count rather than the property')

  // A named licence with no source: the finding the invariant exists for.
  const unsourced = structuredClone(fromBundle)
  unsourced.find((record) => record.name === 'UAC.dll').fields.where = 'a compiled DLL with no licence text'
  const unsourcedProblems = termsSourceProblems(unsourced).problems
  assert.equal(unsourcedProblems.length, 1, `a named licence with no source produced: ${unsourcedProblems.join('; ')}`)
  assert.match(unsourcedProblems[0], /UAC\.dll/, unsourcedProblems[0])

  // A hash with no source path is incomplete in the other direction.
  const hashOnly = structuredClone(fromBundle)
  hashOnly.find((record) => record.name === 'UAC.dll').fields.where = 'sha256 20e3192a…'
  const hashProblems = termsSourceProblems(hashOnly).problems
  assert.ok(
    hashProblems.some((problem) => /quotes 1 sha256/.test(problem)),
    `a short hash with no path produced: ${hashProblems.join('; ')}`,
  )

  // `unresolved` is allowed to have no source. Demanding one there would turn the
  // record's own vocabulary into a failure.
  const unresolved = structuredClone(fromBundle)
  unresolved.find((record) => record.name === 'UAC.dll').fields.licence = '**unresolved**'
  unresolved.find((record) => record.name === 'UAC.dll').fields.where = 'no terms found'
  assert.deepEqual(termsSourceProblems(unresolved).problems, [], 'an unresolved record was required to name a source it does not have')

  // The two artefacts are distinct: a `where` field that cites the downloaded
  // bundle as carrying the licence document is contradicted by the cache.
  const conflated = structuredClone(fromBundle)
  conflated.find((record) => record.name === 'UAC.dll').fields.where =
    'nsis-resources-3.4.1 carries a licence document with the zlib/libpng grant'
  const upstreamEntry = conflated.filter((record) => /LICENSES|upstream NSIS/i.test(termsSources(record).text))
  assert.ok(upstreamEntry.length < fromBundle.length, 'the conflation control did not change which records cite upstream NSIS')

  // Upstream hash comparison: a quoted hash with no matching file reddens, and
  // an absent provenance tree reports every quoted hash as unmeasured (never a
  // pass, never a zero).
  const upstreamAbsent = upstreamHashProblems(fromBundle, [])
  assert.equal(upstreamAbsent.available, false, 'an absent provenance tree was reported as available')
  assert.deepEqual(upstreamAbsent.problems, [], 'an absent provenance tree invented hash findings')
  assert.equal(upstreamAbsent.unmeasured.length, 5, `§2.5 quotes five hashes; ${upstreamAbsent.unmeasured.length} were reported unmeasured`)
  const upstreamBogus = structuredClone(fromBundle)
  upstreamBogus.find((record) => record.name === 'UAC.dll').fields.where =
    'upstream NSIS\'s `LICENSES` tree names `UAC.zip` (sha256 deadbeef…)'
  if (UPSTREAM_DIRS.length > 0) {
    const bogus = upstreamHashProblems(upstreamBogus, UPSTREAM_DIRS)
    assert.ok(
      bogus.problems.some((problem) => /deadbeef/.test(problem)),
      `a quoted hash no upstream file holds produced: ${bogus.problems.join('; ')}`,
    )
  } else {
    // The same comparison over a fixture directory: one real file, one quoted
    // hash that is not its hash. A reader that matched by name rather than bytes
    // would pass this.
    const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'labcairn-upstream-control-'))
    try {
      fs.writeFileSync(path.join(scratch, 'UAC.zip'), 'not the bytes §2.5 quotes')
      const bogus = upstreamHashProblems(upstreamBogus, [scratch])
      assert.equal(bogus.available, true, 'the fixture provenance tree was reported as unavailable')
      assert.ok(bogus.problems.some((problem) => /deadbeef/.test(problem)),
        `a quoted hash no file in the tree holds produced: ${bogus.problems.join('; ')}`)
    } finally {
      fs.rmSync(scratch, { recursive: true, force: true })
    }
  }
})
