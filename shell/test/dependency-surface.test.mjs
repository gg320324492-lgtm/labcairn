/**
 * AC-7's shell half: what the shell's own code and its dependency set name.
 *
 * **The claim, stated exactly.** Two different surfaces, witnessed separately,
 * because the honest claim is not one sentence:
 *
 * 1. **The runtime surface.** `shell/src/` is what the shipped main process
 *    and preload load. Every absolute URL in it names a loopback host; every
 *    request the shell's own code makes is relative to a page origin it read
 *    from `ServiceStarting`. This is the half `web/src/api/bundle.test.ts`
 *    watches for the built workbench, watched here at the bytes the shell
 *    actually runs.
 * 2. **The installed dependency set.** `shell/pnpm-lock.yaml`'s packages are
 *    exactly the thirteen the owner's approval (2026-11-10) was measured over.
 *    A fourteenth package — or a version change — makes this witness red, and
 *    that is §0 rule 4 working: adopting a dependency is the owner's decision,
 *    and the witness is what notices an adoption nobody recorded.
 *
 * **What this file deliberately does not claim.** `@electron/get` names
 * `github.com`: Electron's *install-time* binary download, measured in the
 * selection record (31 s, "Downloading Electron binary…") and part of what the
 * owner approved ("a build job must be able to reach that channel" — plan
 * §4.4). A witness that scanned third-party installers and called them the
 * shell's remote surface would be measuring the wrong thing; a witness that
 * pretended they do not exist would be a green that hides the channel. The
 * runtime scan is scoped to `src/` for that reason, and the distinction is
 * recorded rather than inferred.
 *
 * **The positive control.** A remote host introduced into `src/` (a copy, run
 * through the same scan function) makes the scan red — the plan's AC-7
 * "a positive control (an introduced remote host) makes it red".
 */

import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SHELL_ROOT = path.resolve(HERE, '..')
const SRC = path.join(SHELL_ROOT, 'src')

/** The only hosts `src/` may name. Loopback, and nothing else. */
const RUNTIME_HOST_ALLOW_LIST = new Set(['127.0.0.1', 'localhost'])

/** The dependency set the owner's 2026-11-10 approval was measured over. */
const APPROVED_PACKAGES = new Set([
  '@electron-internal/extract-zip@1.0.8',
  '@electron/get@5.1.0',
  '@types/node@24.19.2',
  'debug@4.4.3',
  'electron@45.2.3',
  'env-paths@3.0.0',
  'graceful-fs@4.2.11',
  'ms@2.1.3',
  'progress@2.0.3',
  'semver@7.8.6',
  'sumchecker@3.0.1',
  'undici-types@7.24.6',
  'undici@7.30.2',
])

const ABSOLUTE_URL = /\bhttps?:\/\/([A-Za-z0-9.-]+)/g

function sourceFiles(dir) {
  const found = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const where = path.join(dir, entry.name)
    if (entry.isDirectory()) found.push(...sourceFiles(where))
    else if (/\.(mjs|cjs|js)$/.test(entry.name)) found.push(where)
  }
  return found
}

/**
 * The remote hosts a bundle of source names.
 *
 * The positive control below feeds mutated text through *this* function, so
 * the control measures the scan the real assertion runs rather than a copy
 * of it.
 */
function remoteHostsIn(text) {
  const hosts = new Set()
  for (const match of text.matchAll(ABSOLUTE_URL)) hosts.add(match[1])
  return hosts
}

test("the shell's own runtime code names no host but loopback", () => {
  const files = sourceFiles(SRC)
  assert.ok(files.length >= 6, `only ${files.length} source file(s) found under src/ — the scan is not looking at what it claims`)
  for (const file of files) {
    const hosts = remoteHostsIn(fs.readFileSync(file, 'utf8'))
    for (const host of hosts) {
      assert.ok(
        RUNTIME_HOST_ALLOW_LIST.has(host),
        `${path.relative(SHELL_ROOT, file)} names ${host}; the shell's runtime surface is loopback-only`,
      )
    }
  }
})

test('the installed dependency set is exactly the approved one', () => {
  const lockText = fs.readFileSync(path.join(SHELL_ROOT, 'pnpm-lock.yaml'), 'utf8')
  const packagesSection = lockText.slice(lockText.indexOf('\npackages:\n'))
  const found = new Set()
  for (const match of packagesSection.matchAll(/^  '?([^'\n]+?)@([^':\n]+)'?:$/gm)) {
    found.add(`${match[1]}@${match[2]}`)
  }
  assert.ok(found.size >= APPROVED_PACKAGES.size, `the lockfile lists ${found.size} package(s); the scan shape has changed`)
  const unapproved = [...found].filter((name) => !APPROVED_PACKAGES.has(name))
  assert.deepEqual(unapproved, [], `the lockfile carries package(s) outside the approved set: ${unapproved.join(', ')}`)
  const missing = [...APPROVED_PACKAGES].filter((name) => !found.has(name))
  assert.deepEqual(missing, [], `the approved package(s) left the lockfile: ${missing.join(', ')} — re-measure, do not edit this list from memory`)

  const manifest = JSON.parse(fs.readFileSync(path.join(SHELL_ROOT, 'package.json'), 'utf8'))
  assert.deepEqual(manifest.dependencies, { electron: '45.2.3' }, 'the manifest declares something other than the approved dependency')
})

test('a remote host introduced into src/ reddens the scan (AC-7 positive control)', () => {
  const mutated = `${fs.readFileSync(path.join(SRC, 'live-guard.mjs'), 'utf8')}
export const INJECTED = fetch('https://report.example.invalid/telemetry')
`
  const hosts = remoteHostsIn(mutated)
  assert.ok(hosts.has('report.example.invalid'), 'the scan did not see an introduced remote host — it is not watching what it claims to watch')
  for (const host of hosts) {
    if (!RUNTIME_HOST_ALLOW_LIST.has(host)) continue
  }
  // Re-run the production allow-list decision on the mutated text, not a
  // hand-written comparison: the control must fail the same assertion real
  // code would fail.
  const violations = [...hosts].filter((host) => !RUNTIME_HOST_ALLOW_LIST.has(host))
  assert.deepEqual(violations, ['report.example.invalid'])
})
