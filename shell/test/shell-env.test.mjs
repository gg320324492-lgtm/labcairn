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

import { parseShellEnv, resolveShellEnvCliPath, resolveShellEnvWorkspace } from '../src/shell-env.mjs'

test('the template form parses: the frozen exe and workspace, both installation-relative', () => {
  // The template carried only the workspace while the backend's arrangement
  // was undecided; since the frozen backend ships in the package the template
  // names it too — the exe inside the bundle directory, not the directory
  // itself, because the supervisor spawns a file.
  const parsed = parseShellEnv(JSON.stringify({
    workspace: 'LabCairn-workspace',
  }))
  assert.deepEqual(parsed, { workspace: 'LabCairn-workspace' })
  const withCli = parseShellEnv(JSON.stringify({
    cliPath: 'backend/labcairn/labcairn.exe',
    workspace: 'LabCairn-workspace',
  }))
  assert.deepEqual(withCli, {
    cliPath: 'backend/labcairn/labcairn.exe',
    workspace: 'LabCairn-workspace',
  })
})

test('an unknown field in the template is a refusal — including a comment field', () => {
  // The template once carried a `_comment` field for humans. The parser
  // refuses any unknown field, so a renamed template with that comment would
  // have refused to start the shell; the comment is gone from the template,
  // and this case holds the rule that let the removal matter.
  assert.throws(
    () => parseShellEnv('{"_comment":"why","workspace":"LabCairn-workspace"}'),
    /unknown field "_comment"/,
  )
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
  // A bare exe name is a PATH lookup, which is §4.1's cwd guess; only the
  // installation-relative form ("backend/labcairn") is allowed to be relative,
  // because it anchors to where the package lives, not to the cwd.
  assert.throws(
    () => parseShellEnv('{"cliPath":"labcairn.exe"}'),
    /"cliPath" must be an absolute path or an installation-relative path/,
  )
})

test('the installation-relative CLI form is accepted and resolves under resources', () => {
  const parsed = parseShellEnv('{"cliPath":"backend/labcairn"}')
  assert.deepEqual(parsed, { cliPath: 'backend/labcairn' })
  assert.equal(
    resolveShellEnvCliPath(parsed.cliPath, 'C:\\Program Files\\LabCairn\\resources'),
    'C:\\Program Files\\LabCairn\\resources\\backend\\labcairn',
  )
  // A Windows separator in the file is the same installation-relative form.
  assert.equal(
    resolveShellEnvCliPath('backend\\labcairn', 'C:\\Program Files\\LabCairn\\resources'),
    'C:\\Program Files\\LabCairn\\resources\\backend\\labcairn',
  )
})

test('an absolute CLI path in the file passes through untouched', () => {
  assert.equal(
    resolveShellEnvCliPath('D:\\Labs\\freeze\\labcairn.exe', 'C:\\Program Files\\LabCairn\\resources'),
    'D:\\Labs\\freeze\\labcairn.exe',
  )
})

test('an installation-relative CLI with no resources directory to anchor to is a refusal', () => {
  assert.throws(
    () => resolveShellEnvCliPath('backend/labcairn', null),
    /no resources directory is known/,
  )
})

test('a CLI path that escapes the installation is a refusal, not a resolved escape', () => {
  assert.throws(
    () => parseShellEnv('{"cliPath":"../elsewhere/labcairn.exe"}'),
    /installation-relative/,
  )
})

