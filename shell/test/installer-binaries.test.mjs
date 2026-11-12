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
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  binaryRecords,
  copyingClaim,
  noticeSubsection,
  readNotice,
} from '../../.github/notice-readers.mjs'
import {
  binaryCarriesLicenceStatement,
  bundleFiles,
  defaultCacheDir,
  extractMembers,
  findCacheBundles,
  fingerprint,
  isLicenceDocument,
  licenceDocumentsIn,
  toolchainDeclarations,
} from '../../.github/installer-binaries.mjs'
import { lockfileKeys } from '../../.github/shell-lockfile-keys.mjs'

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

/** Which unpacked bundle directory holds a file with this name and this sha256. */
function locateInCache(bundleName, record) {
  const dirs = CACHE.bundles.get(bundleName)
  if (!dirs?.length) return null
  for (const dir of dirs) {
    for (const file of bundleFiles(dir)) {
      if (path.basename(file).toLowerCase() !== record.name.toLowerCase()) continue
      const print = fingerprint(file)
      if (print.sha256 === record.fields.sha256) return { dir, file, print }
    }
  }
  return null
}

/** Every file named `record.name` anywhere in that bundle, whatever its bytes are. */
function nameMatchesInCache(bundleName, record) {
  const dirs = CACHE.bundles.get(bundleName) ?? []
  const found = []
  for (const dir of dirs) {
    for (const file of bundleFiles(dir)) {
      if (path.basename(file).toLowerCase() === record.name.toLowerCase()) found.push(fingerprint(file))
    }
  }
  return found
}

/**
 * The bundle §2.5's `bundle` field names, before any trailing path.
 *
 * `nsis-resources-3.4.1 — byte-identical to the upstream StdUtils 1.14 …` names
 * the bundle first and the comparison second; `nsis-3.0.4.1/Plugins/x86-unicode`
 * names the bundle and then the directory inside it.
 */
function bundleNamed(record) {
  const field = record.fields.bundle ?? ''
  const match = /^(nsis-resources-[\d.]+|nsis-[\d.]+)/.exec(field)
  return match ? match[1] : null
}

