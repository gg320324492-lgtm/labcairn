// @vitest-environment node
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { REPORT_FIRST_PASS_NOTICE } from './firstPassNotice'

/**
 * The workbench's notice is the report's notice.
 *
 * The report's voice lives in one place — `labcairn/reports/render/constants.py`
 * — so that the four exports do not phrase the limit four ways. The
 * workbench quotes that sentence rather than writing one of its own, and
 * this test is what keeps the quotation honest: if the renderer is reworded,
 * the workbench's copy is reworded with it, in the same commit, rather than
 * becoming a second spelling that disagrees.
 *
 * **Why the sentence is read out of the Python source rather than imported.**
 * The workbench is TypeScript and the renderer is Python; there is no
 * boundary between them that could carry a string. So the check reads the
 * source of truth and compares the two, which is the one thing that keeps a
 * copy from drifting.
 */

/** The repository root, from this file's own location. */
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', '..')

/** Where the report's own words are written. */
const constantsPath = resolve(repoRoot, 'src', 'labcairn', 'reports', 'render', 'constants.py')

describe('the first-pass notice', () => {
  it('is the sentence the report renderers write', () => {
    const source = readFileSync(constantsPath, 'utf-8')

    expect(source).toContain(REPORT_FIRST_PASS_NOTICE)
  })

  it("is the renderer's own constant, and not a line of prose that happens to match", () => {
    const source = readFileSync(constantsPath, 'utf-8')
    const literal = REPORT_FIRST_PASS_NOTICE.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

    expect(source).toMatch(new RegExp(`FIRST_PASS_NOTICE[^=]*=\\s*\\(\\s*"${literal}"`))
  })

  it('says the report is not journal-ready', () => {
    expect(REPORT_FIRST_PASS_NOTICE).toMatch(/not journal-ready/)
  })
})
