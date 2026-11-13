/**
 * T09's configuration-file supply: the packaged shell may be told its backend
 * entry point and its workspace by its own `resources/shell-env.json`, and the
 * environment always wins over the file.
 *
 * This witness holds the pure layer: the parser, the installation-relative
 * workspace form, and the precedence the main process applies. The main
 * process's read of the real file is a wiring line (like `installGuardIpc`),
 * and the packaged-run drill (`shell/scripts/rehearse-packaged-shell-env.mjs`)
 * drives the real file end to end.
 */

import assert from 'node:assert/strict'
import test from 'node:test'

import { parseShellEnv, resolveShellEnvWorkspace } from '../src/shell-env.mjs'

test('the template form parses: an absolute CLI and an installation-relative workspace', () => {
  const parsed = parseShellEnv(JSON.stringify({
    workspace: 'LabCairn-workspace',
  }))
  assert.deepEqual(parsed, { workspace: 'LabCairn-workspace' })
})

test('absolute values pass through untouched', () => {
  const parsed = parseShellEnv(JSON.stringify({
    cliPath: 'C:\\Program Files\\LabCairn\\backend\\labcairn.exe',
    workspace: 'D:\\Labs\\pilot-workspace',
  }))
  assert.deepEqual(parsed, {
    cliPath: 'C:\\Program Files\\LabCairn\\backend\\labcairn.exe',
    workspace: 'D:\\Labs\\pilot-workspace',
  })
})

test('an unknown field is a refusal, not a silent default', () => {
  assert.throws(
    () => parseShellEnv('{"workspace":"C:/ws","cli":"labcairn.exe"}'),
    /unknown field "cli"/,
  )
})

test('a relative CLI path is a refusal: no cwd guessing, from a file either way', () => {
  assert.throws(
    () => parseShellEnv('{"cliPath":"labcairn.exe"}'),
    /"cliPath" must be an absolute path/,
  )
})

test('a non-string workspace is refused; the file may still name the relative form', () => {
  assert.throws(
    () => parseShellEnv('{"workspace":42}'),
    /"workspace" must be a path string/,
  )
})

test('broken JSON is a refusal with the reason named', () => {
  assert.throws(() => parseShellEnv('{workspace:}'), /not valid JSON/)
  assert.throws(() => parseShellEnv('[]'), /must be a JSON object/)
})

test('the installation-relative workspace resolves beside the resources directory', () => {
  const resourcesDir = 'C:\\Program Files\\LabCairn\\resources'
  assert.equal(
    resolveShellEnvWorkspace('LabCairn-workspace', resourcesDir),
    'C:\\Program Files\\LabCairn\\LabCairn-workspace',
  )
  // A relative form with a subdirectory also anchors to the installation.
  assert.equal(
    resolveShellEnvWorkspace('workspaces\\pilot-1', resourcesDir),
    'C:\\Program Files\\LabCairn\\workspaces\\pilot-1',
  )
})

test('an absolute workspace in the file passes through, whatever the resources path', () => {
  assert.equal(
    resolveShellEnvWorkspace('D:\\Labs\\pilot', 'C:\\Program Files\\LabCairn\\resources'),
    'D:\\Labs\\pilot',
  )
})

test('a relative workspace with no resources directory to anchor to is a refusal', () => {
  assert.throws(
    () => resolveShellEnvWorkspace('LabCairn-workspace', null),
    /no resources directory is known/,
  )
})
