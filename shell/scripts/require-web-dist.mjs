#!/usr/bin/env node
/**
 * The packaging guard: no installer is built without the web bundle.
 *
 * **Why this exists.** `electron-builder.yml` copies the web bundle into the
 * packaged app with `extraResources`. When that source directory is absent,
 * electron-builder prints one line -- `file source doesn't exist` -- and
 * **keeps going**. Measured on 2026-11-11: a build with no `web/dist`
 * exited 0 and produced an installer whose `resources/` carried no
 * `web-dist` at all, while the same build with the bundle present exited 0
 * with the three bundle files inside it. An installer without the frontend
 * installs a window that cannot render, and nothing in the build said so.
 *
 * **What it checks.** The bundle directory must exist, must be a directory,
 * and must carry the entry document. An empty directory is as broken as a
 * missing one, and a bundle without `index.html` cannot be loaded.
 *
 * **How it fails.** A non-zero exit with the reason on stderr, so the
 * `beforeBuild` hook stops the packaging run before anything is written.
 *
 * **How it is called.** `electron-builder` runs it as the `beforeBuild`
 * hook; a caller can also pass the bundle directory to check a different
 * one, which is what the witness does.
 */

import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))

/** The bundle the shell packages: the web workspace's build output. */
const WEB_DIST = path.resolve(HERE, '..', '..', 'web', 'dist')

/** The entry document the packaged window loads. */
const ENTRY_DOCUMENT = 'index.html'

/**
 * Why this bundle cannot be packaged, or null when it can.
 *
 * @param {string} directory the bundle directory to inspect
 * @returns {string | null} the reason the bundle is unusable, or null
 */
function bundleProblem(directory) {
  if (!fs.existsSync(directory)) {
    return `the web bundle directory is absent: ${directory}`
  }
  if (!fs.statSync(directory).isDirectory()) {
    return `the web bundle path is not a directory: ${directory}`
  }
  if (!fs.existsSync(path.join(directory, ENTRY_DOCUMENT))) {
    return `the web bundle carries no ${ENTRY_DOCUMENT}: ${directory}`
  }
  return null
}

function main(argv) {
  const directory = argv[0] ? path.resolve(argv[0]) : WEB_DIST
  const problem = bundleProblem(directory)
  if (problem) {
    process.stderr.write(`the packaging guard refuses this build: ${problem}\n`)
    process.stderr.write('build the web bundle first, then package the shell.\n')
    process.exit(1)
  }
  process.stdout.write(`the web bundle is present: ${directory}\n`)
}

main(process.argv.slice(2))
