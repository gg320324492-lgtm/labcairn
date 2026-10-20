/**
 * The session token: in memory, and nowhere else.
 *
 * The service mints the token at start-up and keeps it in its own memory and
 * in a file under the workspace. A client presents it in the `Authorization`
 * header and nowhere else — no cookie, no query parameter — because a URL is
 * pasted and a header is not.
 *
 * **Why a module variable and not React state.** React's state is inspectable
 * from outside the app: the React DevTools panel shows a component's state,
 * and a screenshot of that panel is a screenshot of the token. A module
 * variable is not in the tree, not in the DOM and not in any inspector, so
 * the token lives here and the only thing React ever holds is the *path* of
 * the file the service wrote it to.
 *
 * **Why the token is not in `localStorage`.** A browser's storage is
 * readable by any script on the origin and survives the tab. The token is
 * minted per service start, so a stored one is stale anyway; and a stored
 * secret is a secret that a later change to this page could read out of the
 * browser and send somewhere.
 */

/** The token this page holds, or `null` when it holds none. */
let held: string | null = null

/** The token this page holds, or `null`. */
export function sessionToken(): string | null {
  return held
}

/**
 * Hold the token.
 *
 * The value is never returned, never logged and never rendered: it goes from
 * the service's response straight into this variable and from here straight
 * into a request header.
 */
export function holdSessionToken(token: string): void {
  held = token
}

/**
 * Forget the token.
 *
 * Called when the service refuses it — the service may have restarted and
 * minted a new one — so that the next request asks for the new one rather
 * than presenting the old one again.
 */
export function forgetSessionToken(): void {
  held = null
}
