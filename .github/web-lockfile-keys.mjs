/**
 * The web tree's lockfile read, as NOTICE §5.4 names it.
 *
 * **Why this file exists.** `web/pnpm-lock.yaml` is a lockfileVersion 9 file,
 * and it carries **no licence field at all** — the substring `licen` does not
 * occur in it. So the lock pins *identity* and never *terms*, and the terms have
 * to be read from somewhere else. This file separates the two: it reads the
 * identity out of the lock (no install, no network, fresh checkout) and, when
 * an installed tree is given, reads the declared licence out of each package's
 * own `package.json`.
 *
 * **Why the counts are printed separately rather than as one number.** A
 * lockfileVersion 9 file names packages in two sections: `packages:` carries the
 * bare `name@version` keys, `snapshots:` carries the resolved dependency maps
 * and additionally the keys whose name carries a peer-resolution suffix. The
 * key count, the distinct-package count and the installed-copy count are three
 * different numbers and all three are real; a reader that printed only one of
 * them would be misread. This is the same reason
 * `.github/shell-lockfile-keys.mjs` prints each of the shell's figures
 * separately.
 *
 * **The reader is shared with the shell's, not copied.** `sectionKeys` and
 * `bareKey` are imported from `.github/shell-lockfile-keys.mjs`, so the lockfile
 * grammar is read by one tested piece of code. A second copy of the grammar is
 * a second thing that can stop reading the lock, and the failure would look
 * like a licence that changed.
 *
 * **This is the reader the witness uses.** `shell/test/notice-scope.test.mjs`
 * imports `webLockKeys` and `installedPackages` rather than carrying its own
 * copy, so its mutation controls feed altered text through *this* code — a
 * reader that cannot be tested is a reader that can be turned off.
 *
 * Usage:
 *   node .github/web-lockfile-keys.mjs web/pnpm-lock.yaml
 *   node .github/web-lockfile-keys.mjs web/pnpm-lock.yaml --installed
 *   node .github/web-lockfile-keys.mjs web/pnpm-lock.yaml --installed --registry
 *   node .github/web-lockfile-keys.mjs web/pnpm-lock.yaml --installed --store <dir>
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { sectionKeys, bareKey } from './shell-lockfile-keys.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))

/**
 * The identity the lock pins, and the licence fields it does not carry.
 *
 * `licence_field_occurrences` counts the case-insensitive substring `licen`
 * anywhere in the lock text. It is printed because a reader who assumes a
 * lockfile records licences has to be shown that this one does not: the
 * absence is a measured fact, not an omission in this file.
 */
export function webLockKeys(text) {
  const packages = sectionKeys(text, 'packages')
  const snapshots = sectionKeys(text, 'snapshots')
  const union = new Set([...packages, ...snapshots])
  const bare = union.size > 0 ? [...union].map(bareKey) : []
  return {
    packages_keys: packages.length,
    snapshots_keys: snapshots.length,
    union_keys: union.size,
    peer_suffixed_keys: [...union].filter((k) => k.includes('(')).length,
    distinct_name_version: new Set(bare).size,
    licence_field_occurrences: (text.match(/licen/gi) ?? []).length,
    packages_entries: packages,
  }
}

/**
 * Every `package.json` the installed web tree presents.
 *
 * **What a record is here, and why the count is larger than the package
 * count.** The pnpm store holds one directory per resolved package under
 * `<store>/<name>@<version>_<peer-hash>/`, and that directory's `node_modules/`
 * contains the package itself plus a link to each of its dependencies. Reading
 * the tree the way the install presents it — following those links — meets the
 * same manifest many times over, once through each store directory that links
 * to it. So two numbers come out of one walk, and they are not the same
 * number: `installed_records` counts the records the tree presents, and
 * `installed_distinct_name_version` counts the distinct packages among them.
 *
 * A record is a `package.json` whose path below the store directory holds
 * exactly one `node_modules` segment — the package's own manifest, not a
 * nested dependency's, which sits below a second one.
 *
 * The walk follows links, so it needs a cycle guard: a directory already on
 * the current path is not entered again. The guard is per *path* and not per
 * *target*, because meeting the same package twice through two different
 * links is the thing being counted.
 */
export function installedPackages(storeDir) {
  const records = []
  if (!fs.existsSync(storeDir)) return records
  const storeDirs = fs
    .readdirSync(storeDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(storeDir, entry.name))
  for (const store of storeDirs) {
    const modules = path.join(store, 'node_modules')
    if (!fs.existsSync(modules)) continue
    for (const pkgJson of packageJsonFiles(modules, [])) {
      const relative = path.relative(store, pkgJson)
      const segments = relative.split(/[\\/]/)
      if (segments.filter((s) => s === 'node_modules').length !== 1) continue
      let data
      try {
        data = JSON.parse(fs.readFileSync(pkgJson, 'utf8'))
      } catch {
        continue
      }
      if (!data || typeof data.name !== 'string') continue
      records.push({
        name: data.name,
        version: typeof data.version === 'string' ? data.version : '',
        license: data.license ?? null,
        path: pkgJson,
      })
    }
  }
  return records
}

