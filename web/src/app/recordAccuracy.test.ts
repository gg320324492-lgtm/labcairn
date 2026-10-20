// @vitest-environment node
import { readFileSync } from 'node:fs'
import { join, relative } from 'node:path'

import { describe, expect, it } from 'vitest'

import { packageRoot, shippedSourceFiles } from '../test/sourceFiles'

/**
 * The package's own record must not carry a claim that has stopped being
 * true.
 *
 * The placeholder this package used to be is retired, and a retired claim is
 * not the same thing as a claim nobody reads: a file that still says "this
 * package renders no research functionality" says it to whoever opens it,
 * and it says it wrongly. So the wording is watched rather than left to
 * whoever happens to read.
 *
 * **The words are the claim, not the vocabulary.** "placeholder" alone is
 * not in the list, because `App.tsx` uses it in a true historical sentence
 * about what the placeholder was. What is listed is the claim the retired
 * placeholder made.
 */

/** The wording the retired placeholder made. */
const RETIRED_CLAIM = [
  'under-construction',
  'BASELINE_FACTS',
  'baseline-notice',
  'notImplemented',
  'renders no research functionality',
  'no product features',
  'engineering baseline',
  'Phase 1 baseline',
]

/** The files that carry the package's record. */
function recordFiles(): string[] {
  return [...shippedSourceFiles(), join(packageRoot, 'README.md'), join(packageRoot, 'index.html')]
}

describe("the package's own record", () => {
  it('makes no claim that has stopped being true', () => {
    const offenders: string[] = []
    for (const path of recordFiles()) {
      const text = readFileSync(path, 'utf-8')
      for (const claim of RETIRED_CLAIM) {
        if (text.includes(claim)) {
          offenders.push(`${relative(packageRoot, path)}: ${claim}`)
        }
      }
    }

    expect(
      offenders,
      `the package still claims what the retired placeholder claimed:\n  ${offenders.join('\n  ')}\n` +
        'A claim that is no longer true has to go, not merely stop being read.',
    ).toEqual([])
  })

  it('describes what the package is now', () => {
    const readme = readFileSync(join(packageRoot, 'README.md'), 'utf-8')

    expect(readme).toContain('local research workbench')
    expect(readme).toContain('event stream is not read')
  })

  it('is not vacuous: the record files are found and read', () => {
    const files = recordFiles()
    expect(files.length).toBeGreaterThan(5)
    expect(files).toContain(join(packageRoot, 'README.md'))
  })
})

describe('the scanner', () => {
  it('finds a claim when there is one', () => {
    const text = 'Status: engineering baseline, no product features.'
    expect(RETIRED_CLAIM.some((claim) => text.includes(claim))).toBe(true)
  })

  it('finds nothing in the record as it stands', () => {
    const readme = readFileSync(join(packageRoot, 'README.md'), 'utf-8')
    const offenders = RETIRED_CLAIM.filter((claim) => readme.includes(claim))
    expect(offenders).toEqual([])
  })
})
