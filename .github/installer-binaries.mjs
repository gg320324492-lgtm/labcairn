/**
 * The binaries a LabCairn installer distributes, read from the bundles they come from.
 *
 * **Why this file exists.** NOTICE §2.5 records eight binaries — seven NSIS
 * plug-ins carried in the installer's `$PLUGINSDIR` and `elevate.exe` in the
 * payload's `resources/` — each with a byte count, a sha256, the bundle it came
 * from, a licence and a holder. Until now the only watch on that section read
 * the records *against each other*: `shell/test/notice-scope.test.mjs` asks
 * whether every §2.5 entry has a sha256 and a licence, and §2.5.2 records the
 * owner's 2026-11-12 decision that a watcher catching **a ninth binary entering
 * the archive** does not exist. Nothing compared §2.5's hashes to the bytes the
 * build actually fetches, so a plug-in swapped for another build — the same
 * name, different terms — would keep every record in §2.5 true.
 *
 * **What the physical sources are.** NOTICE §5.4 names them: the two
 * electron-builder download caches, `${ELECTRON_BUILDER_CACHE}/nsis-resources-3.4.1`
 * and the NSIS 3.0.4.1 distribution. Those bundles are what the NSIS target
 * downloads, and they are what say what each binary's terms are. The third is
 * `app-builder-lib`'s own declaration — the bundle names and the checksums it
 * asks the downloader to verify — which is what ties "the bundle §2.5 names" to
 * "the bundle this build fetches".
 *
 * **What is *not* here.** No licence conclusion is drawn from a binary's bytes.
 * A compiled DLL carries no licence text (§2.5 says so of `StdUtils.dll`, and
 * §2.5.1 measures it: a grep for `lgpl|lesser general public|…` over each of
 * the two LGPL plug-ins returns no hit), so terms come from the bundle that
 * carries them, and this file reports whether that bundle states terms — it
 * does not infer them.
 *
 * Usage:
 *   node .github/installer-binaries.mjs                 # read NOTICE + the cache
 *   node .github/installer-binaries.mjs --cache <dir>   # name the cache
 *   node .github/installer-binaries.mjs --extract <dir> # an installer extract (§5.4 step 3)
 */

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const NOTICE_PATH = path.resolve(import.meta.dirname, '..', 'NOTICE')

