/**
 * T06's update path: the upgrade is a reinstall, and nothing checks the
 * network for one.
 *
 * **The plan's scope.** The clean-Windows drill is "install → launch →
 * upgrade → uninstall → rollback preserving user data" (plan §7 T09 row,
 * §4.3's lifecycle table) — an upgrade is a newer installer run over an
 * older installation, the way the T09 checklist's D12–D18 rows drill it.
 * The threat model records the product's own rule: "no telemetry, no update
 * check, no CDN fetch" — so the update path is deliberately *not* an
 * auto-updater, and this witness holds that absence as a property: an
 * updater reaching for the network is a red tree, not a feature.
 *
 * **Why identity fields are update-path machinery.** A reinstall preserves
 * the user's data only while the installed identity does not move: Electron
 * derives `userData` from the app name, NSIS derives the upgrade from the
 * `appId`, and the uninstaller leaves `userData` alone only while
 * `deleteAppDataOnUninstall` stays unset. Each of those is a line in the
 * tree, and each is watched here — because a silent rename is an upgrade
 * that strands the user's workspace, and nothing else would notice.
 */

import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SHELL_ROOT = path.resolve(HERE, '..')
const SRC_DIR = path.join(SHELL_ROOT, 'src')
const MANIFEST = JSON.parse(fs.readFileSync(path.join(SHELL_ROOT, 'package.json'), 'utf8'))
const BUILDER_CONFIG = fs.readFileSync(path.join(SHELL_ROOT, 'electron-builder.yml'), 'utf8')

/** Every runtime source file, as { name, text }. */
function runtimeSources() {
  return fs.readdirSync(SRC_DIR).filter((name) => name.endsWith('.mjs') || name.endsWith('.cjs')).map((name) => ({
    name,
    text: fs.readFileSync(path.join(SRC_DIR, name), 'utf8'),
  }))
}

test('no runtime source reaches for an updater or a remote update feed', () => {
  for (const { name, text } of runtimeSources()) {
    for (const banned of ['autoUpdater', 'setFeedURL', 'checkForUpdates', 'electron-updater']) {
      assert.ok(!text.includes(banned), `${name} mentions ${banned}; the update path is a reinstall, not a feed`)
    }
  }
})

test('the packaging config carries no publish target and no update-feed setting', () => {
  assert.ok(!/^publish:/m.test(BUILDER_CONFIG), 'a publish target is a network update feed; W28 and the offline rule forbid one')
  assert.ok(!/electron-updater|app-update\.yml|updateProvider/i.test(BUILDER_CONFIG), 'no update provider is configured')
})

test('the installed identity is fixed, so a reinstall lands in the same userData', () => {
  // Electron derives userData from the manifest name; the T09 probe measured
  // %APPDATA%\@labcairn\shell from exactly this value. A rename strands it.
  assert.equal(MANIFEST.name, '@labcairn/shell')
  // NSIS upgrades in place by appId; changing it installs a second product.
  assert.match(BUILDER_CONFIG, /^appId: org\.labcairn\.shell$/m)
  // productName names the installed files; it must stay the product's name.
  assert.match(BUILDER_CONFIG, /^productName: LabCairn$/m)
})

test('the version is a comparable semver, so an upgrade has an order', () => {
  assert.match(MANIFEST.version, /^\d+\.\d+\.\d+$/, `version ${MANIFEST.version} is not a comparable semver`)
})

test('the installer neither deletes nor resets userData on uninstall or upgrade', () => {
  // electron-builder only generates the delete section when the key is set;
  // the T09 checklist's D16 reads this same absence.
  assert.ok(!/deleteAppDataOnUninstall/.test(BUILDER_CONFIG), 'deleteAppDataOnUninstall would make an upgrade destroy the user data')
})

test('counter-mutations: an updater, a feed and a data wipe are each caught', () => {
  // The same reads, run against mutated trees, must each go red — the
  // witness fails for the property, not for the file's existence. The
  // planted text is a bare word, not an import form: the static reader that
  // watches this directory's own imports must not read the mutation string
  // as a package specifier.
  const planted = '// autoUpdater, setFeedURL, checkForUpdates, electron-updater — planted'
  const withUpdater = runtimeSources().map((source) => ({
    ...source,
    text: source.name === 'main.mjs' ? `${source.text}\n${planted}\n` : source.text,
  }))
  const caught = withUpdater.some(({ name, text }) =>
    name === 'main.mjs' && ['autoUpdater', 'setFeedURL', 'checkForUpdates', 'electron-updater'].some((banned) => text.includes(banned)),
  )
  assert.ok(caught, 'planting an autoUpdater import in main.mjs went unnoticed')

  const withPublish = `${BUILDER_CONFIG}\npublish:\n  - provider: generic\n    url: https://updates.example.invalid/\n`
  assert.ok(/^publish:/m.test(withPublish), 'the publish reader missed its own planted key')

  const withWipe = `${BUILDER_CONFIG}\n  deleteAppDataOnUninstall: true\n`
  assert.ok(/deleteAppDataOnUninstall/.test(withWipe), 'the deleteAppDataOnUninstall reader missed its own planted key')
})
