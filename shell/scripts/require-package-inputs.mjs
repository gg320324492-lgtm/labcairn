/**
 * The packaging guard: no installer is built without the web bundle or the
 * frozen backend.
 *
 * **Why this exists.** `electron-builder.yml` copies the web bundle and the
 * frozen backend into the packaged app with `extraResources`. When a source
 * directory is absent, electron-builder prints `file source doesn't exist`
 * -- once per missing path, so the build measured on 2026-11-11 printed it
 * twice -- and **keeps going**. Measured on 2026-11-11: a build with no
 * `web/dist` exited 0 and produced an installer whose `resources/` carried
 * no `web-dist` at all, while the same build with the bundle present exited 0
 * with the three bundle files inside it. An installer without the frontend
 * installs a window that cannot render; since 2026-11-14 an installer without
 * the frozen backend (`shell/build/backend-freeze/labcairn/`, the product of
 * `shell/scripts/build-backend-freeze.mjs`) installs a shell that cannot
 * start its service — the package's own `shell-env.json` names
 * `backend/labcairn`, and nothing else supplies `LABCAIRN_SHELL_CLI` in the
 * package-only supply. Nothing in electron-builder said so for either, so
 * this hook turns a missing input into a build failure.
 *
 * **What it checks.** Each input directory must exist, must be a directory,
 * and must carry its entry artifact: the web bundle its `index.html`, the
 * frozen backend its `labcairn.exe` (the frozen entry the supervisor spawns)
 * and its `migrations/` tree (the schema the frozen exe resolves beside
 * itself — a frozen exe without it refuses `init`). An empty directory is as
 * broken as a missing one.
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

/** The frozen backend the shell packages: the freeze script's output. */
const BACKEND_FREEZE = path.resolve(HERE, '..', 'build', 'backend-freeze', 'labcairn')

/** The entry document the packaged window loads. */
const ENTRY_DOCUMENT = 'index.html'

/** The entry binary the supervisor spawns, per platform. */
const BACKEND_EXE = process.platform === 'win32' ? 'labcairn.exe' : 'labcairn'

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
 * Why this frozen backend cannot be packaged, or null when it can.
 *
 * @param {string} directory the frozen onedir bundle to inspect
 * @returns {string | null} the reason the backend is unusable, or null
 */
export function backendProblem(directory) {
  if (!fs.existsSync(directory)) {
    return (
      `the frozen backend directory is absent: ${directory} — run ` +
      'shell/scripts/build-backend-freeze.mjs first (the freeze is a build ' +
      'product under shell/build/, never tracked, and packaging does not run it).'
    )
  }
  if (!fs.statSync(directory).isDirectory()) {
    return `the frozen backend path is not a directory: ${directory}`
  }
  if (!fs.existsSync(path.join(directory, BACKEND_EXE))) {
    return `the frozen backend carries no ${BACKEND_EXE}: ${directory}`
  }
  if (!fs.existsSync(path.join(directory, 'migrations', 'alembic.ini'))) {
    return `the frozen backend carries no migrations/alembic.ini: ${directory}`
  }
  return null
}

/**
 * Build the hook electron-builder calls, for named input directories.
 *
 * @param {string} webDist the web bundle directory to check
 * @param {string} backendFreeze the frozen backend directory to check
 * @returns {() => Promise<boolean>} the hook
 */
export function makeGuard(webDist, backendFreeze = BACKEND_FREEZE) {
  return async function beforeBuild() {
    const webProblem = bundleProblem(webDist)
    if (webProblem) {
      throw new Error(`the packaging guard refuses this build: ${webProblem}`)
    }
    const backend = backendProblem(backendFreeze)
    if (backend) {
      throw new Error(`the packaging guard refuses this build: ${backend}`)
    }
    return true
  }
}

/**
 * The hook electron-builder resolves. It must return true: a falsy return
 * makes electron-builder treat the dependencies as handled elsewhere and skip
 * its own rebuild.
 */
export default makeGuard(WEB_DIST, BACKEND_FREEZE)

/** Run as a script: check the input directories and report. */
function main(argv) {
  const webDist = argv[0] ? path.resolve(argv[0]) : WEB_DIST
  const backendFreeze = argv[1] ? path.resolve(argv[1]) : BACKEND_FREEZE
  const webProblem = bundleProblem(webDist)
  const backend = backendProblem(backendFreeze)
  if (webProblem || backend) {
    if (webProblem) process.stderr.write(`the packaging guard refuses this build: ${webProblem}\n`)
    if (backend) process.stderr.write(`the packaging guard refuses this build: ${backend}\n`)
    process.stderr.write(
      'build the web bundle (pnpm --dir web run build) and the frozen backend\n' +
        '(node shell/scripts/build-backend-freeze.mjs) first, then package the shell.\n',
    )
    process.exit(1)
  }
  process.stdout.write(`the web bundle is present: ${webDist}\n`)
  process.stdout.write(`the frozen backend is present: ${backendFreeze}\n`)
}

// Only when this file is the program being run, never when it is imported.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2))
}
