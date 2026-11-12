/**
 * The third-party attribution that ships with the built workbench.
 *
 * **Why this file exists.** The bundle in `dist/` carries no licence banner.
 * The bundler drops the comments the licence notices lived in, so the MIT
 * attribution of React and its two siblings is not in the artefact that is
 * installed on a person’s machine — measured on 2026-11-11: the built bundle
 * names `MIT` zero times, `Copyright` zero times and `license` zero times.
 * MIT asks for the notice to travel with the software, so the notice is put
 * in a file that travels with it.
 *
 * **Why the list is measured rather than written.** The packages that reach
 * the bundle are not the packages the project has installed: the build
 * toolchain, the type definitions and the test helpers are installed and are
 * not shipped. A hand-written list is a list of what somebody believed, and
 * the belief goes stale the first time a dependency moves. So the list is
 * read out of the bundle the build actually produced — the bundler’s own
 * module graph — and every field of every entry is read out of the installed
 * package’s own `package.json` and its own licence file.
 *
 * **What is in scope.** A package is listed when the bundler placed that
 * package’s published source files into the bundle. The bundler’s own
 * emitted runtime (the module-preload polyfill and the runtime helpers) is
 * listed too, under the package that provides it: that code is in the
 * artefact, and an attribution file that left it out would be incomplete in
 * exactly the way this file exists to fix.
 *
 * **What is not in scope.** The project’s own source is not third-party code,
 * and LabCairn’s own licence is the repository’s root `LICENSE` file. This
 * file covers third-party code only and does not restate LabCairn’s grant.
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import type { Plugin } from 'vite'

/** The name of the file the notices are written to, beside the bundle. */
export const NOTICES_FILENAME = 'THIRD-PARTY-NOTICES'

/** The web package’s own root: the directory that holds `package.json`. */
export const WEB_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

/**
 * The packages whose MIT attribution the owner’s 2026-11-12 ruling is about.
 *
 * These three are the ones the bundler was found to strip the notices of, and
 * they are checked by name rather than by count: a file that listed two of
 * them would satisfy a count and would still ship an unattributed bundle.
 */
export const REQUIRED_MIT_PACKAGES = ['react', 'react-dom', 'scheduler']

/** A licence file’s name, as the packages that ship one spell it. */
const LICENSE_FILE_PATTERN = /^(licen[cs]e|copying|notice)(\..+)?$/i

/** A package’s own `package.json`, as far as this file reads it. */
interface PackageManifest {
  name?: string
  version?: string
  license?: string | { type?: string }
  licenses?: Array<string | { type?: string }>
  author?: string | { name?: string }
  contributors?: Array<string | { name?: string }>
  repository?: string | { url?: string }
  homepage?: string
}

/** What the notices file says about one package. */
export interface NoticeEntry {
  name: string
  version: string
  license: string
  copyright: string | null
  licenseFile: string | null
  licenseText: string | null
  source: string | null
  project: string | null
}

/**
 * The installed package that owns one module of the bundle.
 *
 * A module id is either a path (an installed file) or a virtual id naming
 * the package that provides it (`vite/modulepreload-polyfill.js`,
 * `rolldown/runtime.js`). A path under `node_modules` is owned by the package
 * directory nearest to it; a virtual id names its owner in its first
 * segment.
 *
 * **The NUL prefix.** Rollup marks a virtual module by prefixing its id with
 * a NUL byte, so that it cannot collide with a real path. The prefix is
 * stripped before the first segment is read, or the module would name
 * nothing and the bundler’s own emitted runtime would go unattributed.
 *
 * @param id The module id the bundler recorded.
 * @param root The web package’s root.
 * @returns The owning package’s directory, or null.
 */
export function packageDirForModuleId(id: string, root: string = WEB_ROOT): string | null {
  if (path.isAbsolute(id)) {
    return owningPackageDir(id)
  }
  const name = id.replace(/^\0+/, '').split('/')[0]
  if (!name) {
    return null
  }
  return findInstalledPackageDir(name, root, null)
}

/**
 * The package directory nearest to an installed file.
 *
 * The last `node_modules` segment wins, so a package that is itself nested
 * inside another package’s `node_modules` is attributed to the nested
 * package rather than to the one that depends on it.
 *
 * @param filePath The module’s path.
 * @returns The owning package’s directory, or null.
 */
export function owningPackageDir(filePath: string): string | null {
  const normalized = filePath.split(path.sep).join('/')
  const marker = '/node_modules/'
  const index = normalized.lastIndexOf(marker)
  if (index === -1) {
    return null
  }
  const name = normalized.slice(index + marker.length).split('/')[0]
  if (!name) {
    return null
  }
  const dir = path.resolve(filePath.slice(0, index + marker.length), name)
  return isPackageDir(dir) ? dir : null
}

