/**
 * The rehearsal's window-reading support, shared by the two rehearsals.
 *
 * **Why it is shared rather than copied.** `rehearse-loop.mjs` and
 * `rehearse-dev-vite.mjs` both read a real Electron window over Chromium's
 * remote-debugging endpoint, and both assert the same strip. A second copy of
 * the client is a second thing to keep in step, and a rehearsal whose reader
 * drifted would report the shell's behaviour rather than measure it.
 *
 * The reader is deliberately thin — `Runtime.evaluate`, `Target.closeTarget`,
 * and one expression per fact — because the rehearsals are this repository's
 * dev-side evidence, not a browser-driver dependency. Playwright is the
 * project's driver for the product's own browser baseline
 * (`docs/plans/PHASE_3-work-orders.md` §4.4, the owner's decision of
 * 2026-11-08); nothing in the plan's shell steps requires a second driver, and
 * a driver the shell tests do not need is a dependency nobody approved.
 */

import net from 'node:net'

/** Ask the operating system for a free loopback port. */
export function freeLoopbackPort() {
  return new Promise((resolve, reject) => {
    const probe = net.createServer()
    probe.once('error', reject)
    probe.listen(0, '127.0.0.1', () => {
      const port = probe.address().port
      probe.close(() => resolve(port))
    })
  })
}

/** The CDP target list, retried until the window exposes one. */
export async function listTargets(debugPort, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs
  for (;;) {
    try {
      const response = await fetch(`http://127.0.0.1:${debugPort}/json/list`)
      const targets = await response.json()
      const pages = targets.filter((target) => target.type === 'page' && target.webSocketDebuggerUrl)
      if (pages.length > 0) return pages
    } catch {
      // the endpoint is not up yet
    }
    if (Date.now() >= deadline) throw new Error('the shell window never exposed a CDP target')
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
}

/** A minimal Chrome DevTools Protocol client: send, await the reply, evaluate. */
export class Cdp {
  constructor(webSocketUrl) {
    this.socket = new WebSocket(webSocketUrl)
    this.nextId = 1
    this.pending = new Map()
    this.ready = new Promise((resolve, reject) => {
      this.socket.addEventListener('open', () => resolve())
      this.socket.addEventListener('error', (event) => reject(new Error(event.message ?? 'CDP socket error')))
    })
    this.socket.addEventListener('message', (event) => {
      const message = JSON.parse(String(event.data))
      const waiting = this.pending.get(message.id)
      if (waiting !== undefined) {
        this.pending.delete(message.id)
        waiting(message)
      }
    })
  }

  send(method, params = {}) {
    return this.ready.then(
      () =>
        new Promise((resolve, reject) => {
          const id = this.nextId
          this.nextId += 1
          this.pending.set(id, (message) => {
            if (message.error !== undefined) reject(new Error(`${method}: ${message.error.message}`))
            else resolve(message.result)
          })
          this.socket.send(JSON.stringify({ id, method, params }))
        }),
    )
  }

  async evaluate(expression) {
    const result = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (result.exceptionDetails !== undefined) {
      throw new Error(`page evaluation failed: ${JSON.stringify(result.exceptionDetails)}`)
    }
    return result.result.value
  }

  close() {
    try {
      this.socket.close()
    } catch {
      // already closed
    }
  }
}

/**
 * What the shell's status strip and the preload bridge say, read from inside
 * the page.
 *
 * One expression per fact rather than one multi-line object literal: a
 * multi-line expression that fails reports "Unexpected end of input" and says
 * nothing about which part the page disagreed with. That cost a debugging pass
 * here, so the shape is fixed rather than a style choice.
 */
export async function pageState(cdp) {
  const strip = await cdp.evaluate(`(() => {
    const node = document.getElementById('labcairn-shell-status');
    if (node === null) return null;
    const label = node.querySelector('[data-shell-label]');
    const detail = node.querySelector('[data-shell-detail]');
    return {
      status: node.getAttribute('data-shell-status'),
      label: label === null ? null : label.textContent,
      detail: detail === null ? null : detail.textContent
    };
  })()`)
  const bridgeStatus = await cdp.evaluate(
    `(typeof window.labcairnShell === 'object' && window.labcairnShell !== null) ? window.labcairnShell.status() : null`,
  )
  const location = await cdp.evaluate('location.origin')
  return {
    location,
    stripStatus: strip === null ? null : strip.status,
    stripLabel: strip === null ? null : strip.label,
    stripDetail: strip === null ? null : strip.detail,
    bridgeStatus,
  }
}

/** Poll a read until a predicate holds, and report the last state when it does not. */
export async function pollUntil(read, predicate, timeoutMs, description) {
  const deadline = Date.now() + timeoutMs
  let last = null
  for (;;) {
    last = await read()
    if (predicate(last)) return last
    if (Date.now() >= deadline) {
      throw new Error(`${description} never happened; last observed state: ${JSON.stringify(last)}`)
    }
    await new Promise((resolve) => setTimeout(resolve, 400))
  }
}
