// @vitest-environment node
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import viteConfig from '../../vite.config'
import { DEV_API_BASE } from './mount'
import { API_PATHS, APPROVAL_GRANT_PATH, ARTIFACT_CONTENT_PATH, REPORT_RENDER_PATH } from './paths'

/**
 * The drift check: the paths the workbench asks for are routes the service
 * actually declares.
 *
 * A path the service does not serve is a 404 that looks like an empty
 * workspace, and an empty workspace is exactly what a workbench shows when
 * something is wrong. So the check reads the service's own route table and
 * compares it with the client's, and the two cannot drift apart without a
 * test failing.
 *
 * **This is a cross-language check, and it is a text scan.** The service's
 * routes are written in Python and this test is written in TypeScript, so
 * the only thing the two share is the file. The scan is therefore written to
 * fail *loudly* rather than to find fewer routes quietly:
 *
 * * the file's absence raises, with a message that says the check could not
 *   run, rather than leaving an empty set to compare against;
 * * a route written in a shape this scan does not recognise is reported
 *   **missing**, so the comparison below fails and names the path — a
 *   changed decorator style produces a loud false failure, not a silent
 *   pass;
 * * the scanner is checked against routes the workbench **never asks for**,
 *   so a scanner that had somehow learned only the paths in `paths.ts`
 *   cannot pass.
 *
 * The machine-readable alternative is the OpenAPI document the API already
 * serves, and it is the better source: it is generated from the routes
 * rather than read out of them. It is not reachable from this test suite
 * today — the document is built by importing the Python models, and the web
 * CI job installs Node and pnpm and nothing else — so the scan stays, with
 * the controls above.
 */

/** The repository root, from this file's own location. */
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', '..')

/** Where the service's route table is written. */
const routesPath = resolve(repoRoot, 'src', 'labcairn', 'api', 'routes.py')

if (!existsSync(routesPath)) {
  throw new Error(
    `the service's routes are not where this test looks for them (${routesPath}). ` +
      'The path check cannot run, and a check that cannot run is not a check. ' +
      'Point this test at the new file rather than deleting the assertion.',
  )
}

/** The service's route table, as it is written. */
const routesSource = readFileSync(routesPath, 'utf-8')

/**
 * A route as the service writes it: `@router.get("/artifacts/{artifact_id}")`.
 *
 * The method is matched as a word rather than as a list, so that a route
 * added with a verb this file has never heard of is still seen.
 */
const ROUTE_PATTERN = /@router\.([a-z]+)\(\s*"([^"]+)"/g

/** A path with its parameters made anonymous, so two spellings can be compared. */
function anonymous(path: string): string {
  return path.replace(/\{[^}]+\}/g, '{param}')
}

/** The routes the service declares. */
function serviceRoutes(source: string): Set<string> {
  const routes = new Set<string>()
  for (const match of source.matchAll(ROUTE_PATTERN)) {
    routes.add(anonymous(match[2] ?? ''))
  }
  return routes
}

describe('the route scanner', () => {
  it('reads the routes the service declares', () => {
    const routes = serviceRoutes(
      '@router.get("/task", response_model=TaskState)\n' +
        '@router.post("/approvals/{approval_id}/grant", response_model=ApprovalGranted)\n',
    )

    expect([...routes].sort()).toEqual(['/approvals/{param}/grant', '/task'])
  })

  it('reads a verb it has not seen before', () => {
    const routes = serviceRoutes('@router.put("/task/{task_id}", response_model=Task)\n')

    expect([...routes]).toEqual(['/task/{param}'])
  })

  it('finds the routes in the real service, so the comparison is not vacuous', () => {
    const routes = serviceRoutes(routesSource)

    expect(routes.has('/health')).toBe(true)
    expect(routes.has('/session')).toBe(true)
    expect(routes.has('/task')).toBe(true)
    expect(routes.has('/artifacts/{param}/content')).toBe(true)
    // Routes the workbench never asks for. Without these, a scanner that
    // had somehow learned only the paths in `paths.ts` would pass.
    expect(routes.has('/events')).toBe(true)
    expect(routes.has('/stages')).toBe(true)
    expect(routes.has('/report')).toBe(true)
    expect(routes.size).toBeGreaterThan(10)
  })
})

describe('the paths the workbench asks for', () => {
  it('are all routes the service declares', () => {
    const routes = serviceRoutes(routesSource)
    const asked = [
      ...Object.values(API_PATHS),
      ARTIFACT_CONTENT_PATH,
      APPROVAL_GRANT_PATH,
      REPORT_RENDER_PATH,
    ].map(anonymous)

    const missing = asked.filter((path) => !routes.has(path))
    expect(
      missing,
      `the workbench asks for paths the service does not declare: ${missing.join(', ')}. ` +
        'Either the path is wrong, or the route is written in a shape this test ' +
        'does not recognise — which is a loud false failure, and the fix is to ' +
        'widen the scan rather than to delete the assertion.',
    ).toEqual([])
  })
})

describe('the development proxy', () => {
  const proxy = viteConfig.server?.proxy
  const entry = proxy?.[DEV_API_BASE]

  it('is mounted where the application asks', () => {
    expect(entry).toBeDefined()
    expect(typeof entry).toBe('object')
  })

  it("does not rewrite the request's origin", () => {
    const options = entry as {
      changeOrigin?: boolean
      rewriteWsOrigin?: boolean
      headers?: Record<string, string>
    }

    expect(options.changeOrigin).not.toBe(true)
    expect(options.rewriteWsOrigin).not.toBe(true)
    const headerNames = Object.keys(options.headers ?? {}).map((name) => name.toLowerCase())
    expect(headerNames).not.toContain('origin')
  })

  it('points at the loopback address and nowhere else', () => {
    const options = entry as { target?: string }
    expect(options.target).toMatch(/^http:\/\/127\.0\.0\.1:\d+$/)
  })

  it('strips exactly the prefix the application adds', () => {
    const options = entry as { rewrite?: (path: string) => string }
    expect(typeof options.rewrite).toBe('function')
    expect(options.rewrite?.(`${DEV_API_BASE}/task`)).toBe('/task')
    expect(options.rewrite?.('/task')).toBe('/task')
  })
})
