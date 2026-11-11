/**
 * The packaging guard: no installer is built without the web bundle.
 *
 * **Why this exists.** `electron-builder.yml` copies the web bundle into the
 * packaged app with `extraResources`. When that source directory is absent,
 * electron-builder prints one line -- `file source doesn't exist` -- and
 * **keeps going**. Measured on 2026-11-11: a build with no `web/dist`
 * exited 0 and produced an installer whose `resources/` carried no
 * `web-dist` at all, while the same build with the bundle present exited 0
 * with the three bundle files inside it. An installer without the frontend
 * installs a window that cannot render, and nothing in the build said so.
 *
 * **What it checks.** The bundle directory must exist, must be a directory,
 * and must carry the entry document. An empty directory is as broken as a
 * missing one, and a bundle without `index.html` cannot be loaded.
 *
 * **The shape electron-builder calls it in.** `beforeBuild` is resolved with
 * `resolveFunction`, which imports the module and takes `m[name]` or, failing
 * that, `m.default || m`; a module with neither is called as if it were a
 * function and the build dies with `beforeBuild is not a function`. The hook
 * is therefore a **default export**, and the module has **no top-level
 * side effect**: importing it must not check anything, and must not exit.
 * The hook is called with a context object and its return value decides
 * whether electron-builder still rebuilds native dependencies --
 * `this._nodeModulesHandledExternally = !performDependenciesInstallOrRebuild`
 * -- so a hook that passes the check returns **true**, and only a falsy
 * return would make electron-builder skip that work.
 *
 * **How it fails.** The hook throws, so electron-builder stops the packaging
 * run before anything is written. Run as a script it prints the reason and
 * exits non-zero, which is what the witness exercises directly.
 */

import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))

/** The bundle the shell packages: the web workspace's build output. */
const WEB_DIST = path.resolve(HERE, '..', '..', 'web', 'dist')

/** The entry document the packaged window loads. */
const ENTRY_DOCUMENT = 'index.html'

/**
 * Why this bundle cannot be packaged, or null when it can.
 *
 * @param {string} directory the bundle directory to inspect
 * @returns {string | null} the reason the bundle is unusable, or null
 */
export function bundleProblem(directory) {
  if (!fs.existsSync(directory)) {
    return `the web bundle directory is absent: ${directory}`
  }
  if (!fs.statSync(directory).isDirectory()) {
    return `the web bundle path is not a directory: ${directory}`
  }
  if (!fs.existsSync(path.join(directory, ENTRY_DOCUMENT))) {
    return `the web bundle carries no ${ENTRY_DOCUMENT}: ${directory}`
  }
  return null
}

/**
 * Build the hook electron-builder calls, for a named bundle directory.
 *
 * @param {string} directory the bundle directory to check
 * @returns {() => Promise<boolean>} the hook
 */
export function makeGuard(directory) {
  return async function beforeBuild() {
    const problem = bundleProblem(directory)
    if (problem) {
      throw new Error(`the packaging guard refuses this build: ${problem}`)
    }
    return true
  }
}

/**
 * The hook electron-builder resolves. It must return true: a falsy return
 * makes electron-builder treat the dependencies as handled elsewhere and skip
 * its own rebuild.
 */
export default makeGuard(WEB_DIST)

/** Run as a script: check a bundle directory and report. */
function main(argv) {
  const directory = argv[0] ? path.resolve(argv[0]) : WEB_DIST
  const problem = bundleProblem(directory)
  if (problem) {
    process.stderr.write(`the packaging guard refuses this build: ${problem}\n`)
    process.stderr.write('build the web bundle first, then package the shell.\n')
    process.exit(1)
  }
  process.stdout.write(`the web bundle is present: ${directory}\n`)
}

// Only when this file is the program being run, never when it is imported.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2))
}