/**
 * An installed package’s directory, found by name.
 *
 * A direct dependency is a link at the top of `node_modules`. A transitive
 * one is not: pnpm keeps it in its virtual store, where the directory is
 * named after the package and its version.
 *
 * @param name The package name.
 * @param root The web package’s root.
 * @param version The version wanted, or null for any.
 * @returns The package’s directory, or null.
 */
export function findInstalledPackageDir(
  name: string,
  root: string = WEB_ROOT,
  version: string | null = null,
): string | null {
  const direct = path.join(root, 'node_modules', name)
  if (
    isPackageDir(direct) &&
    (version === null || readPackageManifest(direct).version === version)
  ) {
    return direct
  }

  const store = path.join(root, 'node_modules', '.pnpm')
  let entries: string[]
  try {
    entries = fs.readdirSync(store)
  } catch {
    return null
  }
  const prefix = `${name.replace('/', '+')}@`
  for (const entry of entries.filter((stored) => stored.startsWith(prefix)).sort()) {
    const dir = path.join(store, entry, 'node_modules', ...name.split('/'))
    if (!isPackageDir(dir)) {
      continue
    }
    if (version !== null && readPackageManifest(dir).version !== version) {
      continue
    }
    return dir
  }
  return null
}

/**
 * Whether a directory holds a package.
 *
 * @param dir The directory to look at.
 * @returns True when it holds a `package.json` that names a package.
 */
export function isPackageDir(dir: string): boolean {
  try {
    return typeof readPackageManifest(dir).name === 'string'
  } catch {
    return false
  }
}

/**
 * A package’s own `package.json`.
 *
 * @param dir The package’s directory.
 * @returns The parsed manifest.
 */
export function readPackageManifest(dir: string): PackageManifest {
  const parsed: unknown = JSON.parse(fs.readFileSync(path.join(dir, 'package.json'), 'utf8'))
  return parsed as PackageManifest
}

/**
 * The licence identifier a package declares.
 *
 * @param pkg The package’s manifest.
 * @returns The identifier, or `UNKNOWN` when it declares none.
 */
export function licenseIdentifier(pkg: PackageManifest): string {
  const declared = pkg.license ?? (Array.isArray(pkg.licenses) ? pkg.licenses[0] : undefined)
  if (typeof declared === 'string') {
    return declared
  }
  if (declared !== undefined && typeof declared === 'object' && typeof declared.type === 'string') {
    return declared.type
  }
  return 'UNKNOWN'
}

/**
 * The licence file a package ships, if it ships one.
 *
 * @param dir The package’s directory.
 * @returns The file’s name, or null.
 */
export function findLicenseFile(dir: string): string | null {
  let entries: fs.Dirent[]
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true })
  } catch {
    return null
  }
  const names = entries
    .filter((entry) => entry.isFile() && LICENSE_FILE_PATTERN.test(entry.name))
    .map((entry) => entry.name)
  names.sort((left, right) => {
    const rank = (name: string): number => {
      const head = (name.split('.')[0] ?? name).toLowerCase()
      if (head === 'license') return 0
      if (head === 'licence') return 1
      if (head === 'copying') return 2
      return 3
    }
    return rank(left) - rank(right) || left.length - right.length || left.localeCompare(right)
  })
  return names[0] ?? null
}

/**
 * The copyright holder a licence names.
 *
 * The licence file is read first because it is the document that carries the
 * notice; the manifest’s author fields are the fallback for a package whose
 * licence file names no holder.
 *
 * @param pkg The package’s manifest.
 * @param licenseText The licence file’s text.
 * @returns The holder, or null when nothing names one.
 */
export function copyrightHolder(pkg: PackageManifest, licenseText: string | null): string | null {
  if (licenseText !== null) {
    for (const line of licenseText.split(/\r?\n/)) {
      if (/^\s*Copyright\b/i.test(line)) {
        return line.trim()
      }
    }
  }
  const author = pkg.author
  if (typeof author === 'string' && author.length > 0) {
    return author
  }
  if (author !== undefined && typeof author === 'object' && typeof author.name === 'string') {
    return author.name
  }
  const contributors = Array.isArray(pkg.contributors) ? pkg.contributors : []
  const names = contributors
    .map((contributor) =>
      typeof contributor === 'string' ? contributor : (contributor?.name ?? null),
    )
    .filter((name): name is string => typeof name === 'string' && name.length > 0)
  return names.length > 0 ? names.join(', ') : null
}

/**
 * Where a package’s published tarball is, which is where its licence text
 * is to be found.
 *
 * @param pkg The package’s manifest.
 * @returns The tarball’s URL, or null.
 */
