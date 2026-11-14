/**
 * The packaged shell's own configuration file: the second way a packaged run
 * is told where its backend and its workspace are (T09's supply question,
 * PHASE_3-work-orders.md §17 "Who supplies a packaged run's three environment
 * variables").
 *
 * **The two ways, and why both exist.** Nothing in the installer supplies
 * `LABCAIRN_SHELL_CLI` or `LABCAIRN_SHELL_WORKSPACE` (measured 2026-11-11:
 * the package carries no Python at all, and the variables are read from the
 * environment only). The two candidate supplies are:
 *
 * - **The environment** — a launcher script (or a drilled shortcut) sets the
 *   two variables before the shell starts. `config.mjs` already reads them;
 *   `shell/scripts/labcairn-shell.cmd` is the launcher template.
 * - **The package's own `resources/shell-env.json`** — a file the installer
 *   ships beside the asar, read when the environment names nothing. The
 *   template travels with the build (`shell-env.template.json`); the owner
 *   decides the installed values (O3's own supply decision, 2026-11-14, is
 *   the mixed form: the file carries `workspace` in its installation-relative
 *   form, and `cliPath` joins the file only once the frozen backend is
 *   packaged — until then the field is absent, which is a refusal at
 *   startup, not a guessed default).
 *
 * **Precedence is explicit wins.** An environment variable beats the file:
 * the file is the package's default, the environment is the operator's word.
 * A value that is present but not an absolute path is a refusal either way —
 * §4.1's rule ("No cwd guessing") does not bend for a file.
 *
 * **The one relative form allowed.** The template may name the workspace
 * relative to the installation itself (`"workspace": "LabCairn-workspace"`
 * means *beside the resources directory, inside the installation*). That is
 * not a working-directory guess: it is anchored to the package's own known
 * location, the same anchoring `resources/web-dist` already uses. In the
 * environment, only absolute paths are accepted.
 *
 * **Unknown fields are a refusal, not a silent drop.** `parseShellEnv`
 * rejects any field outside the two-name allowlist, and the refusal is
 * deliberate: a mistyped field name (`"cliPath"` spelled `"clipath"`, or a
 * human-note field like the template's former `_comment`) would otherwise
 * be silently ignored, and a packaged run would start with the operator's
 * intended value missing and nothing saying so. Refusing at startup makes
 * the mistake visible where it can be fixed; this is the same
 * "no guessed defaults" posture the rest of the file holds (§4.1). Measured
 * 2026-11-14: `shell-env.template.json` carrying a `_comment` field, if
 * renamed and used as-is, fails startup with `unknown field "_comment"`;
 * the comment was removed from the template the same day.
 */

import path from 'node:path'

const ALLOWED_FIELDS = ['cliPath', 'workspace']

function isAbsolutePath(value) {
  return typeof value === 'string' && /^([A-Za-z]:[\\/]|\/)/.test(value)
}

/**
 * Parse and validate the contents of a `shell-env.json`.
 *
 * @param text  the file's text
 * @returns {{ cliPath?: string, workspace?: string }}
 *   only the fields present; `cliPath` is an absolute path, `workspace` may be
 *   installation-relative (resolved by `resolveShellEnvWorkspace`).
 */
export function parseShellEnv(text) {
  let parsed
  try {
    parsed = JSON.parse(text)
  } catch (error) {
    throw new Error(`shell-env.json is not valid JSON: ${error.message}`)
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('shell-env.json must be a JSON object')
  }
  for (const field of Object.keys(parsed)) {
    if (!ALLOWED_FIELDS.includes(field)) {
      throw new Error(
        `shell-env.json names the unknown field "${field}"; the known fields are ${ALLOWED_FIELDS.join(', ')}. ` +
          'A mistyped field name must be a refusal, not a silent default.',
      )
    }
    if (parsed[field] !== null && typeof parsed[field] !== 'string') {
      throw new Error(
        `shell-env.json's "${field}" must be a path string or null; ` +
          `got ${JSON.stringify(parsed[field])}.`,
      )
    }
    if (field === 'cliPath' && typeof parsed[field] === 'string' && !isAbsolutePath(parsed[field])) {
      throw new Error(
        `shell-env.json's "cliPath" must be an absolute path (or null); ` +
          `got ${JSON.stringify(parsed[field])}.`,
      )
    }
  }
  const result = {}
  for (const field of ALLOWED_FIELDS) {
    if (typeof parsed[field] === 'string' && parsed[field].length > 0) {
      result[field] = parsed[field]
    }
  }
  return result
}

/**
 * Resolve one workspace value, allowing the file's installation-relative
 * form. An absolute value passes through; a relative value is anchored to
 * the installation root (the resources directory's parent), never to the
 * process's working directory.
 *
 * @param value  the workspace string from the file
 * @param resourcesDir  the packaged app's resources directory
 */
export function resolveShellEnvWorkspace(value, resourcesDir) {
  if (isAbsolutePath(value)) return value
  if (typeof resourcesDir !== 'string' || resourcesDir.length === 0) {
    throw new Error(
      `shell-env.json's workspace "${value}" is relative, and no resources ` +
        'directory is known to anchor it to the installation.',
    )
  }
  // Anchor to the installation root with the path module matching the
  // resources directory's own form: a Windows path resolves as a Windows
  // path even if this code ever runs where `path` is POSIX, so the
  // installation-relative form means the same thing on both.
  const anchor = /^[A-Za-z]:[\\/]/.test(resourcesDir) ? path.win32 : path
  return anchor.resolve(resourcesDir, '..', value)
}
