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
const GUARD_PATH = path.join(SHELL_ROOT, 'scripts', 'require-package-inputs.mjs')
const FREEZE_DIR = path.join(SHELL_ROOT, 'build', 'backend-freeze', 'labcairn')
const LICENCES_PATH = path.join(SHELL_ROOT, 'licenses')
const NSIS_INCLUDE_PATH = path.join(SHELL_ROOT, 'nsis', 'licenses.nsh')

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

/**
 * The extraResources entries as (from, to) pairs, read from the YAML text.
 * A dedicated reader rather than `list()`: the entries carry prose comments
 * and nested `filter` lists, and the property under test is which sources
 * the package carries and where they land.
 */
function extraResourcePairs(text) {
  const lines = text.split(/\r?\n/)
  const start = lines.findIndex((line) => /^extraResources:\s*$/.test(line))
  assert.ok(start >= 0, 'extraResources is missing from electron-builder.yml')
  const pairs = []
  let current = null
  for (const line of lines.slice(start + 1)) {
    if (/^\S/.test(line)) break
    const from = line.match(/^\s+- from: (.+)$/)
    if (from) {
      current = { from: from[1].trim() }
      pairs.push(current)
      continue
    }
    const to = line.match(/^\s+to: (.+)$/)
    if (to && current) {
      current.to = to[1].trim()
      current = null
    }
  }
  return pairs
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
  // The extraResources list is read structurally (not by one anchored regex)
  // because its entries carry prose comments: the web bundle, the frozen
  // backend (O3, wired 2026-11-14) and the two supply templates.
  assert.deepEqual(extraResourcePairs(config), [
    { from: '../web/dist', to: 'web-dist' },
    { from: 'build/backend-freeze/labcairn', to: 'backend/labcairn' },
    { from: 'shell-env.template.json', to: 'shell-env.template.json' },
    { from: 'labcairn-shell.cmd', to: 'labcairn-shell.cmd' },
  ])
  assert.ok(fs.existsSync(FREEZE_DIR) || !process.env.CI, 'the frozen backend the config ships is absent — run shell/scripts/build-backend-freeze.mjs first')
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

/** Run the packaging guard against a bundle directory and a backend directory. */
function guardAgainst(directory, backend = syntheticFreeze()) {
  return spawnSync(process.execPath, [GUARD_PATH, directory, backend], { encoding: 'utf8' })
}

/** A temporary directory outside the tree, removed when the work is done. */
function temporaryDirectory(prefix) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix))
}

/**
 * A synthetic frozen-backend tree with the minimum the guard inspects.
 *
 * The real freeze output (`shell/build/backend-freeze/labcairn/`) exists only
 * where the freeze script has run, and it is a build product: a runner has
 * neither. The guard's contract is about the *shape* — the entry binary per
 * platform and `migrations/alembic.ini` — so the witnesses assert that shape
 * against a synthetic tree and leave the real artifact out of the loop.
 */
function syntheticFreeze() {
  const directory = temporaryDirectory('labcairn-freeze-synthetic-')
  fs.mkdirSync(path.join(directory, 'migrations'), { recursive: true })
  fs.writeFileSync(path.join(directory, process.platform === 'win32' ? 'labcairn.exe' : 'labcairn'), '')
  fs.writeFileSync(path.join(directory, 'migrations', 'alembic.ini'), '[alembic]\n')
  return directory
}

test('the packaging config runs the input guard before it packages', () => {
  assert.match(config, /^beforeBuild: scripts\/require-package-inputs\.mjs$/m)
  assert.ok(fs.existsSync(GUARD_PATH), 'the configuration names a guard script that is absent')
})

test('the guard is shaped the way electron-builder calls it', async () => {
  const guard = await import('../scripts/require-package-inputs.mjs')
  assert.equal(typeof guard.default, 'function', 'electron-builder resolves the hook as the default export')
  assert.equal(typeof guard.bundleProblem, 'function')
  assert.equal(typeof guard.backendProblem, 'function')
  assert.equal(typeof guard.makeGuard, 'function')
  assert.ok(fs.existsSync(GUARD_PATH), 'the guard script is absent')
})