/** Every `package.json` under `dir`, following directory links. */
function packageJsonFiles(dir, chain) {
  const out = []
  let real
  try {
    real = fs.realpathSync(dir)
  } catch {
    return out
  }
  if (chain.includes(real)) return out
  const nextChain = [...chain, real]
  let entries
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true })
  } catch {
    return out
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      out.push(...packageJsonFiles(full, nextChain))
    } else if (entry.isSymbolicLink()) {
      let isDirectory = false
      try {
        isDirectory = fs.statSync(full).isDirectory()
      } catch {
        isDirectory = false
      }
      if (isDirectory) out.push(...packageJsonFiles(full, nextChain))
    } else if (entry.isFile() && entry.name === 'package.json') {
      out.push(full)
    }
  }
  return out
}

/**
 * The declared licence of each lock key, resolved from the installed tree.
 *
 * A key the installed tree cannot answer is returned in `unresolved` rather
 * than guessed: the platform variants of a native package are absent from a
 * Windows tree, and a licence filled in from the family would be a claim
 * nothing measured.
 */
export function resolveFromInstalled(packagesEntries, records) {
  const byKey = new Map()
  for (const record of records) {
    const key = `${record.name}@${record.version}`
    if (!byKey.has(key)) byKey.set(key, record.license)
  }
  const licences = new Map()
  const unresolved = []
  for (const entry of packagesEntries) {
    const key = bareKey(entry)
    if (byKey.has(key)) licences.set(entry, byKey.get(key))
    else unresolved.push(entry)
  }
  return { licences, unresolved }
}

/**
 * The declared licence of each lock key, from the npm registry.
 *
 * The registry record is the same field the installed tree's `package.json`
 * carries, read from the published package rather than from the install. This
 * is what answers the lock keys a single-platform install cannot: the native
 * packages' other-platform variants.
 */
export async function resolveFromRegistry(entries) {
  const licences = new Map()
  const unresolved = []
  for (const entry of entries) {
    const key = bareKey(entry)
    const at = key.lastIndexOf('@')
    const name = key.slice(0, at)
    const version = key.slice(at + 1)
    const url = `https://registry.npmjs.org/${encodeURIComponent(name)}/${encodeURIComponent(version)}`
    let record
    try {
      const response = await fetch(url)
      if (!response.ok) throw new Error(`registry answered ${response.status}`)
      record = await response.json()
    } catch (error) {
      unresolved.push(entry)
      continue
    }
    licences.set(entry, record?.license ?? null)
  }
  return { licences, unresolved }
}

/** `identifier -> count`, most common first. */
export function classCounts(licences) {
  const counts = new Map()
  for (const licence of licences.values()) {
    const key = String(licence)
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
}

/**
 * The command line: print the figures and exit non-zero when a step could not
 * be completed. A reproduction command that prints a partial set without
 * saying so is the failure mode `.github/shell-lockfile-keys.mjs` was written
 * to avoid.
 */
async function main(argv) {
  const lockPath = argv[0] ?? 'web/pnpm-lock.yaml'
  const useInstalled = argv.includes('--installed')
  const useRegistry = argv.includes('--registry')
  const storeIndex = argv.indexOf('--store')
  if (!fs.existsSync(lockPath)) {
    console.error(`no such lockfile: ${lockPath}`)
    process.exitCode = 1
    return
  }
  const text = fs.readFileSync(lockPath, 'utf8')
  const keys = webLockKeys(text)
  console.log(`packages_keys: ${keys.packages_keys}`)
  console.log(`snapshots_keys: ${keys.snapshots_keys}`)
  console.log(`union_keys: ${keys.union_keys}`)
  console.log(`peer_suffixed_keys: ${keys.peer_suffixed_keys}`)
  console.log(`distinct_name_version: ${keys.distinct_name_version}`)
  console.log(`licence_field_occurrences: ${keys.licence_field_occurrences}`)

  if (!useInstalled && !useRegistry) return

  const storeDir =
    storeIndex >= 0 && argv[storeIndex + 1]
      ? path.resolve(argv[storeIndex + 1])
      : path.resolve(HERE, '..', 'web', 'node_modules', '.pnpm')
  const records = installedPackages(storeDir)
  console.log(`installed_records: ${records.length}`)
  console.log(`installed_distinct_name_version: ${new Set(records.map((r) => `${r.name}@${r.version}`)).size}`)

  const installed = resolveFromInstalled(keys.packages_entries, records)
  const licences = new Map(installed.licences)
  let unresolved = installed.unresolved
  if (useRegistry) {
    const fetched = await resolveFromRegistry(unresolved)
    for (const [entry, licence] of fetched.licences) licences.set(entry, licence)
    unresolved = fetched.unresolved
  }
  console.log(`resolved_keys: ${licences.size}`)
  console.log(`unresolved_keys: ${unresolved.length}`)
  for (const entry of unresolved) console.log(`  unresolved: ${entry}`)
  console.log('licence classes:')
  for (const [licence, count] of classCounts(licences)) {
    console.log(`  ${licence.padEnd(24)} ${String(count).padStart(4)}`)
  }
  if (unresolved.length > 0) process.exitCode = 1
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await main(process.argv.slice(2))
}
