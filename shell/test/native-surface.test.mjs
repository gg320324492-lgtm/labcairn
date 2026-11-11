/**
 * AC-8: no COM / ProgID / UI-automation route to a DOCX host exists in the
 * shell's surface (`docs/plans/PHASE_3-work-orders.md` §0 rule 2, §3.3; plan
 * §5 entry 5 and AC-8).
 *
 * **What is scanned, and why those names.** "The shell's declared native
 * surface" is not a metaphor — it is the enumerable list of what a renderer or
 * a main-process caller can actually ask the shell for, plus the code that
 * answers:
 *
 * - the `contextBridge` names the preload exposes (`labcairnShell`'s keys);
 * - the `webPreferences` object every window is built with (`webviewTag`,
 *   `nodeIntegration` — the two that open a route to a host process);
 * - the main process's child-spawning code (the one process it starts, and
 *   the one command it may start it with);
 * - `electron.shell.openExternal`, the documented way an Electron app hands a
 *   document to whatever the operating system thinks should open it — which is
 *   exactly the WPS/Word route §0 rule 2 forbids;
 * - COM activation (`CreateObject`, `CoCreateInstance`, `GetObject`), ProgID
 *   strings (`Word.Application`, `Kwps.Application`, `wps.application`), WScript
 *   and UI-automation module names, which are how a Node process would reach a
 *   desktop host at all.
 *
 * **A mention is not a call.** The plan and this repository's own prose name
 * these routes in order to forbid them; a scanner that reddened on the *word*
 * would be a witness that punishes documentation. The patterns match
 * invocations — a call, an import, a ProgID string literal, a spawn argument —
 * not sentences. The two controls below prove the distinction cuts both ways:
 * a real call reddens the scan, and prose naming the same route does not.
 */

import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { shellWebPreferences } from '../src/window-security.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SHELL_ROOT = path.resolve(HERE, '..')
const SRC = path.join(SHELL_ROOT, 'src')

