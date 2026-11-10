/** The window factory: builds the shell's one BrowserWindow with the §5 baseline.
 *
 * Lives apart from `main.mjs` so the construction is one named call the
 * witness can read: `createShellWindow` returns the window *and* the
 * `webPreferences` object it was constructed with, and attaches the
 * navigation guards with a refusal log the witness reads back.
 */

import path from 'node:path'
import { BrowserWindow } from 'electron'
import { shellWebPreferences, attachNavigationGuards } from './window-security.mjs'

export function createShellWindow({ allowedOrigins }) {
  const preloadPath = path.join(import.meta.dirname, 'preload.cjs')
  const webPreferences = shellWebPreferences({ preloadPath })
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    show: false,
    title: 'LabCairn',
    webPreferences,
  })
  const refusals = []
  attachNavigationGuards(win.webContents, { allowedOrigins: () => allowedOrigins.current, refusals })
  return { win, webPreferences, refusals }
}
