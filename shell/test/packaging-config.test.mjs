/**
 * T08's packaging configuration: the minimal unsigned Windows installer.
 *
 * This witness reads the configuration bytes and the manifest rather than
 * trusting a build that may not be available on every machine. Signing stays
 * behind W28, so adding an explicit signing setting is a red result here, not
 * a silent change to the first artifact.
 */

import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SHELL_ROOT = path.resolve(HERE, '..')
const CONFIG_PATH = path.join(SHELL_ROOT, 'electron-builder.yml')
const MANIFEST_PATH = path.join(SHELL_ROOT, 'package.json')
const LOCK_PATH = path.join(SHELL_ROOT, 'pnpm-lock.yaml')
const GUARD_PATH = path.join(SHELL_ROOT, 'scripts', 'require-web-dist.mjs')

const config = fs.readFileSync(CONFIG_PATH, 'utf8')
const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'))
const lockText = fs.readFileSync(LOCK_PATH, 'utf8')

/** Read one top-level scalar from the deliberately small YAML config. */
function scalar(name) {
  const match = config.match(new RegExp(`^${name}:\\s*(.+)$`, 'm'))
  assert.ok(match, `${name} is missing from electron-builder.yml`)
  return match[1].trim().split(/\s+#/)[0].trim()
}

/** Read a YAML list by key, including nested lists such as `win.target`. */
function list(name, text = config) {
  const lines = text.split(/\r?\n/)
  const key = new RegExp(`^\\s*${name}:\\s*$`)
  const index = lines.findIndex((line) => key.test(line))
  assert.ok(index >= 0, `${name} is missing from electron-builder.yml`)
  const keyIndent = lines[index].match(/^\s*/)[0].length
  const found = []
  for (const line of lines.slice(index + 1)) {
    const item = line.match(/^(\s*)- (.+)$/)
    if (!item || item[1].length <= keyIndent) break
    found.push(item[2].trim())
  }
  assert.ok(found.length > 0, `${name} is present but carries no items`)
  return found
}

/** The output directory is supplied by the caller and keeps products outside the tree. */
function outputOutsideTrackedTree(text) {
  return /^directories:\n  output: \$\{env\.LABCAIRN_SHELL_DIST_DIR\}$/m.test(text)
}

/** Signing keys that W28 owns; a comment about their absence is not a setting. */
function signingSettingsIn(text) {
  return [...text.matchAll(/^\s*(sign|signing|certificateFile|certificatePassword|signtoolOptions)\b/gm)].map((match) => match[1])
}

test('the packaging config names the product, output and unsigned NSIS target', () => {
  assert.equal(scalar('appId'), 'org.labcairn.shell')
  assert.equal(scalar('productName'), 'LabCairn')
  assert.ok(outputOutsideTrackedTree(config))
  assert.match(config, /^extraMetadata:\n  dependencies: null$/m)
  assert.deepEqual(list('target'), ['nsis'])
  assert.match(config, /^nsis:\n  oneClick: false\n  allowToChangeInstallationDirectory: true\n  perMachine: false$/m)
  assert.deepEqual(signingSettingsIn(config), [])
})

test('the packaging config ships the main process, preload, manifest and web dist', () => {
  assert.deepEqual(list('files'), ['src/**/*', 'package.json'])
  for (const file of ['src/main.mjs', 'src/preload.cjs', 'package.json']) {
    assert.ok(fs.existsSync(path.join(SHELL_ROOT, file)), `${file} is declared but absent for packaging`)
  }
  assert.match(config, /^extraResources:\n  - from: \.\.\/web\/dist\n    to: web-dist\n    filter:\n      - '\*\*\/\*'$/m)
  assert.ok(!/service-runtime|to: service/.test(config), 'the minimal configuration does not claim an unmeasured O3 runtime arrangement')
})

test('the manifest declares the Windows build script and the approved tool', () => {
  assert.equal(manifest.scripts.dist, 'electron-builder --win')
  assert.equal(manifest.devDependencies['electron-builder'], '26.18.0')
  assert.equal(manifest.pnpm?.overrides?.['minimatch@>=7 <11'], '11.0.7')
  assert.match(lockText, /^  electron-builder@26\.18\.0:/m)
  assert.equal(manifest.dependencies.electron, '45.2.3')
})

test('mutations of signing, target and output are visible to the same reads', () => {
  const signed = config.replace(/^  perMachine: false$/m, '  perMachine: false\n  certificateFile: example.pfx')
  assert.notEqual(signed, config, 'the signing mutation did not change the configuration')
  assert.deepEqual(signingSettingsIn(signed), ['certificateFile'])

  const portableOnly = config.replace('- nsis', '- portable')
  assert.notEqual(portableOnly, config, 'the target mutation did not change the configuration')
  assert.deepEqual(list('target', portableOnly), ['portable'])

  const movedOutput = config.replace('${env.LABCAIRN_SHELL_DIST_DIR}', 'dist')
  assert.notEqual(movedOutput, config, 'the output mutation did not change the configuration')
  assert.equal(outputOutsideTrackedTree(movedOutput), false)
})

/** Run the packaging guard against a bundle directory and return its result. */
function guardAgainst(directory) {
  return spawnSync(process.execPath, [GUARD_PATH, directory], { encoding: 'utf8' })
}

/** A temporary directory outside the tree, removed when the work is done. */
function temporaryDirectory(prefix) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix))
}

test('the packaging config runs the bundle guard before it packages', () => {
  assert.match(config, /^beforeBuild: scripts\/require-web-dist\.mjs$/m)
  assert.ok(fs.existsSync(GUARD_PATH), 'the configuration names a guard script that is absent')
})

test('the bundle guard refuses a build with no web bundle', () => {
  const absent = temporaryDirectory('labcairn-web-dist-absent-')
  fs.rmSync(absent, { recursive: true, force: true })
  const result = guardAgainst(absent)
  assert.notEqual(result.status, 0, 'the guard accepted a bundle that does not exist')
  assert.match(result.stderr, /absent/)
})

test('the bundle guard refuses an empty bundle and accepts one with the entry document', () => {
  const empty = temporaryDirectory('labcairn-web-dist-empty-')
  try {
    const result = guardAgainst(empty)
    assert.notEqual(result.status, 0, 'the guard accepted a bundle with no index.html')
    assert.match(result.stderr, /index\.html/)
  } finally {
    fs.rmSync(empty, { recursive: true, force: true })
  }

  const complete = temporaryDirectory('labcairn-web-dist-complete-')
  try {
    fs.writeFileSync(path.join(complete, 'index.html'), '<!doctype html><title>LabCairn</title>')
    const result = guardAgainst(complete)
    assert.equal(result.status, 0, `the guard refused a complete bundle: ${result.stderr}`)
  } finally {
    fs.rmSync(complete, { recursive: true, force: true })
  }
})
