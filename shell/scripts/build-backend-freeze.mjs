/**
 * O3's frozen service: freeze `labcairn.cli:main` with PyInstaller into a
 * onedir bundle the installer can carry in `extraResources` (the owner's
 * 2026-11-14 decision; the decision material is the T09/O3 decision brief).
 *
 * **Why a script and not a documented command.** The freeze is a measured
 * act, not a recipe: the output directory, the entry point it must carry,
 * and the one environment flag the current dependency graph needs
 * (`PYDANTIC_DISABLE_PLUGINS=1`, see the acceptance record's freeze section)
 * are all fixed here, so the drill and the acceptance record measure the
 * same artifact instead of three people's memory of a command line.
 *
 * **What it produces.** `<repo>/shell/build/backend-freeze/labcairn/` — a
 * onedir tree whose `labcairn.exe` is the frozen `labcairn.cli:main`. The
 * directory is a build product: `.gitignore` excludes `shell/build/`, and
 * the installer work that ships it is a later, separately-drilled step.
 *
 * **The plugin flag is measured, not assumed.** `logfire`'s pydantic plugin
 * (a transitive of `pydantic-ai`'s `logfire` extra) reads its target's
 * source text at import time (`inspect.getsource`), which a frozen
 * application cannot provide. The flag is set by this script for the child
 * process as well as the freeze itself, so a frozen run is self-contained.
 *
 * Usage: `node shell/scripts/build-backend-freeze.mjs`
 * (exit 0 and prints the artifact paths; any failure is a non-zero exit).
 */

import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SHELL_ROOT = path.resolve(HERE, '..')
const REPO_ROOT = path.resolve(SHELL_ROOT, '..')
const OUTPUT_DIR = path.join(SHELL_ROOT, 'build', 'backend-freeze')
const ENTRY = 'labcairn.cli:main'

function fail(message) {
  process.stderr.write(`build-backend-freeze: ${message}\n`)
  process.exit(1)
}

/** Locate the project's Python and the PyInstaller it must carry. */
function findPython() {
  const windows = process.platform === 'win32'
  // A worktree checkout holds no .venv; the real checkout is three levels up
  // (.claude/worktrees/<name>), the same resolution shell-paths.mjs makes.
  const parts = REPO_ROOT.split(path.sep)
  const inWorktree = parts.includes('.claude') && parts.includes('worktrees')
  const checkoutRoot = inWorktree ? path.resolve(REPO_ROOT, '..', '..', '..') : REPO_ROOT
  const venvPython = windows
    ? path.join(checkoutRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(checkoutRoot, '.venv', 'bin', 'python')
  if (fs.existsSync(venvPython)) return venvPython
  return windows ? 'python.exe' : 'python3'
}

const python = findPython()

// PyInstaller must be importable by the interpreter that runs the freeze.
const probe = spawnSync(python, ['-c', 'import PyInstaller; print(PyInstaller.__version__)'], {
  encoding: 'utf8',
})
if (probe.status !== 0) {
  fail(
    `PyInstaller is not importable from ${python}. Install it into the project ` +
      `virtualenv first (uv pip install pyinstaller); it is a freeze-time tool, ` +
      'not a runtime dependency, so it stays out of pyproject.toml.',
  )
}
const pyinstallerVersion = probe.stdout.trim()

// The freeze entry: a tiny script that imports the CLI entry point so the
// bundle's __main__ is exactly the console script's target.
fs.mkdirSync(OUTPUT_DIR, { recursive: true })
const workDir = fs.mkdtempSync(path.join(OUTPUT_DIR, 'build-'))
const entryFile = path.join(workDir, 'freeze_labcairn_cli.py')
fs.writeFileSync(
  entryFile,
  [
    '"""The frozen entry point: the same function the console script names."""',
    'import sys',
    '',
    'from labcairn.cli import main',
    '',
    'if __name__ == "__main__":',
    '    sys.exit(main())',
    '',
  ].join('\n'),
)

const env = {
  ...process.env,
  // The measured plugin failure: logfire's pydantic plugin calls
  // inspect.getsource at import time, and a frozen application carries no
  // source text. Disabling third-party plugins is the measured fix (the
  // acceptance record's freeze section).
  PYDANTIC_DISABLE_PLUGINS: '1',
}

const args = [
  '-m',
  'PyInstaller',
  '--noconfirm',
  '--clean',
  '--onedir',
  '--name',
  'labcairn',
  '--distpath',
  OUTPUT_DIR,
  '--workpath',
  path.join(workDir, 'work'),
  '--specpath',
  workDir,
  // The checkout's src tree: the frozen bundle carries this tree's product
  // code, so the drill measures what this tree ships.
  '--paths',
  path.join(REPO_ROOT, 'src'),
  entryFile,
]

process.stdout.write(`freeze: ${python} ${args.join(' ')}\n`)
const started = Date.now()
const build = spawnSync(python, args, { env, stdio: 'inherit' })
const elapsedMs = Date.now() - started
if (build.status !== 0) {
  fail(`PyInstaller exited ${build.status} after ${(elapsedMs / 1000).toFixed(1)}s`)
}

const bundleDir = path.join(OUTPUT_DIR, 'labcairn')
const exeName = process.platform === 'win32' ? 'labcairn.exe' : 'labcairn'
const exePath = path.join(bundleDir, exeName)
if (!fs.existsSync(exePath)) {
  fail(`the build reported success but ${exePath} is absent`)
}

// The frozen code finds its schema migrations beside itself: inside the
// bundle, `labcairn.db.migrations` resolves its repository root to the bundle
// directory, so the migrations tree must live at `<bundle>/migrations/` the
// same way it lives at `<checkout>/migrations/` in a development run. A
// frozen exe without it refuses `init` ("no Alembic configuration"). Copying
// it here is also exactly what the installer's extraResources wiring will do,
// so the drill measures the arrangement the package will ship.
const migrationsSource = path.join(REPO_ROOT, 'migrations')
if (!fs.existsSync(path.join(migrationsSource, 'alembic.ini'))) {
  fail(`the checkout's migrations tree is missing ${migrationsSource}`)
}
fs.cpSync(migrationsSource, path.join(bundleDir, 'migrations'), { recursive: true })

/** The whole onedir tree's size, in bytes (directories + files). */
function treeBytes(root) {
  let total = 0
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const full = path.join(root, entry.name)
    if (entry.isDirectory()) total += treeBytes(full)
    else total += fs.statSync(full).size
  }
  return total
}

const bytes = treeBytes(bundleDir)
fs.rmSync(workDir, { recursive: true, force: true })

process.stdout.write(
  [
    `freeze: ok`,
    `  pyinstaller ${pyinstallerVersion}`,
    `  entry ${ENTRY}`,
    `  bundle ${bundleDir}`,
    `  exe ${exePath}`,
    `  bytes ${bytes}`,
    `  seconds ${(elapsedMs / 1000).toFixed(1)}`,
  ].join('\n') + '\n',
)