/** The DOCX-host activation and automation routes §0 rule 2 puts out of bounds. */
const FORBIDDEN_ROUTES = [
  { name: 'electron shell.openExternal', pattern: /\bshell\.openExternal\s*\(/ },
  { name: 'COM activation', pattern: /\b(?:CreateObject|CoCreateInstance|OLEObjectType|GetObject)\s*\(/ },
  { name: 'ProgID for a DOCX host', pattern: /['"](?:Word|Kwps|wps|KWPS|Excel|Kwps\.ET)\.[A-Za-z]+['"]/ },
  { name: 'ActiveX', pattern: /\bnew\s+ActiveXObject\b/ },
  { name: 'WScript host', pattern: /\bWScript\.(?:CreateObject|GetObject)\b/ },
  { name: 'UI automation', pattern: /\b(?:UIAutomation|pywinauto|comtypes|win32com|System\.Windows\.Automation)\b/ },
  { name: 'native FFI bridge', pattern: /(?:require|import)\s*\(\s*['"](?:ffi|ffi-napi|koffi|ref-napi)['"]\s*\)/ },
  { name: 'a DOCX host executable', pattern: /\b(?:WINWORD|word|wps|et)\.exe\b/i },
]

function sourceFiles(dir) {
  const found = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const where = path.join(dir, entry.name)
    if (entry.isDirectory()) found.push(...sourceFiles(where))
    else if (/\.(mjs|cjs|js|json)$/.test(entry.name)) found.push(where)
  }
  return found
}

/**
 * The violations in a list of `{ file, text }` entries: `[file, route]` pairs.
 *
 * The real assertion passes the files under `src/`; the positive control passes
 * a mutated copy of one of them; the prose control passes a line of prose. All
 * three run through this one function, so the control measures the scan rather
 * than a copy of it.
 */
function findForbiddenRoutes(entries) {
  const violations = []
  for (const { file, text } of entries) {
    for (const { name, pattern } of FORBIDDEN_ROUTES) {
      if (pattern.test(text)) violations.push([file, name])
    }
  }
  return violations
}

function scannedSources() {
  const files = sourceFiles(SRC)
  assert.ok(files.length >= 6, `only ${files.length} file(s) under src/ — the scan is not looking at what it claims`)
  return files.map((file) => ({ file: path.relative(SHELL_ROOT, file), text: fs.readFileSync(file, 'utf8') }))
}

test('the shell declares no route to a COM / ProgID / UI-automation DOCX host', () => {
  const violations = findForbiddenRoutes(scannedSources())
  assert.deepEqual(
    violations,
    [],
    `the shell's surface carries a DOCX-host route: ${violations.map(([f, r]) => `${f}: ${r}`).join('; ')}`,
  )
})

test('the preferences object a shell window is built with opens no host route', () => {
  // §5.1: read back the object the window is *constructed* with. `window.mjs`
  // passes exactly this object to `new BrowserWindow`; it is the same factory,
  // and it is readable without an Electron runtime.
  const webPreferences = shellWebPreferences({ preloadPath: 'shell/src/preload.cjs' })
  assert.equal(webPreferences.nodeIntegration, false, 'nodeIntegration is the documented door to a host process')
  assert.equal(webPreferences.webviewTag, false, '<webview> is a second renderer with its own surface')
  assert.equal(webPreferences.sandbox, true, 'an unsandboxed renderer can reach Node, and Node can reach a child process')
})

test('every child the shell spawns is the service or the recorded group kill', () => {
  const supervisor = fs.readFileSync(path.join(SRC, 'service-supervisor.mjs'), 'utf8')
  // Two spawn call sites exist, and each is a named mechanism rather than an
  // open-ended ability to start a process:
  //   1. `spawnChild`, the service child, on the one resolved command;
  //   2. the Windows forced group termination `taskkill /T /F` (§4.3's row 1),
  //      the backstop the drain witness and the crash arm both read the outcome of.
  // A third call site — a DOCX host executable, a helper, anything else — is a
  // new route into a desktop host, and §0 rule 2 is what says so.
  const callSites = [...supervisor.matchAll(/^ *const \w+ = spawn\(([^)]*)\)/gm)].map((m) => m[1].trim())
  assert.equal(callSites.length, 2, `the supervisor has ${callSites.length} spawn call site(s): ${JSON.stringify(callSites)}`)
  const [serviceSite, killSite] = callSites
  assert.match(serviceSite, /^command,/, `the service spawn does not use the one resolved command: ${serviceSite}`)
  assert.match(killSite, /^'taskkill',/, `the second spawn is not the recorded group kill: ${killSite}`)
  assert.ok(
    !callSites.some((site) => /\b(?:WINWORD|word|wps|et)\.exe\b/i.test(site)),
    'a spawn names a DOCX host executable',
  )
  assert.match(supervisor, /commandOverride \?\? this\.command/, 'the spawn does not resolve its command through the supervisor')
  assert.match(supervisor, /'serve'/, 'the supervisor no longer spawns the service')
  assert.match(supervisor, /'--host',\s*\n?\s*'127\.0\.0\.1'/, 'the spawn no longer pins the loopback bind')
})

test('the preload exposes only the two read-only getters (the enumerable surface)', () => {
  const preload = fs.readFileSync(path.join(SRC, 'preload.cjs'), 'utf8')
  const exposed = preload.match(/exposeInMainWorld\('labcairnShell',\s*\{([\s\S]*?)\n\}\)/)
  assert.ok(exposed !== null, 'the preload no longer exposes a labcairnShell object — the scan shape changed')
  const keys = [...exposed[1].matchAll(/^ {2}([A-Za-z]+):/gm)].map((m) => m[1])
  assert.deepEqual(keys, ['status', 'guard'], `the exposed surface is ${JSON.stringify(keys)}`)
  for (const key of keys) {
    assert.match(exposed[1], new RegExp(`^ {2}${key}: \\(\\) =>`, 'm'), `${key} is not a nullary getter`)
  }
})

test('a real DOCX-host call in the surface reddens the scan (AC-8 positive control)', () => {
  const mutated = `${fs.readFileSync(path.join(SRC, 'window.mjs'), 'utf8')}
export function openADocument(filePath) {
  // A shell that handed a document to the operating system's default handler
  // would reach WPS or Word through the very route §0 rule 2 forbids.
  return require('electron').shell.openExternal(filePath)
}
export const PROGID = 'Word.Application'
`
  const found = findForbiddenRoutes([{ file: 'src/window.mjs (mutated)', text: mutated }]).map(([, route]) => route)
  assert.ok(found.includes('electron shell.openExternal'), 'the scan did not see `shell.openExternal(...)` — it is not watching calls')
  assert.ok(found.includes('ProgID for a DOCX host'), 'the scan did not see a DOCX-host ProgID string — it is not watching ProgIDs')
})

test('a sentence naming a forbidden route does not redden the scan', () => {
  // The plan, this record and the code's own comments name these routes in
  // order to forbid them. The witness reddens on a call, not on a mention.
  const prose = 'The shell has no shell.openExternal on unvalidated URLs, and no Word.Application ProgID.'
  assert.deepEqual(findForbiddenRoutes([{ file: 'prose', text: prose }]), [])
})
