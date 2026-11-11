/**
 * The shell lockfile read, as NOTICE §5.3 names it.
 *
 * **Why this file exists.** NOTICE §5 used to name `pnpm --dir shell list
 * --depth Infinity` as the command that produces the shell's resolved set.
 * Measured on 2026-11-11 on a copy of `shell/package.json` and
 * `shell/pnpm-lock.yaml` outside the repository, with node v24.16.0 and
 * pnpm 9.15.9: with no installed tree that command prints **0 bytes on stdout,
 * 0 on stderr, and exits 0**. A reproduction section whose first command
 * silently prints nothing is not a reproduction. This script reads the same
 * figures out of the lockfile itself, so it works on a fresh checkout with
 * nothing installed and no network.
 *
 * **What it reads, and why those numbers differ.** A lockfileVersion 9 file
 * names packages in two sections: `packages:` carries the bare
 * `name@version` keys, `snapshots:` carries the resolved dependency maps and
 * *additionally* keys whose name carries a peer-resolution suffix. So the key
 * count and the package count are different numbers, and both are real: this
 * file prints each one rather than a single figure a reader would misread.
 *
 * **This is the reader the witnesses use.** `shell/test/notice-licences.test.mjs`
 * imports `lockfileKeys` and `closureOf` rather than carrying its own copy, so
 * its mutation controls feed altered text through *this* code — a reader that
 * cannot be tested is a reader that can be turned off.
 *
 * Usage: node .github/shell-lockfile-keys.mjs [path/to/pnpm-lock.yaml]
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * Top-level keys of one lockfile section.
 *
 * A section key sits at two spaces and carries nothing after its colon except
 * an inline empty map (`{}`); everything more deeply indented belongs to the
 * preceding key. Getting this wrong is how a first attempt counted 272 in
 * `packages:`: a reader that only matches a colon at end of line silently drops
 * the 118 entries written as `'name@version': {}` and picks up other things
 * instead.
 */
export function sectionKeys(text, sectionName) {
  const header = `\n${sectionName}:\n`
  const at = text.indexOf(header)
  if (at < 0) throw new Error(`the lockfile has no '${sectionName}:' section`)
  const body = text.slice(at + header.length)
  const keys = new Map()
  for (const line of body.split('\n')) {
    if (line.trim() === '') continue
    if (!line.startsWith('  ')) break // a column-zero line: the next top-level section
    const match = line.match(/^  ('([^']+)'|[^:\s][^:]*):(?:\s*\{\})?\s*$/)
    if (match) keys.set(match[2] ?? match[1], true)
  }
  return [...keys.keys()]
}

/**
 * The direct dependencies the lockfile's own `importers:` section names.
 *
 * Read from the lock rather than from package.json, because the resolution the
 * closure must start from is the one the lock recorded — including the peer
 * suffix `electron-builder` resolves with.
 */
export function directDependencies(text) {
  const at = text.indexOf('\nimporters:\n')
  if (at < 0) throw new Error('the lockfile has no importers: section')
  const block = text.slice(at, text.indexOf('\npackages:\n', at))
  const out = []
  const pattern = /^      ([^\n]+):\n(?:[^\n]*\n){0,3}?        version: '?([^'\n]+?)'?$/gm
  for (const match of block.matchAll(pattern)) out.push({ name: match[1], specifier: match[2] })
  if (out.length === 0) throw new Error('importers: names no dependency — the read found nothing')
  return out
}

/** `name@version`, with any peer-resolution suffix removed. */
export function bareKey(key) {
  const s = key.startsWith('/') ? key.slice(1) : key
  const at = s.indexOf('@', s.startsWith('@') ? 1 : 0)
  if (at < 0) throw new Error(`not a name@version key: ${key}`)
  const name = s.slice(0, at)
  let version = s.slice(at + 1)
  const cut = version.indexOf('(')
  if (cut >= 0) version = version.slice(0, cut)
  return `${name}@${version}`
}