export function registryTarballUrl(pkg: PackageManifest): string | null {
  if (typeof pkg.name !== 'string' || typeof pkg.version !== 'string') {
    return null
  }
  const unscoped = pkg.name.startsWith('@') ? (pkg.name.split('/')[1] ?? pkg.name) : pkg.name
  return `https://registry.npmjs.org/${pkg.name}/-/${unscoped}-${pkg.version}.tgz`
}

/**
 * A package’s project address, when it declares one.
 *
 * @param pkg The package’s manifest.
 * @returns The address, or null.
 */
export function projectUrl(pkg: PackageManifest): string | null {
  const repository = pkg.repository
  if (typeof repository === 'string') {
    return repository
  }
  if (
    repository !== undefined &&
    typeof repository === 'object' &&
    typeof repository.url === 'string'
  ) {
    return repository.url.replace(/^git\+/, '').replace(/\.git$/, '')
  }
  return typeof pkg.homepage === 'string' ? pkg.homepage : null
}

/**
 * Everything the notices file says about one package.
 *
 * @param dir The package’s directory.
 * @returns The entry’s fields.
 */
export function describePackage(dir: string): NoticeEntry {
  const pkg = readPackageManifest(dir)
  const licenseFile = findLicenseFile(dir)
  const licenseText =
    licenseFile === null ? null : fs.readFileSync(path.join(dir, licenseFile), 'utf8')
  return {
    name: typeof pkg.name === 'string' ? pkg.name : path.basename(dir),
    version: typeof pkg.version === 'string' ? pkg.version : 'UNKNOWN',
    license: licenseIdentifier(pkg),
    copyright: copyrightHolder(pkg, licenseText),
    licenseFile,
    licenseText,
    source: registryTarballUrl(pkg),
    project: projectUrl(pkg),
  }
}

/**
 * The packages the bundle’s module graph names.
 *
 * @param moduleIds The module ids the bundler recorded.
 * @param root The web package’s root.
 * @returns One entry per package, in name order.
 */
export function describePackages(
  moduleIds: Iterable<string>,
  root: string = WEB_ROOT,
): NoticeEntry[] {
  const found = new Map<string, NoticeEntry>()
  for (const id of moduleIds) {
    const dir = packageDirForModuleId(id, root)
    if (dir === null) {
      continue
    }
    const entry = describePackage(dir)
    found.set(`${entry.name}@${entry.version}`, entry)
  }
  return [...found.values()].sort((left, right) => left.name.localeCompare(right.name))
}

/**
 * The notices file’s text.
 *
 * @param entries The packages the bundle names.
 * @returns The file’s contents.
 */
export function renderNotices(entries: NoticeEntry[]): string {
  const lines: string[] = []
  lines.push('THIRD-PARTY NOTICES')
  lines.push('===================')
  lines.push('')
  lines.push('This file records the third-party code that is present in the JavaScript')
  lines.push('bundle shipped in this directory.')
  lines.push('')
  lines.push('The list below is generated at build time from the bundle’s own module')
  lines.push('graph: every package whose published source files the bundler placed into')
  lines.push('the bundle is named here, together with the licence those files carry, the')
  lines.push('copyright holder that licence names, and the licence text itself. It is not')
  lines.push('a list of everything the project has installed — it is the list of what is')
  lines.push('actually in the artefact you are reading.')
  lines.push('')
  lines.push('Regenerate it with `pnpm run build` in `web/`.')
  lines.push('')
  lines.push('LabCairn’s own licence is the repository’s root `LICENSE` file. This file')
  lines.push('covers third-party code only and does not restate LabCairn’s grant.')
  lines.push('')

  if (entries.length === 0) {
    lines.push('No third-party package was placed into this bundle.')
    lines.push('')
    return lines.join('\n')
  }

  for (const entry of entries) {
    lines.push('-'.repeat(80))
    lines.push(`${entry.name}@${entry.version}`)
    lines.push(field('License', entry.license))
    lines.push(field('Copyright', entry.copyright))
    lines.push(field('License file', entry.licenseFile))
    lines.push(field('Source', entry.source))
    lines.push(field('Project', entry.project))
    lines.push('')
    lines.push('  License text:')
    lines.push('')
    if (entry.licenseText === null) {
      lines.push('    (this package ships no licence file)')
    } else {
      const text = entry.licenseText.replace(/\r\n/g, '\n').replace(/\s+$/, '')
      for (const line of text.split('\n')) {
        lines.push(line.length === 0 ? '' : `    ${line}`)
      }
    }
    lines.push('')
  }
  return lines.join('\n')
}

/**
 * One labelled field, with its value in a column of its own.
 *
 * @param label The field’s name.
 * @param value The field’s value.
 * @returns The rendered field.
 */
function field(label: string, value: string | null): string {
  const text = value === null || value.length === 0 ? '(none)' : value
  return `  ${`${label}:`.padEnd(14)}${text}`
}