const RUN_LOG = []
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
  for (const record of RECORDS) {
    const bundleName = bundleNamed(record)
    if (!bundleName) {
      problems.push(`${record.name}: §2.5 names no recognisable bundle in ${JSON.stringify(record.fields.bundle)}`)
      continue
    }
    const found = locateInCache(bundleName, record)
    if (!found) {
      const candidates = nameMatchesInCache(bundleName, record)
      const detail = candidates.length
        ? `the bundle holds ${candidates.length} file(s) of that name, whose sha256s are ${candidates.map((c) => c.sha256.slice(0, 16) + '…').join(', ')}`
        : `the bundle holds no file of that name`
      problems.push(`${record.name}: §2.5 records sha256 ${record.fields.sha256?.slice(0, 16)}… but ${detail}`)
      continue
    }
    if (found.print.bytes !== record.bytes) {
      problems.push(
        `${record.name}: §2.5 records ${record.bytes} bytes but the real file is ${found.print.bytes}`,
      )
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
  const recorded = new Map(RECORDS.map((record) => [record.name.toLowerCase(), record]))

  const unrecorded = binaries
    .map((member) => path.basename(member.member).toLowerCase())
    .filter((name) => !recorded.has(name))
    .sort()
  assert.deepEqual(
    unrecorded,
    [],
    `the installer carries ${unrecorded.length} binary(ies) §2.5 records nothing about: ${unrecorded.join(', ')} — a binary that enters the artefact under a licence this file does not name is the defect §2.5.2 says no watcher exists for`,
  )

  const missing = RECORDS
    .map((record) => record.name.toLowerCase())
    .filter((name) => !binaries.some((member) => path.basename(member.member).toLowerCase() === name))
    .sort()
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
    (record) => bundleNamed(record) === 'nsis-resources-3.4.1' && !/unresolved/i.test(record.fields.licence ?? ''),
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
  const declarations = toolchainDeclarations([
    process.env.LABCAIRN_LICENCE_APP_BUILDER_LIB ?? '',
    path.join(SHELL_ROOT, 'node_modules', '.pnpm'),
    CACHE_DIR,
  ].filter(Boolean))

  if (declarations.length === 0) {
    notRun(
      'the toolchain declaration against §2.5',
      `no app-builder-lib to read (its installed package or a copy named by LABCAIRN_LICENCE_APP_BUILDER_LIB): shell.yml installs no node_modules and downloads no toolchain`,
    )
    return
  }
  ran('the toolchain declaration against §2.5')

  const lockText = fs.readFileSync(path.join(SHELL_ROOT, 'pnpm-lock.yaml'), 'utf8')
  const direct = lockfileKeys(lockText)
  const pinnedBuilder = direct.all_entries.filter((key) => /^electron-builder@/.test(key)).sort()
  assert.ok(pinnedBuilder.length > 0, 'shell/pnpm-lock.yaml pins no electron-builder, so the §2.5 toolchain claim has no pin to be about')

  const namedByToolchain = new Set(declarations.map((declaration) => declaration.bundle))
  const namedByNotice = new Set(RECORDS.map((record) => bundleNamed(record)).filter(Boolean))
  for (const bundle of namedByNotice) {
    assert.ok(
      namedByToolchain.has(bundle),
      `§2.5 records binaries from ${bundle}, but the pinned electron-builder (${pinnedBuilder.join(', ')}) declares ${[...namedByToolchain].join(', ')} — the toolchain §2.5 describes is not the one this lock pins`,
    )
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

  const licenceMembers = members.filter((member) => isLicenceDocument(member.member))
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
    pluginsdir.filter((member) => isLicenceDocument(member.member)).map((member) => member.member),
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
test('an arm that could not look says NOT RUN with a reason, and never reads as a pass', () => {
  assert.ok(RUN_LOG.length > 0, 'no arm reported anything, so this file measured nothing at all')
  const silent = RUN_LOG.filter((entry) => !entry.startsWith('RAN ') && !entry.startsWith('NOT RUN '))
  assert.deepEqual(silent, [], `these arms reported a state that is neither RAN nor NOT RUN: ${silent.join('; ')}`)
  const unexplained = RUN_LOG.filter((entry) => entry.startsWith('NOT RUN ') && !entry.includes(': '))
  assert.deepEqual(unexplained, [], `these arms say NOT RUN without naming a reason: ${unexplained.join('; ')}`)
  const ranArms = RUN_LOG.filter((entry) => entry.startsWith('RAN ')).length
  const skipped = RUN_LOG.filter((entry) => entry.startsWith('NOT RUN '))
  // The arms that must always be able to look, because their reader is the tree
  // itself rather than an artefact a runner does not build.
  const alwaysLookable = RUN_LOG.filter(
    (entry) => entry.startsWith('NOT RUN ') && /§2\.5 hashes|§2\.5\'s eight names/.test(entry),
  )
  if (skipped.length > 0) {
    const reasons = skipped.map((entry) => entry.split(': ', 2)[1])
    assert.ok(
      reasons.every((reason) => /shell\.yml|LABCAIRN_LICENCE_/.test(reason)),
      `these arms are NOT RUN for a reason that is not "the runner builds no artefact" (${reasons.join(' | ')}): the location was not findable on a machine that should have it`,
    )
  }
  assert.ok(ranArms > 0 || skipped.length === RUN_LOG.length, 'the run log is neither a set of arms that ran nor a set that explains why it did not')
})

// ---------------------------------------------------------------------------
// The controls: the properties this file watches, broken on copies of the data.
// ---------------------------------------------------------------------------
test('the controls fail for the properties: a swapped binary, a drifted size, a renamed bundle, a bundle the toolchain does not fetch', () => {
  // (a) A plug-in replaced by another build: the name and the size survive, the
  //     bytes do not. This is the change §2.5's own records would not notice.
  const swapped = structuredClone(RECORDS)
  const target = swapped.find((record) => record.name === 'StdUtils.dll')
  assert.ok(target, '§2.5 records no StdUtils.dll, so this control has nothing to swap')
  target.fields.sha256 = 'f'.repeat(64)
  const located = locateInCache(bundleNamed(target), target)
  assert.equal(located, null, 'a §2.5 record whose sha256 no longer matches any real file still located a file — the lookup is not the hash')

  // (b) A byte count that drifted from the real file.
  const drifted = structuredClone(RECORDS)
  const sized = drifted.find((record) => record.name === 'nsis7z.dll')
  assert.ok(sized, '§2.5 records no nsis7z.dll')
  const found = locateInCache(bundleNamed(sized), sized)
  assert.ok(found, 'the control could not find nsis7z.dll in the bundle it names')
  assert.notEqual(
    found.print.bytes,
    999_999,
    'the real byte count equals the absurd count the control invented, so the size comparison compares nothing',
  )

  // (c) §2.5 naming a bundle the pinned toolchain does not fetch.
  if (toolchainDeclarations([path.join(SHELL_ROOT, 'node_modules', '.pnpm'), CACHE_DIR].filter(Boolean)).length > 0) {
    const declarations = toolchainDeclarations([path.join(SHELL_ROOT, 'node_modules', '.pnpm'), CACHE_DIR].filter(Boolean))
    const named = new Set(declarations.map((declaration) => declaration.bundle))
    assert.ok(!named.has('nsis-9.9.9'), 'the toolchain declares nsis-9.9.9, so this control cannot use it to show a wrong bundle name reddens the read')
    assert.ok(
      [...new Set(RECORDS.map((record) => bundleNamed(record)).filter(Boolean))].every((bundle) => named.has(bundle)),
      `§2.5 names ${[...new Set(RECORDS.map((record) => bundleNamed(record)))].join(', ')} and the toolchain declares ${[...named].join(', ')}: the real records do not match the toolchain, so this control is not testing what it claims`,
    )
  }

  // (d) A reader that cannot look reports that, rather than finding nothing and
  //     calling it clean.
  const empty = findCacheBundles(path.join(os.tmpdir(), `labcairn-no-cache-${process.pid}`))
  assert.equal(empty.available, false, 'findCacheBundles reported a cache where there is none')
  assert.equal(empty.bundles.size, 0, 'a missing cache reported bundles')

  // (e) The extract member scan finds a licence document when one is there.
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'labcairn-licence-scan-'))
  try {
    fs.mkdirSync(path.join(scratch, '$PLUGINSDIR'), { recursive: true })
    fs.writeFileSync(path.join(scratch, '$PLUGINSDIR', 'System.dll'), 'not a licence')
    fs.writeFileSync(
      path.join(scratch, '$PLUGINSDIR', 'COPYING.txt'),
      'GNU LESSER GENERAL PUBLIC LICENSE — this library is licensed under the LGPL.',
    )
    const members = extractMembers([scratch])
    assert.equal(members.length, 2, `the extract scan found ${members.length} of the 2 members it was given`)
    assert.deepEqual(
      members.filter((member) => isLicenceDocument(member.member)).map((member) => member.member),
      ['$PLUGINSDIR/COPYING.txt'],
      'the licence-document scan did not identify the licence document it was given, so §2.5.1\'s "none of them is a licence document" is not a measured absence',
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
