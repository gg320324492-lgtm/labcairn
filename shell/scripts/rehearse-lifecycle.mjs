/**
 * T06's three unwitnessed lifecycle arms (plan AC-2, §4.3), each run against
 * the real shell.
 *
 * Which arms, and why these three. The acceptance record §8 names exactly
 * these as implemented-but-unwitnessed:
 *
 * - **startup refusal** (§4.3 row 3): the service child refuses to start
 *   (an uninitialised workspace); the window must show the diagnostic rather
 *   than a blank page or a foreign page. The witness reads the strip, the
 *   bridge and the page's location from inside the real window over CDP.
 * - **main-process crash** (§4.3 row 2): an uncaught exception reaches
 *   `process.on('uncaughtException')` in the *real* main process — injected
 *   over the main process's own inspector (`--inspect`), not by editing the
 *   shell to throw on a timer — and the child service must not survive it.
 *   The witness asserts the exit, the printed diagnosis, the absent child pid
 *   and the released port.
 * - **second instance** (§4.3 row 6): a second launch of the same shell exits
 *   and starts **no second service**; the first shell and its service stay
 *   running. The single-instance lock is what §4.3 requires, and this is its
 *   first witness.
 *
 * The other three rows of §4.3 already have witnesses, and this file does not
 * duplicate them: the normal-close/no-orphan arm and the crash-after-readiness
 * arm are `rehearse-loop.mjs` acts 1–2, and the foreign-listener occupancy arm
 * is `test/drain-witness.test.mjs`. The graceful-*ask* half of the normal-close
 * row is the owner's recorded measured gap (acceptance record §6.2: Node's
 * `kill` reaches none of a Windows child's handlers) and is deliberately not
 * asserted here.
 *
 * **The focus half of §4.3's second-instance row is not observable through the
 * remote-debugging endpoint** on this Electron (`Browser.getWindowForTarget`
 * answers "wasn't found"), so the witness asserts the lock's observable
 * consequences (the second process exits, starts no service, leaves the first
 * intact) and names the focus half as an unmeasured remainder in the record
 * rather than inferring it.
 *
 * Run one arm: `node scripts/rehearse-lifecycle.mjs --arm crash`. All three:
 * no flag. Scratch and logs live outside the repository.
 */

import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  assertPortFree,
  injectMainCrash,
  killTree,
  makeWorkspace,
  pidIsGone,
  sleep,
  startLiveShell,
  waitForLine,
} from './lib/live-shell-support.mjs'
import { Cdp, listTargets, pageState, pollUntil, freeLoopbackPort } from './lib/rehearsal-support.mjs'
import { assertPaths, shellPaths } from './lib/shell-paths.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ARM = { refusal: true, crash: true, 'second-instance': true }

const argv = process.argv.slice(2)
const wanted = argv[0] === '--arm' ? argv[1] : null
if (wanted !== null && !(wanted in ARM)) {
  process.stderr.write(`unknown arm ${JSON.stringify(wanted)}; expected one of ${Object.keys(ARM).join(', ')}\n`)
  process.exit(2)
}

function log(...parts) {
  process.stdout.write(`${parts.join(' ')}\n`)
}

/** One workspace per arm, fresh: a workspace a previous arm finished with is a different arm's state. */
function workspaceFor(label) {
  const paths = shellPaths({ here: HERE })
  assertPaths(paths)
  return makeWorkspace({ cli: paths.cliExe, productSrc: paths.productSrc, scratchRoot: paths.scratchRoot, label })
}

async function armRefusal() {
  log('=== refusal arm: the service child refuses to start ===')
  const paths = shellPaths({ here: HERE })
  assertPaths(paths)
  // A file where a workspace should be: the CLI's own refusal
  // (`workspace_not_initialised`) is what the shell must surface, not swallow.
  const badWorkspace = path.join(paths.scratchRoot, `not-a-workspace-${Date.now()}.txt`)
  const { writeFile } = await import('node:fs/promises')
  await writeFile(badWorkspace, 'not a workspace\n')

  const shell = await startLiveShell({
    here: HERE,
    label: 'refusal',
    workspace: badWorkspace,
    debugPort: await freeLoopbackPort(),
  })
  try {
    const diagnostic = await waitForLine(shell, /status failed: ([^\n]*)/)
    log(`refusal diagnostic line: ${diagnostic[0].slice(0, 160)}`)
    assert.match(shell.stdout, /workspace_not_initialised/, 'the shell did not surface the CLI\'s refusal reason')

    // The diagnostic page must not be able to talk to the service. `about:blank`
    // serialises its frame origin to `null`, and a sender the shell cannot name
    // is refused rather than guessed at (§5.4 entry 4). This is the observable
    // half of the sender-origin check: with the check removed, the diagnostic
    // page would be granted a probe and this line would not appear.
    const denied = await waitForLine(shell, /refused guard-request origin (\S+)/)
    assert.equal(denied[1], 'null', `the diagnostic page was refused for origin ${denied[1]}; about:blank carries no origin`)
    assert.ok(!/mutation refused: 401 session_required/.test(shell.stdout), 'the diagnostic page was granted a live probe')

    const pages = await listTargets(shell.debugPort)
    assert.equal(pages.length, 1, `the refusal left ${pages.length} page target(s); exactly one diagnostic window is expected`)
    const cdp = new Cdp(pages[0].webSocketDebuggerUrl)
    const state = await pollUntil(
      () => pageState(cdp),
      (seen) => seen.stripStatus === 'failed' && seen.bridgeStatus === 'failed',
      20_000,
      'the diagnostic strip reaching the failed state',
    )
    log(`refusal window state: ${JSON.stringify({ location: state.location, strip: state.stripStatus, bridge: state.bridgeStatus })}`)
    assert.equal(state.location, 'null', 'the refusal window is not on about:blank')
    assert.match(state.stripLabel ?? '', /refused: the service did not start/, `the strip label was ${JSON.stringify(state.stripLabel)}`)
    assert.match(state.stripDetail ?? '', /workspace_not_initialised/, 'the strip did not carry the refusal reason')
    assert.equal(state.bridgeStatus, 'failed', 'the bridge did not report the refusal')
    cdp.close()

    log('refusal arm: a bad workspace produced a visible diagnostic on about:blank, no page loaded')
  } finally {
    killTree(shell.child)
  }
}

