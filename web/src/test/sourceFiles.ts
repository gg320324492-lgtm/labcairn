/**
 * The files the workbench ships, and the files that only the tests read.
 *
 * **The two lists are different on purpose.** The test files and the test
 * support are not bundled — nothing in the application imports them — so a
 * URL in one of them is not a URL the browser would ever see, and the check
 * that covers what ships is the one that reads the built bundle.
 */

import { readdirSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

/** The web package's own root. */
export const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')

/** Every file under a directory, recursively. */
export function filesUnder(root: string): string[] {
  const found: string[] = []
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const path = join(root, entry.name)
    if (entry.isDirectory()) {
      found.push(...filesUnder(path))
    } else if (entry.isFile()) {
      found.push(path)
    }
  }
  return found
}

/** The source files the application ships. */
export function shippedSourceFiles(): string[] {
  const root = resolve(packageRoot, 'src')
  return filesUnder(root).filter((path) => {
    const name = relative(root, path).split('\\').join('/')
    return !name.startsWith('test/') && !name.endsWith('.test.ts') && !name.endsWith('.test.tsx')
  })
}
