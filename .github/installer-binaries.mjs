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
/** A continuation line of a wrapped §2.5 field value, aligned under its value. */
const BINARY_CONTINUATION = /^ {5,}\S/
/** `Measured 2026-11-11 … 15,488 bytes, sha256` + the hash on the next line. */
const COPYING_CLAIM = /`COPYING` \(([\d,]+) bytes, sha256\s*\n?([0-9a-f]{64})\)/
/**
 * A bundle electron-builder downloads, as its own code states the download.
 *
 * The published `app-builder-lib` is CommonJS, so the call that reads as
 * `getBinFromUrl("nsis-3.0.4.1", …)` in the TypeScript source is compiled to
 *
 *     return (0, binDownload_1.getBinFromUrl)("nsis-3.0.4.1", "nsis-3.0.4.1.7z",
 *         "9877df902530f96357d13a7a31ae2b9df67f48b11ffc9a1700a7c961574ec5fa");
 *
 * — the imported function behind the comma operator, with a `)` between the name
 * and the argument list. A pattern that required the name and the parenthesis to
 * be adjacent matched nothing in the published package, and the arm reported
 * "declares no NSIS bundle" about a package that declares two. Measured here at
 * `app-builder-lib@26.18.0`, `out/toolsets/windows.js`.
 */
