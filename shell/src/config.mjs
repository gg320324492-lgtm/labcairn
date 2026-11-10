/**
 * Run-mode resolution: the one place that decides what the shell loads and
 * what it starts. A pure function over (env, packaged) so a witness asserts
 * the packaged/dev difference without a display.
 *
 * **The dev switch (§4.2) is a one-line difference in the URL the window
 * loads**, and it is opt-in on all three counts: not packaged, `LABCAIRN_SHELL_DEV=1`,
 * and a loopback page origin. A packaged configuration that names a dev page
 * URL is a refusal, not an override — AC-1's "the dev-build URL is rejected
 * in a packaged configuration".
 */

/** The Vite origin the dev page is loaded from (§4.2). */
export const DEV_PAGE_ORIGIN = 'http://127.0.0.1:5173'

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
 * Resolve the run configuration.
 *
 * @param env  the environment (pass `process.env` in main; a test passes its own)
 * @param packaged  whether this is a packaged build (Electron's `app.isPackaged`)
 * @returns {{ dev: boolean, pageUrl: string | null, cliPath: string, workspace: string,
 *            staticDir: string | null, port: number | null }}
 *   `pageUrl` is null in packaged mode — the page is the service's own origin,
 *   which is only known once `ServiceStarting` has been read.
 */
export function resolveRunConfig(env, { packaged }) {
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

  const cliPath = requireAbsolute('LABCAIRN_SHELL_CLI', env.LABCAIRN_SHELL_CLI)
  if (cliPath === null) {
    throw new Error(
      'LABCAIRN_SHELL_CLI must name the labcairn entry point by absolute path ' +
        '(in a dev checkout, the virtualenv\'s console script).',
    )
  }
  const workspace = requireAbsolute('LABCAIRN_SHELL_WORKSPACE', env.LABCAIRN_SHELL_WORKSPACE)
  if (workspace === null) {
    throw new Error('LABCAIRN_SHELL_WORKSPACE must name the workspace by absolute path.')
  }
  const staticDir = requireAbsolute('LABCAIRN_SHELL_STATIC_DIR', env.LABCAIRN_SHELL_STATIC_DIR)

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
