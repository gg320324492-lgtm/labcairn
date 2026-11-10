/**
 * Path resolution shared by the shell's live witnesses.
 *
 * **Why a module and not six copies.** A rehearsal run from a mutated copy of
 * `shell/` must still start this checkout's installed CLI and this checkout's
 * product code: a copy that accidentally measured another tree would report a
 * mutation on a tree it did not change. Every override is explicit, and the
 * defaults work from a normal checkout *and* from `.claude/worktrees/<name>`.
 *
 * Scratch, logs and temp state live under `E:\labcairn-local\tmp` — outside the
 * repository (`CLAUDE.md`; the shell skeleton record §8).
 */

import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const WINDOWS = process.platform === 'win32'

/** Resolve the paths a live witness needs from its own location and env. */
export function shellPaths({ here, env = process.env }) {
  const shellRoot = env.LABCAIRN_SHELL_ROOT ?? path.join(here, '..')
  const repoRoot = env.LABCAIRN_SHELL_REPO_ROOT ?? path.resolve(shellRoot, '..')
  const parts = repoRoot.split(path.sep)
  const inWorktree = parts.includes('.claude') && parts.includes('worktrees')
  const checkoutRoot = env.LABCAIRN_SHELL_CHECKOUT_ROOT ??
    (inWorktree ? path.resolve(repoRoot, '..', '..', '..') : repoRoot)

  const pythonExe = env.LABCAIRN_SHELL_PYTHON ?? path.join(
    checkoutRoot,
    '.venv',
    WINDOWS ? 'Scripts' : 'bin',
    WINDOWS ? 'python.exe' : 'python',
  )
  const cliExe = env.LABCAIRN_SHELL_CLI ??
    path.join(path.dirname(pythonExe), WINDOWS ? 'labcairn.exe' : 'labcairn')
  const electronExe = env.LABCAIRN_SHELL_ELECTRON ?? path.join(
    shellRoot,
    'node_modules',
    'electron',
    'dist',
    WINDOWS ? 'electron.exe' : 'electron',
  )
  const productSrc = env.LABCAIRN_SHELL_PRODUCT_SRC ?? path.join(repoRoot, 'src')
  const scratchRoot = env.LABCAIRN_SHELL_SCRATCH ?? 'E:\\labcairn-local\\tmp\\lc-p305-shell'

  return { shellRoot, repoRoot, checkoutRoot, pythonExe, cliExe, electronExe, productSrc, scratchRoot }
}

/**
 * The paths a live witness needs must actually exist before the witness runs.
 *
 * A missing console script or Electron binary is not a failure of the property
 * under test, and a witness that reports a refusal when the binary was simply
 * absent reports the tree's setup as the product's behaviour. This says so
 * first, and it makes the scratch root — outside the repository — rather than
 * letting a child create it wherever the working directory happens to be.
 */
export function assertPaths(paths) {
  for (const [name, where] of [['labcairn', paths.cliExe], ['electron', paths.electronExe]]) {
    assert.ok(fs.existsSync(where), `the witness cannot find ${name} at ${where}`)
  }
  fs.mkdirSync(paths.scratchRoot, { recursive: true })
}