const BIN_DECLARATION =
  /getBinFromUrl\)*\(\s*["'`](nsis[^"'`]*)["'`],\s*["'`]([^"'`]+)["'`],\s*["'`]([0-9a-f]{64})["'`]/g

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

/**
 * Every file a directory holds, following links.
 *
 * `fs.readdirSync(…, { withFileTypes: true })` reports a symbolic link or a
 * Windows junction as neither a file nor a directory, and pnpm's store is built
 * out of them: `<name>@<version>/node_modules/<name>` is a link to the store's
 * own copy, and `<project>/node_modules/<name>` is a link into the store. A walk
 * that trusts `entry.isDirectory()` therefore stops at the link and finds nothing
 * below it — measured here as "declares no NSIS bundle" against a package that
 * declares two. `statSync` follows the link, and a cycle guard on the real path
 * keeps a linked tree from being walked forever.
 */
export function bundleFiles(bundleDir) {
  const files = []
  const seen = new Set()
  function walk(dir) {
    let real
    try {
      real = fs.realpathSync(dir)
    } catch {
      return
    }
    if (seen.has(real)) return
    seen.add(real)
    let entries
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true })
    } catch {
      return
    }
    for (const entry of entries) {
      const full = path.join(dir, entry.name)
      let kind = entry.isDirectory() ? 'directory' : entry.isFile() ? 'file' : 'link'
      if (kind === 'link') {
        try {
          kind = fs.statSync(full).isDirectory() ? 'directory' : 'file'
        } catch {
          continue
        }
      }
      if (kind === 'directory') walk(full)
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
  return bundleFiles(bundleDir).filter((file) => licenceDocumentKind(file) !== null)
}

/**
 * A file's name, when the name is a licence document's name.
 *
 * The names §2.5 and §2.5.1 use for the documents that would settle the
 * obligations — `COPYING`, `LICENSE.txt`, `LGPL.txt`, `THIRD-PARTY-NOTICES` —
 * and nothing looser: `README` is deliberately **not** here, because a bundle's
 * README is not a grant and §2.5.1's absence claim would then be falsified by a
 * file that states no terms.
 */
const LICENCE_NAME = /(^|[/.])(LICEN[CS]E|COPYING|NOTICE|THIRD[- ]PARTY[- ]NOTICES|LGPL|GPL|MPL)([.-]|$)/i

/**
 * The openings that say a file *is* a licence text.
 *
 * The names a licence document can carry are unbounded — `LICENSE.LGPL`,
 * `COPYLEFT`, `StdUtils-LICENCE` — so the absence §2.5.1 records ("none of them
 * is a licence document") is only a measured absence if the check also reads
 * what the file says. Measured on this tree: a `$PLUGINSDIR/LGPL.txt` carrying
 * the `GNU LESSER GENERAL PUBLIC LICENSE` header is the exact thing the LGPL
 * obligation would be discharged with, and a name-only pattern missed it.
 *
 * Only the head of the file is read, and only as latin1: a compiled DLL that
 * happens to contain one of these phrases deeper in its data sections is not a
 * licence document, and a check that read the whole file would say it is.
 */
const LICENCE_TEXT_OPENINGS = [
  /^.{0,400}?\bGNU LESSER GENERAL PUBLIC LICENSE\b/i,
  /^.{0,400}?\bGNU GENERAL PUBLIC LICENSE\b/i,
  /^.{0,400}?\bMozilla Public License Version 2\.0\b/i,
  /^.{0,400}?\bApache License\s*(Version|2)/i,
  /^.{0,400}?\bMIT License\b/i,
  /^.{0,400}\bPermission is hereby granted, free of charge\b/i,
  /^.{0,400}\bThis software is provided 'as-is', without any express or implied warranty\b/i,
]

/**
 * Whether a file is a licence document, and on what grounds: `name` or `text`.
 *
 * `null` means neither. A binary whose *own bytes* carry a licence statement is
 * not a document (§2.5 records that the plug-ins carry no licence text, and
 * `binaryCarriesLicenceStatement` is the check for that claim); this function is
 * about the members that are documents in their own right.
 */
export function licenceDocumentKind(file) {
  if (LICENCE_NAME.test(path.basename(file))) return 'name'
  // A file that travels *in a licences directory* is a licence text, whatever its
  // name. Measured here: the installer's six texts are `LGPL-2.1.txt`,
  // `STDOUTILS-NOTICE.txt`, `STDOUTILS-LGPL-CLARIFICATION.txt`,
  // `NSIS7Z-LICENSE.txt`, `7ZIP-LICENSE.txt` and `README.txt`, and a name
  // pattern recognised **one** of the six -- the others carry the licence word
  // after a hyphen, which the pattern's separator class did not include. So the
  // extract arm counted one licence document where the archive carries six, and
  // §2.5.1's own wording is "the licence texts under `$PLUGINSDIR\licenses\`":
  // the directory is the rule.
  if (LICENCE_DIRECTORY.test(path.dirname(file))) return 'directory'
  let head
  try {
    const handle = fs.openSync(file, 'r')
    try {
      const buffer = Buffer.alloc(4096)
      const read = fs.readSync(handle, buffer, 0, 4096, 0)
      head = buffer.subarray(0, read).toString('latin1')
    } finally {
      fs.closeSync(handle)
    }
  } catch {
    return null
  }
  if (/\x00/.test(head)) return null
  return LICENCE_TEXT_OPENINGS.some((pattern) => pattern.test(head)) ? 'text' : null
}

/** A directory whose name says the files in it are licence texts. */
const LICENCE_DIRECTORY = /(^|[\\/])(licen[cs]es?)$/i

/**
 * The licence texts the repository ships, and the hashes its README records.
 *
 * §2.5.1 states that "hashing the six members gives the sha256s of the
 * repository's six files -- five of the six are recorded in
 * `shell/licenses/`'s `README.txt`, the sixth being that README itself, which
 * cannot record its own hash". That is a claim about bytes, and it is checkable
 * twice over: the README's recorded hashes must match the files in the tree, and
 * the texts the installer carries must be those files.
 *
 * The README is parsed per entry -- a heading naming the file, then its byte
 * count, then its hash -- rather than by collecting every hash in the document.
 * The LGPL entry quotes a *different* file's hash (upstream's own `LGPL.txt`,
 * `1e7e6bae…`), and a reader that took every hash in the file would attribute
 * that one to `LGPL-2.1.txt` and report a mismatch against a correct tree.
 */
export function licenceTextClaims(readmeText) {
  const claims = new Map()
  const entry = /^`([^`]+)`\s*$/gm
  const starts = [...readmeText.matchAll(entry)]
  for (let index = 0; index < starts.length; index += 1) {
    const name = starts[index][1]
    const from = starts[index].index + starts[index][0].length
    const to = index + 1 < starts.length ? starts[index + 1].index : readmeText.length
    const body = readmeText.slice(from, to)
    // The size and the word "sha256" may sit on different lines: the
    // STDOUTILS-NOTICE.txt entry reads "4,052 bytes,\nsha256\n    `hash`". A
    // pattern that required them on one line read four of the five claims the
    // section says the README records, and the file it then could not account
    // for looked like one the README had never mentioned.
    const claim = /([\d,]+) bytes,?\s*\n?\s*sha256\s*\n\s*`([0-9a-f]{64})`/.exec(body)
    if (!claim) continue
    claims.set(name, { bytes: Number(claim[1].replace(/,/g, '')), sha256: claim[2] })
  }
  return claims
}

/**
 * The repository's licence texts against the hashes its README records.
 *
 * `dir` is the repository's own `shell/licenses/`. The README cannot record its
 * own hash, so it is exempt; every other file must match both the byte count and
 * the sha256 its entry states. A file edited without its README entry updated is
 * the drift this catches -- and it is the drift that would put a different text
 * in the installer than the one the record describes.
 */
export function licenceTextFileProblems(claims, dir) {
  const problems = []
  for (const [name, claim] of claims) {
    const file = path.join(dir, name)
    if (!fs.existsSync(file)) {
      problems.push(`shell/licenses/README.txt records ${name} (${claim.bytes} bytes, sha256 ${claim.sha256.slice(0, 12)}…), and the tree holds no such file`)
      continue
    }
    const print = fingerprint(file)
    if (print.bytes !== claim.bytes) {
      problems.push(`shell/licenses/README.txt records ${name} as ${claim.bytes} bytes; the file is ${print.bytes}`)
    }
    if (print.sha256 !== claim.sha256) {
      problems.push(`shell/licenses/README.txt records ${name} as sha256 ${claim.sha256.slice(0, 16)}…; the file is ${print.sha256.slice(0, 16)}…`)
    }
  }
  return problems
}

/**
 * The licence texts the artefact carries against the repository's own files.
 *
 * §2.5.1 claims the six carried members *are* the repository's six files. That is
 * the claim that discharges §1: the text travelling with `StdUtils.dll` has to be
 * the text this tree holds, byte for byte. Naming them is not enough -- the bytes
 * are what travel.
 *
 * `carried` are the extract's licence-text members (name and hash), `dir` the
 * repository's `shell/licenses/`. Both directions: a text the installer carries
 * that the tree does not hold, and a file the tree holds that the installer does
 * not carry.
 */
export function carriedLicenceTextProblems(carried, dir) {
  const problems = []
  const repository = new Map()
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isFile()) continue
    repository.set(entry.name.toLowerCase(), fingerprint(path.join(dir, entry.name)))
  }
  const carriedNames = new Set()
  for (const member of carried) {
    const name = path.posix.basename(member.member)
    const key = name.toLowerCase()
    carriedNames.add(key)
    const own = repository.get(key)
    if (!own) {
      problems.push(`the installer carries ${member.member}, which shell/licenses/ does not hold`)
      continue
    }
    if (member.sha256 && own.sha256 !== member.sha256) {
      problems.push(
        `the installer's ${name} is sha256 ${String(member.sha256).slice(0, 16)}… and shell/licenses/${name} is ${own.sha256.slice(0, 16)}… — the text travelling with the installer is not the text this tree holds`,
      )
    }
  }
  for (const [name] of repository) {
    if (!carriedNames.has(name)) {
      problems.push(`shell/licenses/${name} is not carried by the installer`)
    }
  }
  return problems
}