async function armCrash() {
  log('=== crash arm: an uncaught exception in the main process ===')
  const workspace = workspaceFor('crash')
  const inspectPort = await freeLoopbackPort()
  const shell = await startLiveShell({
    here: HERE,
    label: 'crash',
    workspace,
    inspectPort,
    debugPort: await freeLoopbackPort(),
  })
  try {
    const originMatch = await waitForLine(shell, /service origin=(\S+)/)
    const servicePid = Number.parseInt((await waitForLine(shell, /child pid=(\d+)/))[1], 10)
    const servicePort = Number(new URL(originMatch[1]).port)
    await waitForLine(shell, /loaded (\S+)/)
    log(`crash arm service: ${originMatch[1]} pid=${servicePid}`)

    await injectMainCrash(inspectPort)
    for (let i = 0; i < 120 && shell.child.exitCode === null; i += 1) await sleep(250)
    assert.notEqual(shell.child.exitCode, null, 'the shell never exited after the injected crash')
    assert.equal(shell.child.exitCode, 1, `the crash path exited ${shell.child.exitCode}, not 1`)
    assert.match(shell.stderr, /uncaught: .*WITNESS_INJECTED_CRASH/, 'the crash was not printed by the shell\'s own handler')
    log(`crash exit: ${shell.child.exitCode} (injected exception printed)`)

    // Give the supervisor's stop a bounded window, then ask the process table.
    for (let i = 0; i < 40 && !pidIsGone(servicePid); i += 1) await sleep(250)
    assert.ok(pidIsGone(servicePid), `the service child pid ${servicePid} outlived the crashed main process`)
    await assertPortFree(servicePort, 'crash arm after the shell exited on the crash')
    log('crash arm: main process died on an uncaught exception; no service orphan, port released')
  } finally {
    killTree(shell.child)
  }
}

async function armSecondInstance() {
  log('=== second-instance arm: a second launch starts no second service ===')
  const workspace = workspaceFor('second-instance')
  const first = await startLiveShell({ here: HERE, label: 'first', workspace, debugPort: await freeLoopbackPort() })
  let second = null
  try {
    const originMatch = await waitForLine(first, /service origin=(\S+)/)
    const firstServicePid = Number.parseInt((await waitForLine(first, /child pid=(\d+)/))[1], 10)
    await waitForLine(first, /loaded (\S+)/)
    log(`first shell service: ${originMatch[1]} pid=${firstServicePid}`)
    await sleep(1000)

    second = await startLiveShell({ here: HERE, label: 'second', workspace, debugPort: await freeLoopbackPort() })
    for (let i = 0; i < 120 && second.child.exitCode === null; i += 1) await sleep(250)
    assert.notEqual(second.child.exitCode, null, 'the second instance never exited — the lock is not doing its job')
    assert.equal(second.child.exitCode, 0, `the second instance exited ${second.child.exitCode}, not 0`)
    assert.ok(!/service origin=/.test(second.stdout), 'the second instance started its own service')
    assert.equal(first.child.exitCode, null, 'the first shell exited when a second instance ran')
    assert.ok(!pidIsGone(firstServicePid), `the first shell's service child ${firstServicePid} died when a second instance ran`)
    log(`second instance: exit ${second.child.exitCode}, started no service; the first shell and its service are alive`)
  } finally {
    if (second !== null) killTree(second.child)
    killTree(first.child)
  }
}

const arms = { refusal: armRefusal, crash: armCrash, 'second-instance': armSecondInstance }
const toRun = wanted === null ? Object.keys(arms) : [wanted]

let failed = 0
for (const name of toRun) {
  try {
    await arms[name]()
  } catch (error) {
    failed += 1
    process.stderr.write(`ARM ${name} FAILED: ${error?.stack ?? error}\n`)
  }
}
if (failed > 0) {
  process.stderr.write(`${failed}/${toRun.length} arm(s) failed\n`)
  process.exit(1)
}
log(`lifecycle witness: ${toRun.length} arm(s) held (${toRun.join(', ')})`)