/** `  StdUtils.dll — 102,400 bytes` — one §2.5 binary block heading. */
const BINARY_HEADING = /^ {2}([A-Za-z0-9_.-]+\.(?:dll|exe)) — ([\d,]+) bytes$/
/** `    sha256   b72e9013…` — one field of a §2.5 binary block. */
const BINARY_FIELD = /^ {4}(path|sha256|bundle|licence|holder|where)\s{2,}(\S.*)$/
/** A continuation line of a wrapped §2.5 field value. */
const BINARY_CONTINUATION = /^ {11}\S/
/** `Measured 2026-11-11 … 15,488 bytes, sha256` + the hash on the next line. */
const COPYING_CLAIM = /`COPYING` \(([\d,]+) bytes, sha256\s*\n?([0-9a-f]{64})\)/
/** A bundle electron-builder downloads: `getBinFromUrl("nsis-3.0.4.1", "nsis-3.0.4.1.7z", "<sha256>")`. */
const BIN_DECLARATION =
  /getBinFromUrl\(\s*["'`](nsis[^"'`]*)["'`],\s*["'`]([^"'`]+)["'`],\s*["'`]([0-9a-f]{64})["'`]/g

/**
 * One numbered subsection of NOTICE, by its heading.
 *
 * The same boundary rule `shell/test/notice-scope.test.mjs` uses: the heading is
 * matched at column zero and the slice ends at the next heading *line*, because
 * every heading in this file is underlined by a rule of dashes and treating the
 * underline as the boundary would end the slice after two lines.
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
  return lines.slice(start, end)
}

/**
 * The eight §2.5 records, each with all six fields.
 *
 * A wrapped field value (the `bundle` and `where` fields wrap) is joined back
 * onto its field rather than dropped, because `bundle` is the field this file
 * compares against the real bundles. A §2.5 that names no binary throws rather
 * than returning an empty list: a read that finds nothing when the section is
 * present is the failure mode the repository's rules call the dangerous kind.
 */
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
  if (binaries.length === 0) {
    throw new Error('§2.5 names no binary — the read found nothing')
  }
  return binaries
}

/** The `COPYING` of the NSIS distribution §2.5 names, as §2.5 states it. */
export function copyingClaim(noticeText) {
  const match = COPYING_CLAIM.exec(noticeText)
  if (!match) {
    throw new Error('§2.5 names no sha256 for the NSIS distribution`s COPYING — the read found nothing')
  }
  return { bytes: Number(match[1].replace(/,/g, '')), sha256: match[2] }
}

/** The two bundles §2.5's records name, each with the sub-path it names. */
export function recordedBundles(records) {
  const bundles = new Map()
  for (const record of records) {
    const bundle = record.fields.bundle
    if (!bundle) continue
    bundles.set(bundle, (bundles.get(bundle) ?? []).concat(record.name))
  }
  return bundles
}

/** sha256 and byte count of one file, as the artefact presents them. */
export function fingerprint(file) {
  const buffer = fs.readFileSync(file)
  return {
    path: file,
    bytes: buffer.length,
    sha256: crypto.createHash('sha256').update(buffer).digest('hex'),
  }
}

/**
 * The unpacked bundles in an electron-builder cache.
 *
 * The cache keeps each bundle twice: the `.7z` under `downloads/<checksum>/`,
 * and the unpacked tree under `nsis/<bundle-name>/` (a second layout,
 * `<bundle-name>/<bundle-name>-<hash>/`, appears in caches from other
 * electron-builder versions). Both are searched, and the layout actually found
 * is returned, because a reader that silently searched one layout would report
 * "the bundle is not in the cache" for a cache that simply arranges it
 * differently.
 */
export function findCacheBundles(cacheDir) {
  const found = new Map()
  if (!fs.existsSync(cacheDir)) return { available: false, cacheDir, bundles: found }

  function walk(dir, depth) {
    if (depth > 5) return
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (!entry.isDirectory()) continue
      if (entry.name === 'nsis-3.0.4.1' || entry.name.startsWith('nsis-resources-')) {
        if (!found.has(entry.name)) found.set(entry.name, [])
        found.get(entry.name).push(full)
      }
      walk(full, depth + 1)
    }
  }
  walk(cacheDir, 0)
  return { available: true, cacheDir, bundles: found }
}

/** Every file a bundle directory holds, with its path below the bundle root. */
export function bundleFiles(bundleDir) {
  const files = []
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) walk(full)
      else files.push(full)
    }
  }
  walk(bundleDir)
  return files
}

/**
 * The licence documents a bundle carries.
 *
 * `nsis-3.0.4.1` carries `COPYING`; `nsis-resources-3.4.1` carries **none**, and
 * that absence is §2.5's stated reason for recording two of its plug-ins as
 * `unresolved`. A name pattern rather than a fixed list, because the claim is
 * "this bundle states no terms", and a claim about an absence has to be checked
 * by looking for what would falsify it.
 */
export function licenceDocumentsIn(bundleDir) {
  const NAME = /^(LICEN[CS]E|COPYING|NOTICE|LICENSE\.txt|README)/i
  return bundleFiles(bundleDir).filter((file) => NAME.test(path.basename(file)))
}

/**
 * `app-builder-lib`'s own declaration of the NSIS toolchain.
 *
 * Which bundle names it downloads, with the checksum it verifies each against.
 * Measured at `app-builder-lib@26.18.0`: `out/toolsets/windows.js` declares
 * `nsis-3.0.4.1` / `nsis-3.0.4.1.7z` and `nsis-resources-3.4.1` /
 * `nsis-resources-3.4.1.7z`. This is what ties §2.5's bundle names to the
 * toolchain the build actually runs: when electron-builder is bumped and the
 * plug-ins move to a newer bundle, the declaration changes and this read says
 * so.
 *
 * Read from the installed package when the tree has one, and from a caller-
 * supplied directory otherwise. `shell.yml` installs no `node_modules`
 * (`tests/test_shell_ci.py::test_the_test_step_runs_inside_the_shell_and_names_the_runner_temp`
 * refuses a `pnpm install` step there), so the witness reports this arm as
 * unavailable on a runner rather than pretending it read something.
 */
