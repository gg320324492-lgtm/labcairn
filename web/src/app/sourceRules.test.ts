// @vitest-environment node
import { readFileSync } from 'node:fs'
import { relative } from 'node:path'

import { describe, expect, it } from 'vitest'

import { packageRoot, shippedSourceFiles } from '../test/sourceFiles'

/**
 * Nothing from the model is executed.
 *
 * *"Arbitrary code execution is not a Phase 1 tool"*, and the report renders
 * retrieved text — so the text the report carries is data and must stay
 * data. The ways a browser would stop treating it as data are a small, named
 * list, and this test reads the shipped source and fails if any of them
 * appears.
 *
 * **Why the source and not the bundle.** The bundle would also carry React's
 * own code, and React's code is allowed to do things this list forbids in
 * ours. The source is the part this task wrote, and it is the part the rule
 * is about.
 */

/** The things that would turn text into code. */
const FORBIDDEN: ReadonlyArray<{ readonly name: string; readonly pattern: RegExp }> = [
  { name: 'eval', pattern: /\beval\s*\(/ },
  { name: 'new Function', pattern: /\bnew\s+Function\s*\(/ },
  { name: 'dangerouslySetInnerHTML', pattern: /dangerouslySetInnerHTML/ },
  { name: 'insertAdjacentHTML', pattern: /insertAdjacentHTML/ },
  { name: 'srcdoc', pattern: /\bsrcdoc\b/ },
  { name: 'document.write', pattern: /document\s*\.\s*write\b/ },
  { name: 'a javascript: URL', pattern: /javascript:/i },
]

/** The names of the things a piece of text does. */
function offences(text: string): string[] {
  return FORBIDDEN.filter((rule) => rule.pattern.test(text)).map((rule) => rule.name)
}

describe('the source scanner', () => {
  it('catches every one of them', () => {
    const samples: Record<string, string> = {
      eval: 'const answer = eval("1 + 1")',
      'new Function': 'const make = new Function("return 1")',
      dangerouslySetInnerHTML: '<div dangerouslySetInnerHTML={{ __html: text }} />',
      insertAdjacentHTML: 'node.insertAdjacentHTML("beforeend", text)',
      srcdoc: '<iframe srcdoc="<p>text</p>" title="x" />',
      'document.write': 'document.write(text)',
      'a javascript: URL': 'const url = "javascript:alert(1)"',
    }

    for (const rule of FORBIDDEN) {
      expect(offences(samples[rule.name] ?? '')).toContain(rule.name)
    }
  })

  it('finds nothing in text that does none of them', () => {
    expect(offences('<p>{text}</p>')).toEqual([])
  })
})

describe('the shipped source', () => {
  it('executes nothing it was given', () => {
    const offenders: string[] = []
    for (const path of shippedSourceFiles()) {
      for (const name of offences(readFileSync(path, 'utf-8'))) {
        offenders.push(`${relative(packageRoot, path)}: ${name}`)
      }
    }

    expect(offenders).toEqual([])
  })

  it('is not empty, so the scan above is not vacuous', () => {
    expect(shippedSourceFiles().length).toBeGreaterThan(5)
  })
})
