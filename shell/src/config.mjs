/**
 * Run-mode resolution: the one place that decides what the shell loads and
 * what it starts. A pure function over (env, packaged, resourcesDir) so a
 * witness asserts the packaged/dev difference without a display.
 *
 * **The dev switch (§4.2) is a one-line difference in the URL the window
 * loads**, and it is opt-in on all three counts: not packaged, `LABCAIRN_SHELL_DEV=1`,
 * and a loopback page origin. A packaged configuration that names a dev page
 * URL is a refusal, not an override — AC-1's "the dev-build URL is rejected
 * in a packaged configuration".
 */

import fs from 'node:fs'
import path from 'node:path'

import { parseShellEnv, resolveShellEnvWorkspace } from './shell-env.mjs'

/** The Vite origin the dev page is loaded from (§4.2). */
export const DEV_PAGE_ORIGIN = 'http://127.0.0.1:5173'

/** The configuration file a packaged build may carry beside its asar (T09). */
export const SHELL_ENV_FILE = 'shell-env.json'

function requireAbsolute(name, value) {
  if (typeof value !== 'string' || value.length === 0) return null
  if (!/^([A-Za-z]:[\\/]|\/)/.test(value)) {
    throw new Error(
      `${name} must be an absolute path — a name resolved from PATH or a relative ` +
        'path is a guess about the working directory (§4.1: "No cwd guessing").',
    )
  }
  return value
}

/**
 * Where a packaged build keeps its own web bundle.
 *
 * The installer ships the bundle at `resources/web-dist`, beside the asar.
 * Measured on 2026-11-11: the package carried the bundle and the code named
 * no reader for it, so a packaged run had to be told where its own bundle
 * was — by an environment variable nothing in the package supplies. The
 * bundle's place in the package is not a guess about the working directory,
 * so it is derived rather than asked for.
 *
 * @param {string | null} resourcesDir Electron's resources directory
 * @param {boolean} packaged whether this is a packaged build
 * @returns {string | null} the bundle directory, or null when there is none
 */
function packagedBundleDir(resourcesDir, packaged) {
  if (!packaged || typeof resourcesDir !== 'string' || resourcesDir.length === 0) {
    return null
  }
  return path.join(resourcesDir, 'web-dist')
}

/**
 * Where a packaged build keeps its own configuration file.
 *
 * Same anchoring as the bundle: beside the asar, derived, not guessed. The
 * file is optional — a null return means "the package carries none" and the
 * caller keeps the environment-only behaviour.
 */
function packagedShellEnvPath(resourcesDir, packaged) {
  if (!packaged || typeof resourcesDir !== 'string' || resourcesDir.length === 0) {
    return null
  }
  return path.join(resourcesDir, SHELL_ENV_FILE)
}

/**
 * Read the packaged configuration file, if this build carries one.
 *
 * The environment is the operator's word and wins; the file is the package's
 * default. A file that exists but does not parse is a refusal — a package
 * that carries a broken default is broken, and silence would turn it into a
 * missing-variable error far from the cause.
 *
 * @param {string | null} shellEnvPath where the file would be
 * @returns {{ cliPath?: string, workspace?: string, read: boolean }}
 */
function readPackagedShellEnv(shellEnvPath) {
  if (shellEnvPath === null) return { read: false }
  let text
  try {
    text = fs.readFileSync(shellEnvPath, 'utf8')
  } catch {
    // Absent is the normal case: the package ships the template commented
    // out, or the operator chose the environment-only supply.
    return { read: false }
  }
  return { ...parseShellEnv(text), read: true }
}

/**
 * Resolve the run configuration.
 *
 * @param env  the environment (pass `process.env` in main; a test passes its own)
 * @param packaged  whether this is a packaged build (Electron's `app.isPackaged`)
 * @param resourcesDir Electron's resources directory in a packaged build
 * @returns {{ dev: boolean, pageUrl: string | null, cliPath: string, workspace: string,
 *            staticDir: string | null, port: number | null }}
 *   `pageUrl` is null in packaged mode — the page is the service's own origin,
 *   which is only known once `ServiceStarting` has been read.
 */
export function resolveRunConfig(env, { packaged, resourcesDir = null }) {
  if (packaged && env.LABCAIRN_SHELL_DEV_URL) {
    throw new Error(
      'a packaged build refuses LABCAIRN_SHELL_DEV_URL: the packaged window loads ' +
        "the service's own origin and nothing else (ADR-0023, AC-1).",
    )
  }
  const dev = !packaged && env.LABCAIRN_SHELL_DEV === '1'

  const devUrl = env.LABCAIRN_SHELL_DEV_URL ?? DEV_PAGE_ORIGIN
  if (dev) {
    const origin = new URL(devUrl).origin
    if (origin !== DEV_PAGE_ORIGIN && !/^http:\/\/(127\.0\.0\.1|localhost):5173$/.test(origin)) {
      throw new Error(
        `LABCAIRN_SHELL_DEV_URL must be the Vite origin (${DEV_PAGE_ORIGIN}); ` +
          `got ${origin}.`,
      )
    }
  }

  // T09's supply precedence: the environment names it, or the package's own
  // `resources/shell-env.json` does. The file's `workspace` may be
  // installation-relative; the environment only accepts absolute paths.
  const fromFile = readPackagedShellEnv(packagedShellEnvPath(resourcesDir, packaged))

  const cliPath =
    requireAbsolute('LABCAIRN_SHELL_CLI', env.LABCAIRN_SHELL_CLI) ??
    requireAbsolute('shell-env.json "cliPath"', fromFile.cliPath ?? null)
  if (cliPath === null) {
    throw new Error(
      'LABCAIRN_SHELL_CLI must name the labcairn entry point by absolute path ' +
        '(in a dev checkout, the virtualenv\'s console script; in a packaged ' +
        `build, the environment or ${SHELL_ENV_FILE}).`,
    )
  }

  const workspaceEnv = requireAbsolute('LABCAIRN_SHELL_WORKSPACE', env.LABCAIRN_SHELL_WORKSPACE)
  const workspace =
    workspaceEnv ??
    (fromFile.workspace !== undefined
      ? resolveShellEnvWorkspace(fromFile.workspace, resourcesDir)
      : null)
  if (workspace === null) {
    throw new Error(
      'LABCAIRN_SHELL_WORKSPACE must name the workspace by absolute path ' +
        `(the environment, or ${SHELL_ENV_FILE}'s "workspace").`,
    )
  }

  const staticDir =
    requireAbsolute('LABCAIRN_SHELL_STATIC_DIR', env.LABCAIRN_SHELL_STATIC_DIR) ??
    packagedBundleDir(resourcesDir, packaged)

  const portRaw = env.LABCAIRN_SHELL_PORT
  let port = null
  if (portRaw !== undefined && portRaw !== '') {
    port = Number(portRaw)
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      throw new Error(`LABCAIRN_SHELL_PORT is not a port number: ${portRaw}`)
    }
  }

  return {
    dev,
    pageUrl: dev ? devUrl : null,
    cliPath,
    workspace,
    staticDir,
    port,
  }
}