/** The resolved dependency maps, read out of `snapshots:` — where v9 puts them. */
export function snapshotEdges(text) {
  const header = '\nsnapshots:\n'
  const at = text.indexOf(header)
  if (at < 0) throw new Error('the lockfile has no snapshots: section')
  const body = text.slice(at + header.length)
  const edges = new Map()
  let current = null
  let bucket = null
  for (const line of body.split('\n')) {
    if (line.trim() === '') continue
    if (!line.startsWith('  ')) break
    const key = line.match(/^  ('([^']+)'|[^:\s][^:]*):(?:\s*\{\})?\s*$/)
    if (key) {
      current = key[2] ?? key[1]
      if (!edges.has(current)) edges.set(current, [])
      bucket = null
      continue
    }
    if (/^    (dependencies|optionalDependencies):\s*$/.test(line)) {
      bucket = line.trim().split(':')[0]
      continue
    }
    if (/^    (peerDependencies|peerDependenciesMeta|transitivePeerDependencies):/.test(line)) {
      bucket = null // peers are named, not bundled: they are not edges of the closure
      continue
    }
    if (current && bucket) {
      // A dependency *name* is quoted when it needs it (`'@electron/get': 5.1.0`),
      // and its version may be quoted as well. Unquoting only the version — the
      // shape a first attempt matched — leaves the quotes inside the name, and
      // every scoped dependency then fails to resolve.
      const dep = line.match(/^      ('([^']+)'|[^:]+):\s*'?([^'\n]+?)'?\s*$/)
      if (dep) edges.get(current).push({ name: dep[2] ?? dep[1], version: dep[3], kind: bucket })
    }
  }
  return edges
}

/** Candidate lock keys a `name@version` reference could resolve to. */
function candidates(name, version, allKeys) {
  const raw = version.startsWith('/') ? version.slice(1) : `${name}@${version}`
  const out = [raw]
  let stem = raw
  while (stem.includes('(')) {
    stem = stem.slice(0, stem.lastIndexOf('('))
    out.push(stem)
  }
  for (const key of allKeys) if (bareKey(key) === bareKey(raw) && key !== raw) out.push(key)
  return out
}

/**
 * Everything reachable from one direct dependency, by `name@version`.
 *
 * Edges come from `snapshots:` only. A bare-only key borrows the resolved map of
 * its bare form, which is what the lockfile layout means by splitting catalog
 * from resolution.
 */
export function closureOf(text, startName, startVersion) {
  const keys = new Set([...sectionKeys(text, 'packages'), ...sectionKeys(text, 'snapshots')])
  const edges = snapshotEdges(text)
  const start = candidates(startName, startVersion, keys).find((c) => keys.has(c))
  if (!start) throw new Error(`${startName}@${startVersion} is not a key in this lockfile`)
  const seen = new Set([bareKey(start)])
  const queue = [start]
  const unresolved = []
  while (queue.length > 0) {
    const key = queue.shift()
    const own = edges.get(key) ?? edges.get(bareKey(key))
    if (own === undefined) continue // a package the lock records with no resolved map
    for (const dep of own) {
      const resolved = candidates(dep.name, dep.version, keys).find((c) => keys.has(c))
      if (!resolved) {
        unresolved.push(`${key} -> ${dep.name}@${dep.version}`)
        continue
      }
      const bare = bareKey(resolved)
      if (!seen.has(bare)) {
        seen.add(bare)
        queue.push(resolved)
      }
    }
  }
  return { entries: [...seen], unresolved }
}

/** Every count NOTICE §2.4 prints, derived from the lock's own text. */
export function lockfileKeys(text) {
  const packages = sectionKeys(text, 'packages')
  const snapshots = sectionKeys(text, 'snapshots')
  const union = new Set([...packages, ...snapshots])
  const suffixOnly = [...union].filter((k) => k.includes('('))
  const bare = new Set([...union].map(bareKey))
  const names = new Map()
  for (const key of bare) {
    const name = key.slice(0, key.lastIndexOf('@'))
    names.set(name, (names.get(name) ?? 0) + 1)
  }
  const direct = directDependencies(text)
  const electron = direct.find((d) => d.name === 'electron')
  const builder = direct.find((d) => d.name === 'electron-builder')
  if (!electron || !builder) {
    throw new Error(`the lock's importers name ${direct.map((d) => d.name).join(', ')}; NOTICE §2.4 is written for electron and electron-builder`)
  }
  const runtime = closureOf(text, electron.name, electron.specifier)
  const build = closureOf(text, builder.name, builder.specifier)
  const runtimeSet = new Set(runtime.entries)
  const buildSet = new Set(build.entries)
  const shared = [...runtimeSet].filter((k) => buildSet.has(k))
  return {
    packages_keys: packages.length,
    snapshots_keys: snapshots.length,
    union_keys: union.size,
    peer_suffixed_keys: suffixOnly.length,
    distinct_name_version: bare.size,
    distinct_names: names.size,
    names_at_more_than_one_version: [...names.values()].filter((n) => n > 1).length,
    runtime_closure: runtimeSet.size,
    build_closure: buildSet.size,
    shared_by_both_closures: shared.length,
    build_only: [...buildSet].filter((k) => !runtimeSet.has(k)).length,
    entries_in_neither_closure: [...bare].filter((k) => !runtimeSet.has(k) && !buildSet.has(k)).length,
    unresolved_edges: [...runtime.unresolved, ...build.unresolved],
    runtime_entries: [...runtimeSet].sort(),
    build_only_entries: [...buildSet].filter((k) => !runtimeSet.has(k)).sort(),
  }
}

/** Accept either a path to the lock or the directory the lock lives in. */
function resolveLock(arg) {
  const resolved = path.resolve(arg)
  if (fs.existsSync(resolved) && fs.statSync(resolved).isDirectory()) {
    return path.join(resolved, 'pnpm-lock.yaml')
  }
  return resolved
}

function main() {
  const target = resolveLock(process.argv[2] ?? 'shell/pnpm-lock.yaml')
  const text = fs.readFileSync(target, 'utf8')
  const counts = lockfileKeys(text)
  for (const key of [
    'packages_keys', 'snapshots_keys', 'union_keys', 'peer_suffixed_keys',
    'distinct_name_version', 'distinct_names', 'names_at_more_than_one_version',
    'runtime_closure', 'build_closure', 'shared_by_both_closures', 'build_only',
    'entries_in_neither_closure',
  ]) {
    console.log(`${key}: ${counts[key]}`)
  }
  console.log(`unresolved_edges: ${counts.unresolved_edges.length}`)
  if (counts.unresolved_edges.length > 0) {
    for (const edge of counts.unresolved_edges) console.error(`  unresolved: ${edge}`)
    process.exitCode = 1
  }
}

const invokedDirectly =
  process.argv[1] !== undefined &&
  fs.realpathSync(path.resolve(process.argv[1])) === fs.realpathSync(fileURLToPath(import.meta.url))
if (invokedDirectly) main()
