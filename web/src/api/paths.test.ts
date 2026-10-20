// @vitest-environment node
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import viteConfig from '../../vite.config'
import { DEV_API_BASE } from './mount'
import { API_PATHS, APPROVAL_GRANT_PATH, ARTIFACT_CONTENT_PATH } from './paths'

/**
 * The drift check: the paths the workbench asks for are routes the service
 * actually declares.
 *
 * A path the service does not serve is a 404 that looks like an empty
 * workspace, and an empty workspace is exactly what a workbench shows when
 * something is wrong. So the check reads the service's own route table and
 * compares it with the client's, and the two cannot drift apart without a
 * test failing.
 */

/** The repository root, from this file's own location. */
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', '..')

/** The service's route table, as it is written. */
const routesSource = readFileSync(resolve(repoRoot, 'src', 'labcairn', 'api', 'routes.py'), 'utf-8')

/** A route as the service writes it: `@router.get("/artifacts/{artifact_id}")`. */
const ROUTE_PATTERN = /@router\.(get|post)\(\s*"([^"]+)"/g

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

  it('finds the routes in the real service, so the comparison is not vacuous', () => {
    const routes = serviceRoutes(routesSource)

    expect(routes.has('/health')).toBe(true)
    expect(routes.has('/session')).toBe(true)
    expect(routes.has('/task')).toBe(true)
    expect(routes.has('/artifacts/{param}/content')).toBe(true)
    expect(routes.size).toBeGreaterThan(10)
  })
})

describe('the paths the workbench asks for', () => {
  it('are all routes the service declares', () => {
    const routes = serviceRoutes(routesSource)
    const asked = [...Object.values(API_PATHS), ARTIFACT_CONTENT_PATH, APPROVAL_GRANT_PATH].map(
      anonymous,
    )

    const missing = asked.filter((path) => !routes.has(path))
    expect(missing).toEqual([])
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
