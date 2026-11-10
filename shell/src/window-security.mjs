/**
 * The window's security baseline and its navigation guards — the pure half.
 *
 * Everything here is a *factory of the object the window is constructed
 * with* and a *function that decides about a URL*, so both are testable
 * without a display and readable by a witness without reading a config file
 * (plan §5.1: "a test reads the actual `webPreferences` object the window was
 * constructed with, not a constant declared in a config file").
 *
 * The baseline (`docs/plans/LC-P3-05-shell-implementation-plan.md` §5):
 * `nodeIntegration: false`, `contextIsolation: true`, `sandbox: true` on
 * every window; external navigation and new windows refused unless the URL's
 * origin is the service origin (dev: the Vite origin too); no `file://` and
 * no custom scheme is ever allowed — their `URL.origin` is `"null"`, which is
 * in no allow-list.
 */

/**
 * The webPreferences every shell window is constructed with. The window
 * module passes this object to `new BrowserWindow`; the witness reads this
 * same object back from the construction call.
 */
export function shellWebPreferences({ preloadPath }) {
  return {
    nodeIntegration: false,
    contextIsolation: true,
    sandbox: true,
    webviewTag: false,
    preload: preloadPath,
  }
}

/** The origin a URL string carries, or null when it carries none or is malformed. */
export function originOf(urlString) {
  try {
    return new URL(urlString).origin
  } catch {
    return null
  }
}

/**
 * Whether a URL may be loaded in the shell's window.
 *
 * `file://` and custom schemes fail here by construction: `URL.origin` is
 * `"null"` for them, and the allow-list is a set of `http(s)` origins built
 * from `ServiceStarting`, so a `file://` page is a refusal, not a page.
 */
export function isAllowedUrl(urlString, allowedOrigins) {
  const origin = originOf(urlString)
  if (origin === null || origin === 'null') return false
  return allowedOrigins.has(origin)
}

/**
 * Attach the guards to a webContents: every new window is denied (the
 * workbench opens no popups), and every renderer-initiated navigation to a
 * foreign origin is prevented. Each refusal is recorded in `refusals` so the
 * witness asserts the refusal happened — not merely that nothing bad appeared.
 */
export function attachNavigationGuards(contents, { allowedOrigins, refusals }) {
  contents.setWindowOpenHandler(({ url }) => {
    refusals.push({ kind: 'window-open', url })
    return { action: 'deny' }
  })
  contents.on('will-navigate', (event, url) => {
    if (!isAllowedUrl(url, allowedOrigins())) {
      event.preventDefault()
      refusals.push({ kind: 'will-navigate', url })
    }
  })
  return refusals
}