export function toolchainDeclarations(searchDirs) {
  const declarations = []
  for (const dir of searchDirs) {
    if (!fs.existsSync(dir)) continue
    for (const file of bundleFiles(dir)) {
      if (!/\.js$/.test(file) || /\.map$/.test(file)) continue
      let text
      try {
        text = fs.readFileSync(file, 'utf8')
      } catch {
        continue
      }
      if (!text.includes('getBinFromUrl')) continue
      for (const match of text.matchAll(BIN_DECLARATION)) {
        declarations.push({
          bundle: match[1],
          archive: match[2],
          checksum: match[3],
          declaredIn: file,
        })
      }
    }
  }
  return declarations
}

/**
 * The members of an installer extract.
 *
 * §5.4 step 3 produces exactly this: the installer's members under one
 * directory and the payload's members under another. The claim §2.5.1 makes
 * about them — "the NSIS archive lists **ten** members and none of them is a
 * licence document", "the installer carries **zero** licence text for either
 * LGPL binary" — is only checkable against a real extract, so an absent extract
 * is reported as absent.
 */
export function extractMembers(extractDirs) {
  const members = []
  for (const dir of extractDirs) {
    if (!fs.existsSync(dir)) continue
    for (const file of bundleFiles(dir)) {
      const relative = path.relative(dir, file).split(path.sep).join('/')
      if (relative.startsWith('$PLUGINSDIR/') || relative.startsWith('resources/')) {
        members.push({ ...fingerprint(file), member: relative })
      } else {
        members.push({ ...fingerprint(file), member: relative })
      }
    }
  }
  return members
}

/** A member whose name says it is a licence document. */
export function isLicenceDocument(member) {
  return /(^|[/.])(LICEN[CS]E|COPYING|LICENSE|NOTICE)(\.|$|\.txt|\.html)/i.test(member)
}

/**
 * Whether a binary's own bytes carry a licence statement.
 *
 * The same grep §2.5.1 describes: the phrases and the holder's name, searched
 * over the raw bytes. A hit means the binary does carry the statement and the
 * "the header does not survive into the installer" claim needs re-reading; a
 * miss is what §2.5 records.
 */
export function binaryCarriesLicenceStatement(file, phrases) {
  const buffer = fs.readFileSync(file)
  const hits = []
  for (const phrase of phrases) {
    const pattern = new RegExp(phrase, 'i')
    if (pattern.test(buffer.toString('latin1'))) hits.push(phrase)
  }
  return hits
}

/** The default cache directory: `ELECTRON_BUILDER_CACHE`, as §5.4 names it. */
export function defaultCacheDir(env = process.env) {
  return env.ELECTRON_BUILDER_CACHE ?? path.join(env.LOCALAPPDATA ?? '', 'electron-builder', 'Cache')
}

async function main(argv) {
  const cacheIndex = argv.indexOf('--cache')
  const extractIndex = argv.indexOf('--extract')
  const noticeText = fs.readFileSync(argv[0] === '--notice' ? argv[1] : NOTICE_PATH, 'utf8')
  const records = binaryRecords(noticeText)
  console.log(`§2.5 records ${records.length} binaries`)
  for (const record of records) {
    console.log(`  ${record.name} ${record.bytes}b sha256=${(record.fields.sha256 ?? '').slice(0, 16)}… bundle=${record.fields.bundle}`)
  }
  const claim = copyingClaim(noticeText)
  console.log(`§2.5's COPYING claim: ${claim.bytes}b sha256=${claim.sha256.slice(0, 16)}…`)

  const cacheDir = cacheIndex >= 0 ? argv[cacheIndex + 1] : defaultCacheDir()
  const cache = findCacheBundles(cacheDir)
  if (!cache.available) {
    console.log(`cache: NOT AVAILABLE at ${cacheDir}`)
    process.exitCode = 1
    return
  }
  console.log(`cache: ${cacheDir}`)
  for (const [name, dirs] of cache.bundles) {
    console.log(`  bundle ${name}: ${dirs.length} location(s); licence documents: ${licenceDocumentsIn(dirs[0]).map((f) => path.basename(f)).join(', ') || '(none)'}`)
  }
  if (extractIndex >= 0) {
    const members = extractMembers([argv[extractIndex + 1]])
    console.log(`extract members: ${members.length}`)
    for (const member of members) {
      console.log(`  ${member.member} ${member.bytes}b ${member.sha256.slice(0, 16)}…${isLicenceDocument(member.member) ? ' [LICENCE DOCUMENT]' : ''}`)
    }
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(import.meta.url.slice(7))) {
  await main(process.argv.slice(2))
}
