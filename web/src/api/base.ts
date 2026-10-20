/**
 * Where the API is, relative to the page.
 *
 * There are two deployments and one scheme.
 *
 * **In production** the service serves the built workbench from its own root,
 * so the API is at the origin's root and the base is the empty string. The
 * page and the API share one origin, which is the whole reason the service's
 * origin check means what it says: a page on another site cannot be at this
 * origin, so it cannot ask for anything.
 *
 * **In development** the workbench is served by Vite on another port, so the
 * API is reached through Vite's proxy, which is mounted at
 * {@link DEV_API_BASE}. The proxy strips that prefix and leaves everything
 * else alone — including the request's `Origin` header. A proxy that
 * rewrote the origin would make the check vacuous in exactly the path where
 * the check is being relied on.
 *
 * **The base is a path and never a host.** There is no URL in this file that
 * names a server, because a workbench that phoned home would not be
 * local-first, and because the report renders retrieved text: a remote script
 * would be a remote script with the user's material in it. The only absolute
 * URL in the package is the proxy's target, which lives in `vite.config.ts`
 * and names the loopback address.
 */

import { DEV_API_BASE } from './mount'

export { DEV_API_BASE }

/**
 * The path the API is mounted under, for the mode this bundle was built in.
 *
 * `import.meta.env.DEV` is false in a production build, so the built bundle
 * asks for `/task` rather than `/api/task`. The two are the same request:
 * the proxy rewrites the prefix away before the service sees it.
 */
export const API_BASE = import.meta.env.DEV ? DEV_API_BASE : ''

/**
 * The URL of an API path, relative to the page's origin.
 *
 * The result is always a path. It cannot be a URL with a host in it, so the
 * workbench cannot reach anything but the origin it was served from — which
 * is the property {@link assertRelativePath} then checks at the boundary.
 *
 * @param path the API's own path, such as `/task`.
 * @param base the mount point; the one this bundle was built for by default.
 */
export function apiUrl(path: string, base: string = API_BASE): string {
  return `${base}${path}`
}
