// @vitest-environment node
/**
 * The third-party attribution that travels with the built workbench.
 *
 * **The claim, stated exactly.** The bundle the installer ships carries the
 * attribution of the third-party code inside it: a `THIRD-PARTY-NOTICES` file
 * is written beside the bundle, it names every package whose published
 * source files the bundler placed into that bundle, it carries the MIT
 * attribution of React and its two siblings in full, and the installer
 * copies it to `resources/web-dist/THIRD-PARTY-NOTICES`.
 *
 * **Why the list has to be measured.** The packages that reach the bundle
 * are not the packages the project has installed — the build toolchain, the
 * type definitions and the test helpers are installed and are not shipped —
 * and they are not the packages a person would write down, because the
 * bundler also emits runtime of its own. So the expected set is read out of
 * the bundle's own module graph, the way the generator reads it, and the two
 * are compared. A hand-written list would agree with the generator only
 * until a dependency moved.
 *
 * **Why the expected set is not the generator's own answer.** This file
 * derives the package set with its own reading of the module graph rather
 * than by calling the generator, so that a generator that mis-attributes a
 * module is caught rather than confirmed. The two readings agree about which
 * directory is a package and which module id belongs to it; they do not
 * share code.
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import process from 'node:process'

import { build } from 'vite'
import { beforeAll, describe, expect, it } from 'vitest'

import { packageRoot } from './test/sourceFiles'

/** The file the attribution is written to, beside the bundle. */
const NOTICES_FILENAME = 'THIRD-PARTY-NOTICES'

/** The repository's root: one level above the web package. */
const REPO_ROOT = join(packageRoot, '..')

/** Vite's own entry point, which is what the build script runs. */
const VITE_BIN = join(packageRoot, 'node_modules', 'vite', 'bin', 'vite.js')

/** The generator's command line, which is what the build script runs. */
const NOTICES_SCRIPT = join(packageRoot, 'scripts', 'third-party-notices.ts')

/** The packages whose MIT attribution the owner's ruling is about. */
const REQUIRED_MIT_PACKAGES = ['react', 'react-dom', 'scheduler']

/**
 * The two builds the witness works with.
 *
 * `shipped` is the artefact: it is built by running Vite's command line the
 * way the package's own build script runs it — a separate process, in
 * production mode — because that is the artefact that is installed on a
 * person's machine.
 *
 * `measured` is the same build with a probe that records which modules went
 * into it. It is built in process so that the probe can see the module
 * graph; the two builds are compared, so a measurement that described some
 * other bundle would be caught.
 */
interface Builds {
  shipped: string
  measured: string
  moduleIds: string[]
}

let builds: Builds

/**
 * Build the workbench twice: once the way the build script builds it, and
 * once with a probe that records the module graph.
 */
async function buildBoth(): Promise<Builds> {
  const shipped = await mkdtemp(join(tmpdir(), 'labcairn-notices-shipped-'))
  execFileSync(process.execPath, [VITE_BIN, 'build', '--outDir', shipped], {
    cwd: packageRoot,
    env: { ...process.env, NODE_ENV: 'production' },
    stdio: 'ignore',
  })

  const measured = await mkdtemp(join(tmpdir(), 'labcairn-notices-measured-'))
  const moduleIds: string[] = []
  const previousEnv = process.env.NODE_ENV
  process.env.NODE_ENV = 'production'
  try {
    await build({
      root: packageRoot,
      configFile: join(packageRoot, 'vite.config.ts'),
      mode: 'production',
      logLevel: 'error',
      build: { outDir: measured, emptyOutDir: true },
      plugins: [
        {
          name: 'witness-probe',
          generateBundle(_options, bundle) {
            for (const chunk of Object.values(bundle)) {
              if (chunk.type !== 'chunk') {
                continue
              }
              for (const id of Object.keys(chunk.modules)) {
                moduleIds.push(id)
              }
            }
          },
        },
      ],
    })
  } finally {
    if (previousEnv === undefined) {
      delete process.env.NODE_ENV
    } else {
      process.env.NODE_ENV = previousEnv
    }
  }

  return { shipped, measured, moduleIds }
}

/**
 * The package a module id belongs to, read out of the module graph.
 *
 * A module under `node_modules` belongs to the package directory nearest to
 * it; a virtual module — one the bundler emits itself, which Rollup marks
 * with a NUL prefix so it cannot collide with a path — belongs to the
 * package its first segment names.
 *
 * @param id The module id.
 * @returns The package name, or null when the module is not a package's.
 */