test('the hook electron-builder calls throws on a missing bundle and returns true on a good one', async () => {
  const guard = await import('../scripts/require-package-inputs.mjs')
  const absent = temporaryDirectory('labcairn-hook-absent-')
  fs.rmSync(absent, { recursive: true, force: true })
  const freeze = syntheticFreeze()
  await assert.rejects(() => guard.makeGuard(absent, freeze)(), /absent/)

  const complete = temporaryDirectory('labcairn-hook-complete-')
  try {
    fs.writeFileSync(path.join(complete, 'index.html'), '<!doctype html><title>LabCairn</title>')
    const result = await guard.makeGuard(complete, freeze)()
    assert.equal(result, true, 'the hook must return true so electron-builder still rebuilds the dependencies')
  } finally {
    fs.rmSync(complete, { recursive: true, force: true })
    fs.rmSync(freeze, { recursive: true, force: true })
  }
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

test('the packaging guard refuses a build with no frozen backend and names the freeze script', () => {
  // O3's frozen service (2026-11-14) is the second input a package needs: the
  // package's own shell-env.json names `backend/labcairn`, and electron-builder
  // would silently ship a package without it. The refusal names the tool that
  // produces the missing directory. A synthetic web bundle keeps the web input
  // out of the assertion; the backend input is the one under test.
  const webBundle = temporaryDirectory('labcairn-web-dist-guard-')
  const absent = temporaryDirectory('labcairn-freeze-absent-')
  fs.rmSync(absent, { recursive: true, force: true })
  try {
    fs.writeFileSync(path.join(webBundle, 'index.html'), '<!doctype html>')
    const result = guardAgainst(webBundle, absent)
    assert.notEqual(result.status, 0, 'the guard accepted a build with no frozen backend')
    assert.match(result.stderr, /frozen backend directory is absent/)
    assert.match(result.stderr, /build-backend-freeze\.mjs/)
  } finally {
    fs.rmSync(webBundle, { recursive: true, force: true })
  }
})

test('the packaging guard refuses a frozen backend without its entry binary or migrations', () => {
  const webBundle = temporaryDirectory('labcairn-web-dist-guard2-')
  const hollow = temporaryDirectory('labcairn-freeze-hollow-')
  try {
    fs.writeFileSync(path.join(webBundle, 'index.html'), '<!doctype html>')
    fs.mkdirSync(path.join(hollow, 'migrations'), { recursive: true })
    fs.writeFileSync(path.join(hollow, 'migrations', 'alembic.ini'), '[alembic]\n')
    const noExe = guardAgainst(webBundle, hollow)
    assert.notEqual(noExe.status, 0, 'the guard accepted a backend with no entry binary')
    assert.match(noExe.stderr, /labcairn\.exe/)

    fs.mkdirSync(path.join(hollow, 'labcairn.exe'), { recursive: true })
    fs.rmSync(path.join(hollow, 'migrations'), { recursive: true, force: true })
    const noMigrations = guardAgainst(webBundle, hollow)
    assert.notEqual(noMigrations.status, 0, 'the guard accepted a backend with no migrations')
    assert.match(noMigrations.stderr, /migrations\/alembic\.ini/)
  } finally {
    fs.rmSync(webBundle, { recursive: true, force: true })
    fs.rmSync(hollow, { recursive: true, force: true })
  }
})

/**
 * The licence texts the installer carries.
 *
 * LGPL-2.1 section 1 requires a copy of the Licence to travel with the
 * Library, and the NSIS installer is what carries the Library: the plug-ins
 * are members of the installer's own archive, extracted to `$PLUGINSDIR` at
 * install time. So the texts have to be in that archive too, in the same
 * place, or the obligation is not discharged by the artefact.
 *
 * These cases watch the mechanism rather than the build: the build needs
 * electron-builder, a network and minutes, and the mechanism is what a
 * reader has to be able to check. The build that proves it is recorded in
 * `NOTICE` §5.4.
 */

/** The `File /oname=…` lines of the include, and the member they write. */
function fileCommands(include) {
  const commands = []
  for (const line of include.split('\n')) {
    const match = line.match(/^\s*File \/oname=(\S+)\s+"([^"]+)"\s*$/)
    if (match) commands.push({ member: match[1], source: match[2] })
  }
  return commands
}

/** The file name of the repository text a `File` command writes. */
function carriedName(command) {
  return path.basename(command.source.replace(/\\/g, path.sep))
}

/** The licence texts the repository holds. */
function repositoryTexts() {
  return fs.readdirSync(LICENCES_PATH).filter((name) => name.endsWith('.txt'))
}

/** The licence texts a given include carries. */
function carriedTexts(include) {
  return new Set(fileCommands(include).map(carriedName))
}

test('the packaging config names the NSIS include that carries the licence texts', () => {
  assert.match(config, /^ {2}include: nsis\/licenses\.nsh$/m)
  assert.ok(fs.existsSync(NSIS_INCLUDE_PATH), 'the configuration names an NSIS include that is absent')
})

test("the NSIS include writes each licence text into the installer's plugin directory", () => {
  const include = fs.readFileSync(NSIS_INCLUDE_PATH, 'utf8')
  assert.match(include, /^!macro customInit$/m)
  assert.match(include, /^!macroend$/m)
  assert.match(include, /^\s*InitPluginsDir$/m)
  assert.match(include, /^\s*CreateDirectory "\$PLUGINSDIR\\licenses"$/m)

  const commands = fileCommands(include)
  assert.ok(commands.length > 0, 'the include writes no file at all')
  for (const command of commands) {
    assert.match(
      command.member,
      /^\$PLUGINSDIR\\licenses\\[^\\]+$/,
      `the include writes ${command.member} outside the plugin directory's licenses subdirectory`,
    )
    const source = command.source.replace('${PROJECT_DIR}', SHELL_ROOT).replace(/\\/g, path.sep)
    assert.ok(fs.existsSync(source), `the include writes ${command.member} from ${command.source}, which is absent`)
  }
})

test('every licence text in the repository is carried by the NSIS include', () => {
  const carried = carriedTexts(fs.readFileSync(NSIS_INCLUDE_PATH, 'utf8'))
  const present = repositoryTexts()
  assert.ok(present.length > 0, 'the repository holds no licence text at all')
  for (const name of present) {
    assert.ok(carried.has(name), `shell/licenses/${name} is in the repository but the NSIS include does not carry it`)
  }
})

test('the licence texts the include carries are the ones the repository holds', () => {
  const include = fs.readFileSync(NSIS_INCLUDE_PATH, 'utf8')
  const present = new Set(repositoryTexts())
  for (const command of fileCommands(include)) {
    const name = carriedName(command)
    assert.ok(present.has(name), `the include writes ${name}, which shell/licenses/ does not hold`)
  }
})

test('the packaging config ships the two T09 supply templates into the package', () => {
  // The templates travel so an installed shell can be told its backend and
  // workspace either way: the launcher beside the exe, the JSON beside the
  // asar. A template is not a default — nothing reads them until they exist
  // under their live names — so shipping them is inert without an edit.
  assert.match(config, /^  - from: shell-env\.template\.json\n    to: shell-env\.template\.json$/m)
  assert.match(config, /^  - from: labcairn-shell\.cmd\n    to: labcairn-shell\.cmd$/m)
  for (const name of ['shell-env.template.json', 'labcairn-shell.cmd']) {
    assert.ok(fs.existsSync(path.join(SHELL_ROOT, name)), `${name} is declared for shipping but absent`)
  }
  // The live name must not ship: only the template does.
  assert.ok(!/^  - from: shell-env\.json$/m.test(config), 'a live shell-env.json must not be shipped by the build')
})

test('a licence text the include does not name is a gap the mutation shows', () => {
  const include = fs.readFileSync(NSIS_INCLUDE_PATH, 'utf8')
  const commands = fileCommands(include)
  const first = commands[0]
  assert.ok(first, 'the include writes no file, so there is nothing to mutate')

  const mutated = include.replace(first.source, '${PROJECT_DIR}\\licenses\\NOT-THERE.txt')
  assert.notEqual(mutated, include, 'the mutation did not change the include')

  const carried = carriedTexts(mutated)
  const dropped = carriedName(first)
  assert.ok(!carried.has(dropped), 'the mutated include still carries the licence text it was supposed to drop')

  const gaps = repositoryTexts().filter((name) => !carried.has(name))
  assert.ok(gaps.length > 0, 'the mutation left the repository texts carried, so the check has no teeth')
})
