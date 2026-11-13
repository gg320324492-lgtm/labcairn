/**
 * T05's artifact hash: name the installer's bytes the way the drill record
 * names them.
 *
 * **Why this exists.** The T09 checklist's first row (D01) and the acceptance
 * record's evidence table both rest on the installer's sha256, and the 11-11
 * build report measured it by hand. A hand-measured hash is a number nobody
 * can re-run; this tool is the re-run. It hashes what the build produced —
 * the `Setup …exe`, its block map, and the unpacked `LabCairn.exe` — and
 * prints one JSON object, so a drill record can quote it and a later record
 * can re-measure against it.
 *
 * **What it does not do.** It does not sign (W28), does not move the
 * artifacts, and does not read anything outside the directory it is given.
 * The output directory is the caller's `LABCAIRN_SHELL_DIST_DIR`, which the
 * build keeps outside the tracked tree.
 *
 * Usage: `node shell/scripts/installer-hash.mjs <dist-directory>`
 */

import assert from 'node:assert/strict'
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/** Hash one file's bytes as lowercase hex. */
export function sha256File(filePath) {
  const digest = crypto.createHash('sha256')
  digest.update(fs.readFileSync(filePath))
  return digest.digest('hex')
}

/** Hash every file directly inside a directory, keyed by name. */
export function hashDirectoryFlat(directory) {
  const result = {}
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.isFile()) {
      const filePath = path.join(directory, entry.name)
      result[entry.name] = { bytes: fs.statSync(filePath).size, sha256: sha256File(filePath) }
    }
  }
  return result
}

function main(argv) {
  const distDir = argv[2]
  assert.ok(distDir, 'usage: node shell/scripts/installer-hash.mjs <dist-directory>')
  const resolved = path.resolve(distDir)
  assert.ok(fs.existsSync(resolved), `no such directory: ${resolved}`)

  const artifacts = hashDirectoryFlat(resolved)
  const unpacked = path.join(resolved, 'win-unpacked')
  const payload = fs.existsSync(unpacked) ? hashDirectoryFlat(unpacked) : null

  process.stdout.write(
    `${JSON.stringify({ directory: resolved, artifacts, winUnpacked: payload }, null, 2)}\n`,
  )
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main(process.argv)
}
