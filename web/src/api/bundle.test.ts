// @vitest-environment node
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, relative } from 'node:path'
import process from 'node:process'

import { describe, expect, it } from 'vitest'

import { filesUnder, packageRoot, shippedSourceFiles } from '../test/sourceFiles'

/**
 * The workbench talks to the local API and to nothing else.
 *
 * **Why the built bundle and not the source.** The source can be read; the
 * bundle is what the browser runs. A dependency that carried a remote host
 * would put one in the bundle without putting one in a line of ours, so the
 * check is on the bytes that ship.
 *
 * **Why the build is run here rather than read from `dist/`.** A `dist/`
 * left over from before a change would turn a real regression green, and no
 * `dist/` at all would turn the assertion into a no-op. So the bundle is
 * built fresh, into a temporary directory outside the repository, and the
 * bytes that are checked are the bytes that were just produced.
 */

/**
 * The hosts the built bundle may name.
 *
 * Two, and neither is a place the workbench reaches for.
 *
 * `www.w3.org` — XML namespace identifiers. `http://www.w3.org/2000/svg` is
 * the *name* of the SVG namespace: a browser matches it to decide what an
 * element is, and never resolves it as an address. React's renderer carries
 * them.
 *
 * `react.dev` — the address React puts into its minified error messages, so
 * that a production error says where to look it up. It is a string in an
 * error path; the workbench never fetches it, and the client refuses a path
 * that names a host at all.
 *
 * The list is a list, not a wildcard: a host that is not on it fails the
 * build.
 */
const ALLOWED_HOSTS = new Set(['www.w3.org', 'react.dev'])

/** An absolute URL, and the host it names. */
const ABSOLUTE_URL = /\bhttps?:\/\/([A-Za-z0-9.-]+)/g

/** The hosts a piece of text names. */
function hostsIn(text: string): Set<string> {
  const hosts = new Set<string>()
  for (const match of text.matchAll(ABSOLUTE_URL)) {
    hosts.add((match[1] ?? '').toLowerCase())
  }
  return hosts
}

describe('the host scanner', () => {
  it('finds a remote host when there is one', () => {
    expect([...hostsIn('fetch("https://collect.example/ping")')]).toEqual(['collect.example'])
  })

  it('finds a host in a plain http URL too', () => {
    expect([...hostsIn('const u = "http://collect.example/ping"')]).toEqual(['collect.example'])
  })

  it('finds nothing in text that names no host', () => {
    expect([...hostsIn('const path = "/artifacts/1/content"')]).toEqual([])
  })
})

describe('the application source', () => {
  it('names no remote host', () => {
    const offenders: string[] = []
    for (const path of shippedSourceFiles()) {
      for (const host of hostsIn(readFileSync(path, 'utf-8'))) {
        offenders.push(`${relative(packageRoot, path)}: ${host}`)
      }
    }

    expect(offenders).toEqual([])
  })

  it('is not empty, so the scan above is not vacuous', () => {
    expect(shippedSourceFiles().length).toBeGreaterThan(5)
  })
})

describe('the built bundle', () => {
  it('names no remote host', async () => {
    const outDir = await mkdtemp(join(tmpdir(), 'labcairn-bundle-'))

    // The build is run the way the package's own build script runs it — a
    // separate process, in production mode — because that is the artefact
    // that ships. Building it in-process would inherit this test run's
    // `NODE_ENV`, and a development bundle carries React's development
    // error messages, which name a great many more documentation addresses
    // than the production bundle does.
    execFileSync(
      process.execPath,
      [join(packageRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '--outDir', outDir],
      {
        cwd: packageRoot,
        env: { ...process.env, NODE_ENV: 'production' },
        stdio: 'ignore',
      },
    )

    const built = filesUnder(outDir).filter((path) => /\.(js|css|html)$/.test(path))
    expect(built.length).toBeGreaterThan(0)

    const offenders: string[] = []
    const named = new Set<string>()
    for (const path of built) {
      for (const host of hostsIn(readFileSync(path, 'utf-8'))) {
        named.add(host)
        if (!ALLOWED_HOSTS.has(host)) {
          offenders.push(`${relative(outDir, path)}: ${host}`)
        }
      }
    }

    // The scan must have seen something, or "no offenders" would be a
    // statement about an empty scan rather than about the bundle.
    expect(named.size).toBeGreaterThan(0)
    expect(offenders).toEqual([])
  }, 180_000)
})