function packageNameForModuleId(id: string): string | null {
  const cleaned = id.replace(/^\0+/, '')
  const marker = '/node_modules/'
  const index = cleaned.lastIndexOf(marker)
  const rest = index === -1 ? cleaned : cleaned.slice(index + marker.length)
  const parts = rest.split('/')
  if (parts[0] === undefined || parts[0].length === 0) {
    return null
  }
  return parts[0].startsWith('@') ? parts.slice(0, 2).join('/') : parts[0]
}

/**
 * The version of an installed package, wherever the package manager put it.
 *
 * @param name The package name.
 * @returns The version, or null when the package is not installed.
 */
function installedVersion(name: string): string | null {
  const direct = join(packageRoot, 'node_modules', name)
  const fromDirect = versionAt(direct)
  if (fromDirect !== null) {
    return fromDirect
  }
  const store = join(packageRoot, 'node_modules', '.pnpm')
  if (!existsSync(store)) {
    return null
  }
  const prefix = `${name.replace('/', '+')}@`
  for (const entry of readdirSync(store).sort()) {
    if (!entry.startsWith(prefix)) {
      continue
    }
    const version = versionAt(join(store, entry, 'node_modules', ...name.split('/')))
    if (version !== null) {
      return version
    }
  }
  return null
}

/**
 * The version a package directory declares.
 *
 * @param dir The package's directory.
 * @returns The version, or null.
 */
function versionAt(dir: string): string | null {
  const manifest = join(dir, 'package.json')
  if (!existsSync(manifest)) {
    return null
  }
  const parsed = JSON.parse(readFileSync(manifest, 'utf8')) as { version?: unknown }
  return typeof parsed.version === 'string' ? parsed.version : null
}

/**
 * The packages whose code is in the bundle, with their versions.
 *
 * @param moduleIds The module ids the probe recorded.
 * @returns The `name@version` of each package.
 */
function packagesInBundle(moduleIds: string[]): string[] {
  const found = new Set<string>()
  for (const id of moduleIds) {
    const name = packageNameForModuleId(id)
    if (name === null) {
      continue
    }
    const version = installedVersion(name)
    if (version === null) {
      continue
    }
    found.add(`${name}@${version}`)
  }
  return [...found].sort()
}

/**
 * The `name@version` headings a notices file carries.
 *
 * @param text The file's contents.
 * @returns The headings.
 */
function noticeHeadings(text: string): string[] {
  const headings: string[] = []
  for (const line of text.split(/\r?\n/)) {
    const match = line.match(/^(@[^/\s@]+\/[^@\s]+|[^@\s]+)@(\S+)$/)
    if (match) {
      headings.push(`${match[1]}@${match[2]}`)
    }
  }
  return headings.sort()
}

/**
 * One entry of a notices file, read back out of the file.
 *
 * @param text The file's contents.
 * @param heading The entry's heading.
 * @returns The entry's lines.
 */
function noticeBlock(text: string, heading: string): string {
  const lines = text.split(/\r?\n/)
  const start = lines.indexOf(heading)
  expect(start).toBeGreaterThanOrEqual(0)
  const rest = lines.slice(start + 1)
  const end = rest.findIndex((line) => line.startsWith('----'))
  return (end === -1 ? rest : rest.slice(0, end)).join('\n')
}

/**
 * The lines of a YAML key's block, with the indentation removed.
 *
 * @param text The file's contents.
 * @param key The key to read.
 * @returns The block's lines.
 */
function yamlBlock(text: string, key: string): string[] {
  const lines = text.split(/\r?\n/)
  const index = lines.findIndex((line) => line.startsWith(`${key}:`))
  if (index === -1) {
    return []
  }
  const indent = (lines[index] ?? '').match(/^\s*/)?.[0].length ?? 0
  const block: string[] = []
  for (const line of lines.slice(index + 1)) {
    if (line.trim().length === 0) {
      continue
    }
    if ((line.match(/^\s*/)?.[0].length ?? 0) <= indent) {
      break
    }
    block.push(line.trim())
  }
  return block
}

/**
 * Whether a packaging filter pattern covers a file name.
 *
 * The two patterns the packaging configuration uses are a double star followed
 * by a slash and a single star, and a single star; this understands those and
 * nothing else, and says so rather than pretending to be a general matcher.
 *
 * @param pattern The pattern.
 * @param name The file name, relative to the copied directory.
 * @returns Whether the pattern covers the name.
 */