/**
 * The Vite plugin that writes the notices beside the bundle.
 *
 * The plugin measures the bundle the build produced and writes the file
 * into the output directory, so the notices travel with the artefact
 * wherever it is built — including into the temporary directory a test
 * builds into.
 *
 * @param options Where the web package’s root is.
 * @returns The Vite plugin.
 */
export function thirdPartyNoticesPlugin(options: { root?: string } = {}): Plugin {
  let root = options.root ?? WEB_ROOT
  let outDir = path.resolve(root, 'dist')
  const moduleIds = new Set<string>()

  return {
    name: 'labcairn-third-party-notices',
    apply: 'build',
    configResolved(config) {
      root = config.root
      outDir = path.resolve(config.root, config.build.outDir)
    },
    generateBundle(_options, bundle) {
      moduleIds.clear()
      for (const chunk of Object.values(bundle)) {
        if (chunk.type !== 'chunk') {
          continue
        }
        for (const id of Object.keys(chunk.modules)) {
          moduleIds.add(id)
        }
      }
    },
    writeBundle(options) {
      const entries = describePackages(moduleIds, root)
      fs.writeFileSync(
        path.join(options.dir ?? outDir, NOTICES_FILENAME),
        renderNotices(entries),
        'utf8',
      )
    },
  }
}

/**
 * The packages the notices file names, read back out of it.
 *
 * @param text The notices file’s contents.
 * @returns The `name@version` headings it carries.
 */
export function parseNoticeHeadings(text: string): string[] {
  const headings: string[] = []
  for (const line of text.split(/\r?\n/)) {
    const match = line.match(/^(@[^/\s@]+\/[^@\s]+|[^@\s]+)@(\S+)$/)
    if (match) {
      headings.push(`${match[1]}@${match[2]}`)
    }
  }
  return headings
}

/**
 * Check a written notices file against the installed packages.
 *
 * The file is re-derived from the installed tree and compared byte for byte,
 * so a file that names a package that is not installed, states a licence the
 * package does not declare, quotes a copyright line the package’s licence
 * file does not carry, or leaves out a package the owner’s ruling names,
 * fails here.
 *
 * @param outDir The directory the bundle was written to.
 * @param root The web package’s root.
 * @returns The problems found; empty when the file is right.
 */
export function checkNotices(outDir: string, root: string = WEB_ROOT): string[] {
  const file = path.join(outDir, NOTICES_FILENAME)
  if (!fs.existsSync(file)) {
    return [`${NOTICES_FILENAME} is missing from ${outDir}`]
  }
  const text = fs.readFileSync(file, 'utf8')
  const problems: string[] = []

  const named = parseNoticeHeadings(text).map((heading) => {
    const index = heading.lastIndexOf('@')
    return { name: heading.slice(0, index), version: heading.slice(index + 1) }
  })

  const located: Array<{ name: string; version: string; dir: string }> = []
  for (const entry of named) {
    const dir = findInstalledPackageDir(entry.name, root, entry.version)
    if (dir === null) {
      problems.push(`${entry.name}@${entry.version} is named but not installed`)
      continue
    }
    located.push({ name: entry.name, version: entry.version, dir })
  }

  for (const required of REQUIRED_MIT_PACKAGES) {
    if (!named.some((entry) => entry.name === required)) {
      problems.push(`${required} is not named in ${NOTICES_FILENAME}`)
    }
  }

  if (problems.length === 0) {
    const entries = located
      .map((item) => describePackage(item.dir))
      .sort((left, right) => left.name.localeCompare(right.name))
    if (renderNotices(entries) !== text) {
      problems.push(`${NOTICES_FILENAME} does not match the installed packages`)
    }
  }

  return problems
}

/**
 * The command line: check a written notices file against the installed tree.
 *
 * @param argv The command’s arguments.
 * @returns The process’s exit code.
 */
function main(argv: string[]): number {
  const index = argv.indexOf('--check')
  if (index === -1) {
    console.error('usage: node scripts/third-party-notices.ts --check <outDir>')
    return 2
  }
  const outDir = argv[index + 1]
  if (outDir === undefined) {
    console.error('--check needs the directory the bundle was written to')
    return 2
  }
  const problems = checkNotices(path.resolve(outDir), WEB_ROOT)
  for (const problem of problems) {
    console.error(`third-party-notices: ${problem}`)
  }
  if (problems.length > 0) {
    console.error(`third-party-notices: ${problems.length} problem(s) found`)
    return 1
  }
  console.log(`third-party-notices: ${NOTICES_FILENAME} is in order`)
  return 0
}

if (
  process.argv[1] !== undefined &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  process.exitCode = main(process.argv.slice(2))
}