/**
 * What an extract actually covers.
 *
 * An extract is not the installer: it is whatever was unpacked. Measured here, the
 * 2026-11-12 build's `extract3` holds only `$PLUGINSDIR\licenses\` -- the six
 * licence texts, and none of the seven plug-in DLLs. An arm that needed the
 * plug-ins and compared the whole extract against §2.5's eight binaries would
 * report that the installer carries none of them, which is a red about the
 * record caused by an extract that never held them.
 *
 * So each arm says what its source covers: the plug-in arms need the plug-ins,
 * the payload arm needs the payload, and the licence-text arm needs the texts.
 * A source that covers a layer is evidence for that layer only.
 */
export function extractCoverage(members) {
  const plugins = members.filter((member) => /^\$PLUGINSDIR\/[^/]+\.(?:dll|exe)$/i.test(member.member))
  const payload = members.filter((member) => /^resources\/[^/]+\.(?:dll|exe)$/i.test(member.member))
  const texts = members.filter((member) => /^\$PLUGINSDIR\/licen[cs]es\//i.test(member.member))
  return {
    plugins,
    payload,
    texts,
    coversPlugins: plugins.length > 0,
    coversPayload: payload.length > 0,
    coversTexts: texts.length > 0,
    summary: [
      `${plugins.length} plug-in binary(ies)`,
      `${payload.length} payload binary(ies)`,
      `${texts.length} licence text(s)`,
    ].join(', '),
  }
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
 *
 * A directory that holds no `getBinFromUrl` call yields nothing, which is the
 * point: a caller that points this at an empty tree gets an empty list and has
 * to report that, rather than receiving a list assembled from somewhere else.
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
 * The directory that holds this exact `name@version`'s own files, if any.
 *
 * pnpm names each resolved package `<name>@<version>` plus a peer suffix, so the
 * version the lock pins selects the store directory — the declaration read is
 * then the declaration of the version the lock pins, not of whatever copy the
 * machine happens to have installed.
 *
 * The package's files are not at the top of that directory: they are under its
 * `node_modules/<name>`, which is a link, and `fs.readdirSync` reports a link as
 * neither a file nor a directory, so a recursive walk of the store directory
 * stops short of the package. Measured here: walking
 * `.pnpm/app-builder-lib@26.18.0_…/` finds no `out/toolsets/windows.js`, while
 * the same walk from `.pnpm/app-builder-lib@26.18.0_…/node_modules/app-builder-lib`
 * finds it. The caller is given the package's own directory for that reason.
 */
export function storeDirectoryFor(storeDir, name, version) {
  if (!fs.existsSync(storeDir)) return null
  const wanted = `${name}@${version}`
  const candidates = fs
    .readdirSync(storeDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && entry.name.startsWith(wanted))
    .map((entry) => path.join(storeDir, entry.name))
    .sort()
  for (const candidate of candidates) {
    const packageDir = path.join(candidate, 'node_modules', name)
    if (fs.existsSync(path.join(packageDir, 'package.json'))) return packageDir
  }
  // A directory the caller named directly, holding the package's own files.
  const direct = candidates.find((candidate) => fs.existsSync(path.join(candidate, 'package.json')))
  return direct ?? null
}

/**
 * The members of a `7z l` / `7z l -slt` listing of an NSIS installer.
 *
 * **Why the listing is a source of its own.** `$PLUGINSDIR` is an installation-time
 * temporary directory: the plug-ins are written there while the installer runs and
 * removed when it finishes. 7-Zip's NSIS handler can *list* those members but does
 * not extract them -- measured here with three `7za` invocations against the
 * 2026-11-11 build: a plain `x` yields only the payload, `-spf` yields the same,
 * and `e '$PLUGINSDIR\*'` reports `Files: 0`. So a witness that waited for an
 * extract of those members had arms that could never run on any machine.
 *
 * What the listing does give is exactly what §2.5.1's member census needs: the
 * member names, their `Packed Size` (the archive's compressed size, which is the
 * number §5.4 says it prints and §2.5 says is not the unpacked size), and the
 * absence or presence of a licence-document name. The 7-Zip build matters: the
 * system 7-Zip 26.02 (x64) reports `Type = Nsis` and lists the nine
 * `$PLUGINSDIR` members plus `$R0\Uninstall LabCairn.exe`; the 24.09 (x86) binary
 * electron-builder caches reports `Type = 7z` and lists only the outer payload.
 * `parseInstallerListing` returns the archive type with the members, so a listing
 * of the wrong layer is reported rather than mistaken for a short installer.
 *
 * Both output shapes are read. Plain `7z l` lines look like
 *
 *     2026-11-11 16:29:18 .....    123968060    123968060  $PLUGINSDIR\app-64.7z
 *                         .....                      6931  $PLUGINSDIR\System.dll
 *
 * and `-slt` gives one `Path = …` / `Packed Size = …` block per member.
 */
export function parseInstallerListing(listingText) {
  const type = /^Type\s*=\s*(\S+)/m.exec(listingText)?.[1] ?? null
  const members = []
  const seen = new Set()
  // 7-Zip's Windows output is CRLF. Every line is stripped of its CR before any
  // `$`-anchored pattern sees it: a trailing `\r` is how a first version of this
  // reader found 0 members in a listing that names all ten.
  const lines = listingText.split('\n').map((line) => line.replace(/\r$/, ''))

  /** A member of the NSIS archive, not a line from the archive's own header. */
  function looksLikeMember(name) {
    return /^\$(PLUGINSDIR|R0)[\\/]/i.test(name) || /^resources[\\/]/i.test(name)
  }

  function add(rawName, packedSize) {
    const name = rawName.trim()
    if (!name || name.endsWith('\\') || name.endsWith('/')) return
    if (!looksLikeMember(name)) return
    const member = name.replace(/\\/g, '/')
    const key = member.toLowerCase()
    if (seen.has(key)) return
    seen.add(key)
    members.push({
      member,
      name: path.posix.basename(member).toLowerCase(),
      packedSize: Number.isFinite(packedSize) && packedSize > 0 ? packedSize : null,
      // A listing names a member; it does not hold its bytes. The hash arm is
      // optional and only runs where an extract actually exists.
      sha256: null,
      path: null,
    })
  }

  // -slt shape: `Path = …` then `Packed Size = …` per member. A state machine
  // rather than a split on the `----------` separator, whose `\s*` also matches
  // newlines and swallowed every block after the first. The archive header carries
  // `Path = <installer.exe>`; `looksLikeMember` refuses it.
  let pending = null
  for (const line of lines) {
    const named = /^Path\s*=\s*([^\n]+)$/.exec(line)
    if (named) {
      if (pending) add(pending, null)
      pending = named[1].trim()
      continue
    }
    const packed = /^Packed Size\s*=\s*(\d+)/.exec(line)
    if (packed && pending) {
      add(pending, Number(packed[1]))
      pending = null
    }
  }
  if (pending) add(pending, null)

  // Plain `l` shape. The member name starts at one of the NSIS/payload roots;
  // locating it first and taking the last number before it as the packed size
  // works for both a row with one numeric column and a row with two:
  //
  //                     .....                      6931  $PLUGINSDIR\System.dll
  // 2026-11-11 16:29:18 .....    123968060    123968060  $PLUGINSDIR\app-64.7z
  //                     ....A       107520        49588  resources\elevate.exe
  const MEMBER_AT = /\$PLUGINSDIR[\\/]|\$R0[\\/]|resources[\\/]/i
  for (const line of lines) {
    const at = MEMBER_AT.exec(line)?.index
    if (at === undefined) continue
    // A `Path = …` line in an -slt listing also carries a member name; the
    // state machine above has already read it, with its own Packed Size.
    if (/^Path\s*=/.test(line)) continue
    // A `D....` row is a directory. Counting `resources\app.asar.unpacked` as a
    // binary would report a ninth member that is not a binary at all.
    if (/\bD\.{3,}[A-Za-z]?\b/.test(line.slice(0, at))) continue
    const before = line.slice(0, at)
    const numbers = [...before.matchAll(/(\d+)/g)]
    const packed = numbers.length ? Number(numbers[numbers.length - 1][1]) : null
    add(line.slice(at).trim(), packed)
  }
  return { type, members }
}

/**
 * A licence document named in a listing, where no bytes are available to read.
 *
 * `licenceDocumentKind` answers from a file's *name* or its *text*. A listing has
 * names and no text, so this is the name half of that same vocabulary -- keeping
 * the two in one place is what stops a `$PLUGINSDIR/licences/LGPL-2.1.txt` from
 * being missed by one reader and found by the other.
 */
export function listedLicenceDocuments(members) {
  return members.filter((member) => {
    const name = path.posix.basename(member.member)
    // A licence document is a name in the grant vocabulary, or a member under a
    // `licences/` directory. The compiled plug-ins, the wizard bitmap and the
    // payload archive are neither, and the `LICENCE_NAME` pattern is what keeps a
    // `.dll` from being counted as one.
    return LICENCE_NAME.test(name) || /licen[cs]es?\//i.test(member.member)
  })
}

/**
 * The compressed-size table §5.4 step 2 prints for the installer's plug-ins.
 *
 * §5.4 says plainly that these are the archive's own compressed sizes and that
 * §2.5 prints each binary's *unpacked* size instead. That distinction is why a
 * listing is useful evidence even though it carries no bytes: the seven numbers
 * §5.4 records are a second, independent statement about the same archive, and
 * they can be checked against `Packed Size` in a `7z l` output.
 *
 * The rows are `# $PLUGINSDIR\System.dll       6931   $PLUGINSDIR\nsExec.dll …`
 * — two `name size` pairs per line. A read that took §2.5's unpacked sizes as the
 * expected values would report all seven as wrong, which is a red about the
 * reader rather than about the artefact.
 */
export function compressedSizeTable(noticeText) {
  const table = new Map()
  const pattern = /\$PLUGINSDIR\\([A-Za-z0-9_.-]+\.dll)\s{2,}(\d+)/g
  for (const match of noticeText.matchAll(pattern)) {
    table.set(match[1].toLowerCase(), Number(match[2]))
  }
  if (table.size === 0) {
    throw new Error('§5.4 prints no compressed-size row — the read found nothing')
  }
  return table
}

/**
 * §5.4's compressed sizes against the `Packed Size` values in a listing.
 *
 * `recorded` comes from NOTICE; `members` come from the artefact. Both directions
 * are checked: a plug-in whose size moved, a plug-in §5.4 names that the listing
 * does not, and a listed plug-in §5.4 says nothing about all redden it. A listing
 * that carried no size at all is reported as an unmeasured value rather than
 * compared as zero -- the rule this repository prints for a number it did not
 * measure.
 */
export function listedSizeProblems(members, recorded) {
  const problems = []
  const listed = new Map(
    members
      .filter((member) => member.member.startsWith('$PLUGINSDIR/') && /\.dll$/i.test(member.name))
      .map((member) => [member.name, member.packedSize]),
  )
  for (const [name, size] of recorded) {
    if (!listed.has(name)) {
      problems.push(`§5.4 prints a compressed size for ${name}, which the listing does not name`)
      continue
    }
    const actual = listed.get(name)
    if (actual === null || actual === undefined) {
      problems.push(`the listing names ${name} but gives no Packed Size, so §5.4's ${size} could not be checked`)
      continue
    }
    if (actual !== size) {
      problems.push(`§5.4 prints ${size} compressed bytes for ${name}; the listing gives ${actual}`)
    }
  }
  for (const [name, size] of listed) {
    if (!recorded.has(name)) {
      problems.push(`the listing names ${name} (${size ?? 'no size'} compressed bytes), which §5.4 records no size for`)
    }
  }
  return problems
}

/**
 * §2.5.1's ten-member census against a listing, and the obligation state against
 * the licence documents the listing names.
 *
 * `recordedCensus` is the number §2.5.1 states for the NSIS archive, and
 * `claimsCarry` is which of its two states -- DONE or NOT DONE -- the record is
 * in. A listing that names a licence document while the record says NOT DONE is
 * exactly the state the LGPL-text batch arriving in the installer produces: the
 * record has to be re-measured, and this is the arm that says so without needing
 * the extract of an installation-time directory.
 */
/**
 * §2.5.1's three obligation states, read from their own bullets.
 *
 * The section does **not** have one state. It has three, and they are deliberately
 * different: the §1 text-and-notice obligation is DONE, the §4 corresponding-source
 * route is PARTLY DONE / NOT YET POINTED AT, and replaceability is NOT MEASURED. A
 * reader that scanned the whole section for `DONE` or `NOT DONE` would let one
 * bullet's word decide the whole record, and the word appears in all three. The
 * text-and-notice bullet is identified by its own heading, and the other two are
 * required to be present so the shape is watched rather than assumed.
 */
export function obligationStates(noticeText) {
  const section = noticeSubsection(noticeText, '2.5.1').join(' ')
  const textAndNotice = /\*\*The licence text and the notice \(§1, §6\) — (DONE|NOT DONE)\.\*\*/.exec(section)
  const correspondingSource = /\*\*The corresponding source \(§4, §6\(c\)\) — PARTLY DONE/.test(section)
  const replaceability = /\*\*Replaceability \(§6\(b\)[^*]*— NOT\s+MEASURED\.\*\*/.test(section)
  return {
    textAndNotice: textAndNotice ? textAndNotice[1] : null,
    correspondingSource,
    replaceability,
  }
}

/**
 * How many licence texts §2.5.1 says the archive carries.
 *
 * The section states "six of them are the licence texts under
 * `$PLUGINSDIR\licenses\`" for the 2026-11-12 build, and "none of them is a licence
 * document" for the older one. That number is a claim about the artefact, not a
 * restatement of DONE: a record can say DONE while naming five, or NOT DONE while
 * naming none, and the listing is what decides. `null` means the section printed no
 * count at all, which is reported rather than compared as zero.
 */
export function licenceTextCountClaim(noticeText) {
  const section = noticeSubsection(noticeText, '2.5.1').join(' ')
  const none = /none of them is a licence\s+document/i.test(section)
  if (none) return 0
  // The section wraps this sentence, and `join(' ')` keeps each line's leading
  // indentation -- "six of them are     the licence texts". A pattern that
  // required one space read nothing out of a section that states the count
  // plainly, and the text-count arm then reported itself as unmeasurable.
  const match = /\*\*(\w+)\*\* of them are\s+the licence texts/i.exec(section)
    ?? /(\w+) of them are\s+the licence texts/i.exec(section)
  if (!match) return null
  return _COUNT_WORDS[match[1].toLowerCase()] ?? null
}

const _COUNT_WORDS = {
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8,
  nine: 9, ten: 10, eleven: 11, twelve: 12, thirteen: 13, fourteen: 14,
  fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18, nineteen: 19, twenty: 20,
}

/**
 * §2.5.1's ten/sixteen-member census and its licence-text state against a listing.
 *
 * Two independent properties are checked against the same artefact:
 *
 *   * the archived member count and the seven plug-in DLLs;
 *   * the **§1 text-and-notice state and its stated text count**: `DONE` with the
 *     stated number of `licences/` documents, or `NOT DONE` with none. Both
 *     consistent states must pass -- this is an equivalence, not a rule that
 *     requires one particular word. Either direction of disagreement reddens it.
 *
 * `recordedTexts` is §2.5.1's own number (`null` when it prints none). The other
 * two obligation states are required to be present: reading the whole section as
 * one DONE/NOT DONE sentence would let the §4 or §6(b) bullet decide the §1 arm.
 */
export function listedCensusProblems(
  members,
  recordedCensus,
  claimsCarry,
  licenceDocuments,
  recordedTexts = null,
) {
  const problems = []
  const plugin = members.filter((member) => member.member.startsWith('$PLUGINSDIR/'))
  const uninstaller = members.filter((member) => /^\$R0\//.test(member.member))
  if (plugin.length + uninstaller.length !== recordedCensus) {
    problems.push(
      `§2.5.1 counts ${recordedCensus} members in the NSIS archive; the listing presents ` +
      `${plugin.length} under $PLUGINSDIR and ${uninstaller.length} at $R0 = ` +
      `${plugin.length + uninstaller.length}`,
    )
  }
  const pluginDlls = plugin.filter((member) => /\.dll$/i.test(member.name))
  if (pluginDlls.length !== 7) {
    problems.push(
      `§2.5.1 counts seven plug-in DLLs under $PLUGINSDIR; the listing presents ${pluginDlls.length}`,
    )
  }
  const docs = licenceDocuments.filter((member) => member.member.startsWith('$PLUGINSDIR/'))
  if (claimsCarry && docs.length === 0) {
    problems.push(
      '§2.5.1 records the licence-text obligation as DONE, but the listing names no licence '
      + 'document under $PLUGINSDIR — the record claims something the artefact does not',
    )
  }
  if (!claimsCarry && docs.length > 0) {
    problems.push(
      `§2.5.1 records the licence-text obligation as NOT DONE, but the listing names `
      + `${docs.length} licence document(s) under $PLUGINSDIR `
      + `(${docs.map((member) => member.member).join(', ')}) — the record is behind the `
      + 'artefact, and §2.5.1 has to be re-measured against it',
    )
  }
  if (recordedTexts === null) {
    problems.push(
      '§2.5.1 states no count of licence texts for the NSIS archive, so its "six of them '
      + 'are the licence texts" claim has nothing to compare with the listing',
    )
  } else if (recordedTexts !== docs.length) {
    problems.push(
      `§2.5.1 states ${recordedTexts} licence text(s) in the NSIS archive; the listing `
      + `names ${docs.length} under $PLUGINSDIR`,
    )
  }
  return problems
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

/**
 * Whether an extract member is a licence document, and on what grounds.
 *
 * `licenceDocumentKind`'s answer for the member's real path, attached when the
 * member is read: the claim §2.5.1 makes is about *what the archive holds*, and
 * a member identified only by a name pattern is a claim about names.
 */
export function isLicenceDocument(member) {
  return licenceDocumentKind(member.path) !== null
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

// ---------------------------------------------------------------------------
// The comparisons, as functions that take data rather than opening artefacts.
//
// A witness that compares the artefacts it opened inside its own test body
// cannot be shown to fail for the property: the only way to hand it a broken
// value is to break the artefact, which is a build, a download or a tree
// mutation. These three take what the record states and what the artefact
// presents, and answer with the problems. The witness feeds them the real
// bytes; the controls feed them records with a value changed. Same code both
// ways — `shell/test/dependency-surface.test.mjs`'s precedent.
// ---------------------------------------------------------------------------

/**
 * §2.5's per-binary records against the files the bundle really holds.
 *
 * `filesByLowerName` maps a lower-cased file name to every fingerprint found for
 * it in the bundle the records name. A record whose sha256 is none of them is the
 * plug-in-swap case: same name, same size, different bytes, terms nobody read.
 */
export function binaryRecordProblems(records, filesByLowerName) {
  const problems = []
  for (const record of records) {
    const found = filesByLowerName.get(record.name.toLowerCase()) ?? []
    const match = found.find((print) => print.sha256 === record.fields.sha256)
    if (!match) {
      const detail = found.length
        ? `the bundle holds ${found.length} file(s) of that name, whose sha256s are ${found.map((c) => `${c.sha256.slice(0, 16)}…`).join(', ')}`
        : 'the bundle holds no file of that name'
      problems.push(`${record.name}: §2.5 records sha256 ${(record.fields.sha256 ?? '(none)').slice(0, 16)}… but ${detail}`)
      continue
    }
    if (match.bytes !== record.bytes) {
      problems.push(`${record.name}: §2.5 records ${record.bytes} bytes but the real file is ${match.bytes}`)
    }
  }
  return problems
}

/**
 * Which layer a §2.5 record's `path` field places it in.
 *
 * §2.5's eight records span two *different* archives: seven plug-ins in the NSIS
 * installer's `$PLUGINSDIR`, and `elevate.exe` inside the payload's `resources/`.
 * A `7z l` of the installer lists the first layer only; the payload needs its own
 * listing (or an extract). Comparing all eight records against a single-layer
 * listing reports `elevate.exe` as missing -- a false red about the record caused
 * by an absent source, which is exactly the kind of red that gets a witness
 * disabled. Keeping the layer with the record is what makes a partial source an
 * honest NOT RUN.
 */
export function recordLayer(record) {
  const recordedPath = record.fields.path ?? ''
  if (/\$PLUGINSDIR/i.test(recordedPath)) return 'plugins'
  if (/\bresources\b/i.test(recordedPath)) return 'payload'
  return 'unknown'
}

/**
 * §2.5's records against the binaries an artefact actually carries, both ways.
 *
 * A carried binary no record names is the defect §2.5.2 records as unwitnessed;
 * a record naming a binary the artefact does not carry means §2.5 is describing
 * an artefact that no longer contains it. `layers` names the layers a source was
 * actually available for, so records in an unmeasured layer are excluded from
 * both sides rather than reported as findings.
 */
export function memberRecordProblems(members, records, layers = ['plugins', 'payload']) {
  const measured = new Set(layers)
  // A record in an unmeasured layer has no evidence either way. Excluding it is
  // not the same as passing it: the caller reports that layer as NOT RUN, and the
  // other layer's comparison still has to hold.
  const comparable = records.filter((record) => measured.has(recordLayer(record)))
  const recorded = new Map(comparable.map((record) => [record.name.toLowerCase(), record]))
  const carried = members
    .filter((member) => measured.has(member.member.startsWith('$PLUGINSDIR/') ? 'plugins' : /^resources\//.test(member.member) ? 'payload' : 'unknown'))
    .map((member) => path.basename(member.member).toLowerCase())
  return {
    unrecorded: [...new Set(carried.filter((name) => !recorded.has(name)))].sort(),
    missing: comparable
      .map((record) => record.name.toLowerCase())
      .filter((name) => !carried.includes(name))
      .sort(),
    measuredLayers: [...measured].sort(),
  }
}

/**
 * §2.5's bundle names against the bundles the pinned toolchain declares.
 *
 * Independent of NOTICE's own numbers: `app-builder-lib` states the bundle names
 * and the checksums it verifies, and that is a second statement about the same
 * archives §2.5 hashes.
 */
export function toolchainRecordProblems(records, declarations) {
  const named = new Set(declarations.map((declaration) => declaration.bundle))
  const problems = []
  for (const bundle of new Set(records.map((record) => bundleNamedFromRecord(record)).filter(Boolean))) {
    if (!named.has(bundle)) {
      problems.push(
        `§2.5 records binaries from ${bundle}, but the pinned toolchain declares ${[...named].join(', ') || 'no bundle'} — the toolchain §2.5 describes is not the one this build fetches`,
      )
    }
  }
  return problems
}

/** The bundle a §2.5 record names, before any path or comparison after it. */
export function bundleNamedFromRecord(record) {
  const match = /^(nsis-resources-[\d.]+|nsis-[\d.]+)/.exec(record.fields.bundle ?? '')
  return match ? match[1] : null
}

// ---------------------------------------------------------------------------
// Where a named licence's terms come from.
//
// `nsis-resources-3.4.1` carries no licence document. §2.5's records therefore
// name the *upstream* source of each grant: a plug-in's own source header, the
// 7-Zip terms, and -- after the upstream-provenance review -- NSIS 3.13's
// `LICENSES` tree, which attributes UAC.dll and WinShell.dll to their upstream
// release archives. Those are different artefacts from the bundle the build
// downloads, and keeping them apart is the point: a source inside the bundle is
// not the same claim as a source in NSIS's own release tree.
// ---------------------------------------------------------------------------

/** A short `sha256 997fd014…` reference as §2.5 writes it. */
const SHORT_HASH = /sha256\s+([0-9a-f]{8})…/gi

/** A source named in a §2.5 `where` field: an URL or a backticked file path. */
const SOURCE_PATH = /`([^`]+)`|https?:\/\/[^\s`.,;)]+/g

/**
 * Read the "where the terms come from" claims out of one §2.5 record.
 *
 * Two shapes count as a source: a named path/URL, and a short sha256 that binds
 * the claim to a specific artefact. A record with a named licence but neither is
 * the defect this reads for -- a grant with no provenance. A record with only a
 * hash and no path is incomplete in the other direction: the hash says *which*
 * bytes, but not *where* they came from.
 */
export function termsSources(record) {
  const where = record.fields.where ?? ''
  const hashes = [...where.matchAll(SHORT_HASH)].map((match) => match[1].toLowerCase())
  const paths = [...where.matchAll(SOURCE_PATH)].map((match) => (match[1] ?? match[0]).trim())
  // A source route is either an upstream URL/archive, a file inside the NSIS
  // LICENSES tree, or a *prose* statement of where the grant is stated. StdUtils
  // is the third shape: §2.5 says "the plug-in's own source header states the
  // grant" and names no backticked path, because the header does not survive into
  // the installer. That is a source and a limit, not an absence -- demanding a
  // path for it would turn a correct record into a failure for a reason that has
  // nothing to do with the property under watch.
  const named = paths.filter((value) =>
    /nsis\.sourceforge\.io|github\.com|LICENSES|\.zip|\.txt|api\.h|COPYING|source header|7-Zip/i.test(value),
  )
  const proseSource = /source header states the grant|7-Zip's terms|compiled binary carries no licence text|LICENSES` tree|upstream NSIS/i.test(where)
  return { hashes, paths: named, proseSource, hasTermsSource: named.length > 0 || proseSource, text: where }
}

/**
 * §2.5's named-licence records against the requirement that each names its source.
 *
 * No count is watched: the number of plug-ins whose terms have been resolved is a
 * measurement that can grow as upstream provenance is found. What must hold is
 * that every record stating a specific licence states where that licence comes
 * from, and every short hash it quotes is bound to a named source. A record still
 * marked `unresolved` is allowed to have none: that is what the word means.
 */
export function termsSourceProblems(records) {
  const problems = []
  let named = 0
  for (const record of records) {
    const licence = record.fields.licence ?? ''
    if (/unresolved/i.test(licence)) continue
    named += 1
    const source = termsSources(record)
    if (!source.hasTermsSource) {
      problems.push(`${record.name}: §2.5 records ${JSON.stringify(licence)} but its \`where\` field names no source for the terms`)
    }
    if (source.hashes.length > 0 && source.paths.length === 0) {
      problems.push(`${record.name}: §2.5 quotes ${source.hashes.length} sha256 value(s) but names no source path they belong to`)
    }
  }
  if (named === 0) {
    problems.push('§2.5 names no licence at all for these binaries, so the source requirement has nothing to watch')
  }
  return { problems, named }
}

/**
 * The short hashes §2.5 quotes against the files in an upstream provenance tree.
 *
 * `LABCAIRN_LICENCE_UPSTREAM_DIR` names a directory holding NSIS 3.13's
 * `LICENSES` tree (and, optionally, the upstream release archives). Each short
 * hash is looked up by hashing the files under that directory: a match proves the
 * record's quoted bytes are really there, a miss says so by name. The lookup is
 * deliberately over files rather than over a hard-coded path list -- §2.5's
 * `where` fields name paths inside an upstream tree whose layout is not this
 * repository's to pin.
 */
export function upstreamHashProblems(records, upstreamDirs) {
  // The upstream evidence lives in more than one place: NSIS 3.13's `LICENSES`
  // tree holds the licence texts (UAC's `License.txt`, WinShell's
  // `NOTICE-plugin-api.txt`, nsis7z's `DOC/License.txt`), while the release
  // archives themselves (`UAC.zip`, `WinShell.zip`) were fetched into a separate
  // provenance directory for the obligation review. Both are named by
  // `LABCAIRN_LICENCE_UPSTREAM_DIR`, `path.delimiter`-separated.
  const dirs = (Array.isArray(upstreamDirs) ? upstreamDirs : [upstreamDirs])
    .filter(Boolean)
    .filter((dir) => fs.existsSync(dir))
  if (dirs.length === 0) {
    return { available: false, problems: [], unmeasured: records.flatMap((record) => termsSources(record).hashes) }
  }
  const real = new Map()
  for (const dir of dirs) {
    for (const file of bundleFiles(dir)) {
      const print = fingerprint(file)
      real.set(print.sha256.slice(0, 8), { file, ...print })
    }
  }
  const problems = []
  const matched = []
  for (const record of records) {
    for (const short of termsSources(record).hashes) {
      const found = real.get(short)
      if (!found) {
        problems.push(`${record.name}: §2.5 quotes sha256 ${short}… and no file under ${dirs.join(', ')} hashes to it`)
        continue
      }
      matched.push({ record: record.name, short, ...found })
    }
  }
  return { available: true, problems, matched, unmeasured: [] }
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