function filterCovers(pattern: string, name: string): boolean {
  if (pattern === '**/*') {
    return true
  }
  if (pattern === '*') {
    return !name.includes('/')
  }
  const source = pattern
    .split('/')
    .map((segment) =>
      segment === '**'
        ? '.*'
        : segment.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '[^/]*'),
    )
    .join('/')
  return new RegExp(`^${source}$`).test(name)
}

describe('the third-party notices that travel with the bundle', () => {
  beforeAll(async () => {
    builds = await buildBoth()
  }, 180_000)

  it('are written beside the bundle the build produces', () => {
    expect(existsSync(join(builds.shipped, NOTICES_FILENAME))).toBe(true)
    expect(existsSync(join(builds.measured, NOTICES_FILENAME))).toBe(true)
  })

  it('are the same file in the build the build script runs', () => {
    const shipped = readFileSync(join(builds.shipped, NOTICES_FILENAME), 'utf8')
    const measured = readFileSync(join(builds.measured, NOTICES_FILENAME), 'utf8')
    expect(shipped).toBe(measured)
  })

  it('name exactly the packages whose code is in the bundle', () => {
    const text = readFileSync(join(builds.shipped, NOTICES_FILENAME), 'utf8')
    expect(noticeHeadings(text)).toEqual(packagesInBundle(builds.moduleIds))
  })

  it('are not empty of the packages the bundle actually carries', () => {
    // The comparison above would pass on an empty list, so the list is shown
    // to be the one the bundle's own dependencies produce.
    expect(packagesInBundle(builds.moduleIds)).toEqual(
      expect.arrayContaining(
        [...REQUIRED_MIT_PACKAGES].map((name) => {
          const version = installedVersion(name)
          expect(version).not.toBeNull()
          return `${name}@${version}`
        }),
      ),
    )
  })

  it('carry the MIT attribution of React and its two siblings in full', () => {
    const text = readFileSync(join(builds.shipped, NOTICES_FILENAME), 'utf8')
    for (const name of REQUIRED_MIT_PACKAGES) {
      const heading = noticeHeadings(text).find((entry) => entry.startsWith(`${name}@`))
      expect(heading, `${name} is not named in the notices`).toBeDefined()
      const block = noticeBlock(text, heading as string)
      expect(block).toContain('License:      MIT')
      expect(block).toMatch(/Copyright:\s+Copyright \(c\) Meta Platforms, Inc\. and affiliates\./)
      expect(block).toContain('MIT License')
      expect(block).toContain(
        'Permission is hereby granted, free of charge, to any person obtaining a copy',
      )
    }
  })

  it('pass the check the build script runs', () => {
    const output = execFileSync(process.execPath, [NOTICES_SCRIPT, '--check', builds.shipped], {
      cwd: packageRoot,
      encoding: 'utf8',
    })
    expect(output).toContain(NOTICES_FILENAME)
  })

  it('fail the check when the attribution is broken', async () => {
    // The control for the check above: a file that has lost an entry has to
    // be refused, or "the check passes" would say nothing.
    const broken = await mkdtemp(join(tmpdir(), 'labcairn-notices-broken-'))
    const text = readFileSync(join(builds.shipped, NOTICES_FILENAME), 'utf8')
    const lines = text.split(/\r?\n/)
    const start = lines.findIndex((line) => line.startsWith('react-dom@'))
    expect(start).toBeGreaterThanOrEqual(0)
    const rest = lines.slice(start + 1)
    const end = rest.findIndex((line) => line.startsWith('----'))
    const kept = [...lines.slice(0, start), ...(end === -1 ? [] : rest.slice(end))]
    writeFileSync(join(broken, NOTICES_FILENAME), kept.join('\n'), 'utf8')

    let failed = false
    try {
      execFileSync(process.execPath, [NOTICES_SCRIPT, '--check', broken], {
        cwd: packageRoot,
        stdio: 'ignore',
      })
    } catch {
      failed = true
    }
    expect(failed).toBe(true)
  }, 180_000)

  it('are copied into the installer beside the bundle', () => {
    const config = readFileSync(join(REPO_ROOT, 'shell', 'electron-builder.yml'), 'utf8')
    const block = yamlBlock(config, 'extraResources')
    expect(block).toContain('- from: ../web/dist')
    expect(block).toContain('to: web-dist')

    const filters = block
      .filter((line) => line.startsWith('- ') && line !== '- from: ../web/dist')
      .map((line) => line.replace(/^-\s*/, '').replace(/^['"]|['"]$/g, ''))
    expect(filters.length).toBeGreaterThan(0)
    expect(filters.some((pattern) => filterCovers(pattern, NOTICES_FILENAME))).toBe(true)
  })
})
