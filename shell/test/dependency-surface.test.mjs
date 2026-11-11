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
 *    exactly the set measured when this witness was written: the thirteen
 *    packages the owner's 2026-11-10 approval covered, the electron-builder
 *    devDependency the owner authorised on 2026-11-11, and the transitive
 *    closure that installation pinned. A package outside this set — or a
 *    version change — makes this witness red, and that is §0 rule 4
 *    working: adopting a dependency is the owner's decision, and the witness
 *    is what notices an adoption nobody recorded.
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

/** The dependency set measured from shell/pnpm-lock.yaml at this commit. */
const APPROVED_PACKAGES = new Set([
  '@electron-internal/extract-zip@1.0.8',
  '@electron/asar@3.4.1',
  '@electron/fuses@1.8.0',
  '@electron/get@3.1.0',
  '@electron/get@5.1.0',
  '@electron/notarize@2.5.0',
  '@electron/osx-sign@1.3.3',
  '@electron/rebuild@4.2.1',
  '@electron/universal@2.0.3',
  '@electron/windows-sign@1.2.2',
  '@isaacs/fs-minipass@4.0.1',
  '@isaacs/nonrecursive-glob-match@1.1.0',
  '@malept/cross-spawn-promise@2.0.0',
  '@malept/flatpak-bundler@0.4.0',
  '@noble/hashes@1.8.0',
  '@peculiar/asn1-schema@2.11.1',
  '@peculiar/json-schema@1.1.12',
  '@peculiar/utils@2.0.3',
  '@peculiar/webcrypto@1.7.2',
  '@sindresorhus/is@4.6.0',
  '@szmarczak/http-timer@4.0.6',
  '@types/cacheable-request@6.0.3',
  '@types/debug@4.1.13',
  '@types/fs-extra@9.0.13',
  '@types/http-cache-semantics@4.2.0',
  '@types/keyv@3.1.4',
  '@types/ms@2.1.0',
  '@types/node@24.19.2',
  '@types/responselike@1.0.3',
  '@xmldom/xmldom@0.8.15',
  'abbrev@4.0.0',
  'agent-base@7.1.4',
  'ajv@8.20.0',
  'ansi-regex@5.0.1',
  'ansi-styles@4.3.0',
  'app-builder-lib@26.18.0',
  'app-builder-lib@26.18.0(dmg-builder@26.18.0)(electron-builder-squirrel-windows@26.18.0)',
  'argparse@2.0.1',
  'asn1js@3.1.0',
  'async-exit-hook@2.0.1',
  'async@3.2.6',
  'asynckit@0.4.0',
  'at-least-node@1.0.0',
  'aws4@1.13.2',
  'balanced-match@1.0.2',
  'balanced-match@4.0.4',
  'base64-js@1.5.1',
  'bluebird@3.7.2',
  'boolean@3.2.0',
  'brace-expansion@1.1.21',
  'brace-expansion@2.1.7',
  'brace-expansion@5.0.12',
  'buffer-from@1.1.2',
  'builder-util-runtime@9.7.0',
  'builder-util@26.16.0',
  'bytestreamjs@2.0.1',
  'cacheable-lookup@5.0.4',
  'cacheable-request@7.0.4',
  'call-bind-apply-helpers@1.0.2',
  'chalk@4.1.2',
  'chownr@3.0.0',
  'chromium-pickle-js@0.2.0',
  'ci-info@4.3.1',
  'ci-info@4.5.0',
  'cliui@8.0.1',
  'clone-response@1.0.3',
  'color-convert@2.0.1',
  'color-name@1.1.4',
  'combined-stream@1.0.8',
  'commander@5.1.0',
  'commander@9.5.0',
  'compare-version@0.1.2',
  'concat-map@0.0.1',
  'core-util-is@1.0.3',
  'cross-dirname@0.1.0',
  'cross-spawn@7.0.6',
  'debug@4.4.3',
  'decompress-response@6.0.0',
  'defer-to-connect@2.0.1',
  'define-data-property@1.1.4',
  'define-properties@1.2.1',
  'delayed-stream@1.0.0',
  'detect-node@2.1.0',
  'dir-compare@4.2.0',
  'dmg-builder@26.18.0',
  'dmg-builder@26.18.0(electron-builder-squirrel-windows@26.18.0)',
  'dotenv-expand@11.0.7',
  'dotenv@16.6.1',
  'dunder-proto@1.0.1',
  'duplexer2@0.1.4',
  'ejs@3.1.10',
  'electron-builder-squirrel-windows@26.18.0',
  'electron-builder-squirrel-windows@26.18.0(dmg-builder@26.18.0)',
  'electron-builder@26.18.0',
  'electron-builder@26.18.0(electron-builder-squirrel-windows@26.18.0)',
  'electron-publish@26.18.0',
  'electron-winstaller@5.4.0',
  'electron@45.2.3',
  'emoji-regex@8.0.0',
  'end-of-stream@1.4.5',
  'env-paths@2.2.1',
  'env-paths@3.0.0',
  'err-code@2.0.3',
  'es-define-property@1.0.1',
  'es-errors@1.3.0',
  'es-object-atoms@1.1.2',
  'es-set-tostringtag@2.1.0',
  'es6-error@4.1.1',
  'escalade@3.2.0',
  'escape-string-regexp@4.0.0',
  'exponential-backoff@3.1.3',
  'fast-deep-equal@3.1.3',
  'fast-uri@3.1.9',
  'fdir@6.5.0',
  'fdir@6.5.0(picomatch@4.0.7)',
  'filelist@1.0.6',
  'form-data@4.0.6',
  'fs-extra@10.1.0',
  'fs-extra@11.3.1',
  'fs-extra@11.4.1',
  'fs-extra@7.0.1',
  'fs-extra@8.1.0',
  'fs-extra@9.1.0',
  'fs.realpath@1.0.0',
  'function-bind@1.1.2',
  'get-caller-file@2.0.5',
  'get-intrinsic@1.3.0',
  'get-proto@1.0.1',
  'get-stream@5.2.0',
  'glob@7.2.3',
  'global-agent@3.0.0',
  'globalthis@1.0.4',
  'gopd@1.2.0',
  'got@11.8.6',
  'graceful-fs@4.2.11',
  'has-flag@4.0.0',
  'has-property-descriptors@1.0.2',
  'has-symbols@1.1.0',
  'has-tostringtag@1.0.2',
  'hasown@2.0.4',
  'hosted-git-info@4.1.0',
  'http-cache-semantics@4.3.0',
  'http-proxy-agent@7.0.2',
  'http2-wrapper@1.0.3',
  'https-proxy-agent@7.0.6',
  'inflight@1.0.6',
  'inherits@2.0.4',
  'is-fullwidth-code-point@3.0.0',
  'isarray@1.0.0',
  'isbinaryfile@4.0.10',
  'isbinaryfile@5.0.7',
  'isexe@2.0.0',
  'isexe@3.1.5',
  'isexe@4.0.0',
  'jake@10.9.4',
  'jiti@2.7.0',
  'js-yaml@4.3.2',
  'json-buffer@3.0.1',
  'json-schema-traverse@1.0.0',
  'json-stringify-safe@5.0.1',
  'json5@2.2.3',
  'jsonfile@4.0.0',
  'jsonfile@6.2.1',
  'keyv@4.5.4',
  'lazy-val@1.0.5',
  'lodash@4.18.1',
  'lowercase-keys@2.0.0',
  'lru-cache@6.0.0',
  'matcher@3.0.0',
  'math-intrinsics@1.1.0',
  'mime-db@1.52.0',
  'mime-types@2.1.35',
  'mime@2.6.0',
  'mimic-response@1.0.1',
  'mimic-response@3.1.0',
  'minimatch@11.0.7',
  'minimatch@3.1.5',
  'minimatch@5.1.9',
  'minimist@1.2.8',
  'minipass@7.1.3',
  'minizlib@3.1.0',
  'mkdirp@0.5.6',
  'ms@2.1.3',
  'node-abi@4.40.0',
  'node-api-version@0.2.1',
  'node-gyp@12.4.0',
  'node-int64@0.4.0',
  'nopt@9.0.0',
  'normalize-url@6.1.0',
  'object-keys@1.1.1',
  'once@1.4.0',
  'p-cancelable@2.1.1',
  'p-limit@3.1.0',
  'path-is-absolute@1.0.1',
  'path-key@3.1.1',
  'pe-library@0.4.1',
  'picocolors@1.1.1',
  'picomatch@4.0.7',
  'pkijs@3.4.3',
  'plist@3.1.0',
  'postject@1.0.0-alpha.6',
  'proc-log@6.1.0',
  'process-nextick-args@2.0.1',
  'progress@2.0.3',
  'promise-retry@2.0.1',
  'proper-lockfile@4.1.2',
  'pump@3.0.4',
  'pvtsutils@1.3.6',
  'pvutils@1.2.0',
  'quick-lru@5.1.1',
  'read-binary-file-arch@1.0.6',
  'readable-stream@2.3.8',
  'require-directory@2.1.1',
  'require-from-string@2.0.2',
  'resedit@1.7.2',
  'resolve-alpn@1.2.1',
  'responselike@2.0.1',
  'retry@0.12.0',
  'rimraf@2.6.3',
  'roarr@2.15.4',
  'safe-buffer@5.1.2',
  'sanitize-filename@1.6.5',
  'sax@1.6.1',
  'semver-compare@1.0.0',
  'semver@5.7.3',
  'semver@6.3.2',
  'semver@7.7.4',
  'semver@7.8.6',
  'serialize-error@7.0.1',
  'shebang-command@2.0.0',
  'shebang-regex@3.0.0',
  'signal-exit@3.0.7',
  'simple-update-notifier@2.0.0',
  'source-map-support@0.5.21',
  'source-map@0.6.1',
  'sprintf-js@1.1.3',
  'stat-mode@1.0.0',
  'string-width@4.2.3',
  'string_decoder@1.1.1',
  'strip-ansi@6.0.1',
  'sumchecker@3.0.1',
  'supports-color@7.2.0',
  'tar@7.5.22',
  'temp-file@3.4.0',
  'temp@0.9.4',
  'tiny-async-pool@1.3.0',
  'tinyglobby@0.2.17',
  'tmp-promise@3.0.3',
  'tmp@0.2.7',
  'truncate-utf8-bytes@1.0.2',
  'tslib@2.9.1',
  'type-fest@0.13.1',
  'undici-types@7.24.6',
  'undici@6.29.1',
  'undici@7.30.2',
  'universalify@0.1.2',
  'universalify@2.0.1',
  'unzipper@0.12.5',
  'utf8-byte-length@1.0.5',
  'util-deprecate@1.0.2',
  'webcrypto-core@1.9.2',
  'which@2.0.2',
  'which@5.0.0',
  'which@6.0.1',
  'wrap-ansi@7.0.0',
  'wrappy@1.0.2',
  'xmlbuilder@15.1.1',
  'y18n@5.0.8',
  'yallist@4.0.0',
  'yallist@5.0.0',
  'yargs-parser@21.1.1',
  'yargs@17.7.3',
  'yocto-queue@0.1.0',
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