test('a workspace that escapes the installation is a refusal, in both separators', () => {
  // The installation-relative form is one rule for both fields: the header's
  // "never an escape (`..`)" is a property of the file's relative forms, not
  // of the CLI path alone. A workspace of `..\\..\\elsewhere` parses to an
  // absolute path outside the installation — a resolution step could only
  // confirm the escape, so the parse refuses it. The workspace may still be
  // a single step ("LabCairn-workspace", beside the resources directory), so
  // the check is the climb, not the step count.
  assert.throws(
    () => parseShellEnv(JSON.stringify({ workspace: '..\\..\\elsewhere' })),
    /must not climb out of the installation/,
  )
  assert.throws(
    () => parseShellEnv('{"workspace":"../elsewhere"}'),
    /must not climb out of the installation/,
  )
  // A name with a `..` in the middle climbs too.
  assert.throws(
    () => parseShellEnv(JSON.stringify({ workspace: 'workspaces\\..\\elsewhere' })),
    /must not climb out of the installation/,
  )
  // And the resolved value never existed to begin with: there is no
  // resolveShellEnvWorkspace call to make on an escaped value.
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

// O3's decision B (2026-11-15): the workspace lives outside the installation,
// under the running user's profile directory, so an uninstall leaves it
// behind. The file names it with the Windows/NSIS `%APPDATA%` prefix — an
// absolute in meaning, a different absolute per user — and the resolution
// expands the prefix against the APPDATA environment variable, never against
// a guess.

test('the profile-relative workspace form parses and resolves against APPDATA', () => {
  const appData = 'C:\\Users\\pc\\AppData\\Roaming'
  const parsed = parseShellEnv(JSON.stringify({ workspace: '%APPDATA%\\@labcairn\\workspace' }))
  assert.deepEqual(parsed, { workspace: '%APPDATA%\\@labcairn\\workspace' })
  // The resources directory is irrelevant to this form: the anchor is the
  // profile directory, not the installation.
  assert.equal(
    resolveShellEnvWorkspace(parsed.workspace, 'C:\\Program Files\\LabCairn\\resources', { APPDATA: appData }),
    'C:\\Users\\pc\\AppData\\Roaming\\@labcairn\\workspace',
  )
  assert.equal(
    resolveShellEnvWorkspace(parsed.workspace, null, { APPDATA: appData }),
    'C:\\Users\\pc\\AppData\\Roaming\\@labcairn\\workspace',
  )
})

test('the profile-relative prefix is case-insensitive and accepts forward slashes', () => {
  const appData = 'C:\\Users\\pc\\AppData\\Roaming'
  // NSIS and Windows path spellings vary in case; the convention is about the
  // expansion, not the letters.
  assert.equal(
    resolveShellEnvWorkspace('%appdata%\\@labcairn\\workspace', null, { APPDATA: appData }),
    'C:\\Users\\pc\\AppData\\Roaming\\@labcairn\\workspace',
  )
  // The template could as well name the target with forward slashes; the
  // expanded path is a Windows path either way.
  assert.equal(
    resolveShellEnvWorkspace('%APPDATA%/@labcairn/workspace', null, { APPDATA: appData }),
    'C:\\Users\\pc\\AppData\\Roaming\\@labcairn\\workspace',
  )
})

test('the profile-relative form without an APPDATA value to expand against is a refusal', () => {
  // A refusal, not an empty expansion: silently resolving against an absent
  // profile directory would put the workspace at a relative-looking path, and
  // §4.1's rule is that a missing fact is named, not guessed.
  assert.throws(
    () => resolveShellEnvWorkspace('%APPDATA%\\@labcairn\\workspace', null, {}),
    /no APPDATA value is known/,
  )
  assert.throws(
    () => resolveShellEnvWorkspace('%APPDATA%\\@labcairn\\workspace', null),
    /no APPDATA value is known/,
  )
})

test('a bare or malformed %APPDATA% value is not silently accepted as profile-relative', () => {
  const appData = 'C:\\Users\\pc\\AppData\\Roaming'
  // The bare prefix with nothing after it has no target to name; it falls to
  // the relative rules and is refused there (no anchor, no path).
  assert.throws(
    () => resolveShellEnvWorkspace('%APPDATA%', null, { APPDATA: appData }),
    /no resources directory is known/,
  )
  // A value that merely contains %APPDATA% somewhere in the middle is not the
  // prefix form; it is a relative name, and it resolves to nowhere real — so
  // the resolution is the refusal, at the same layer the relative rules live.
  assert.throws(
    () => resolveShellEnvWorkspace('workspaces\\%APPDATA%', null, { APPDATA: appData }),
    /no resources directory is known/,
  )
})
