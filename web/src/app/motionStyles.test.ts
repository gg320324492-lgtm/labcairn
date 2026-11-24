import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { packageRoot } from '../test/sourceFiles'
import { MOTION_ATTRIBUTE } from './motionState'

/**
 * The two paths to reduced motion, and the stylesheet that states them.
 *
 * **The property.** The system-level path — the `prefers-reduced-motion`
 * media query — and the application-level path — the rule that reads the
 * attribute the workbench writes on the document root — stand down **the same
 * motion**. A selector the media query covers and the application path does
 * not would be motion that one path could turn off and the other could not,
 * and the two would disagree about what "reduced" means. So the selector
 * lists are the same, and the declarations are the same, and this file
 * watches that they stay the same.
 *
 * **Why it reads the stylesheet rather than the screen.** The disagreement
 * this watches is between two rules of one file. A test that rendered the
 * page could not see it: a selector that both paths agree on and a selector
 * that only one path covers look exactly the same on the screen, because the
 * screen has no opinion about which path was meant to cover it. The
 * stylesheet does, and it is where the answer is.
 *
 * **The attribute is the contract between the module and the stylesheet.**
 * The module writes `data-motion` on the document root; the stylesheet keys
 * its application-level rule off it. The name and the value are checked here
 * too, so renaming one without the other is a failing test rather than a
 * rule that quietly stops matching.
 */

/** The stylesheet the workbench ships, without its comments. */
const stylesheet = readFileSync(resolve(packageRoot, 'src', 'index.css'), 'utf8').replace(
  /\/\*[\s\S]*?\*\//g,
  '',
)

/** One rule of the stylesheet: what it selects and what it declares. */
interface Rule {
  /** The selectors the rule matches. */
  readonly selectors: readonly string[]
  /** The declarations the rule makes. */
  readonly declarations: readonly string[]
}

/** Where a block's closing brace is, given where its opening one is. */
function closingBrace(source: string, openBrace: number): number {
  let depth = 0
  for (let index = openBrace; index < source.length; index += 1) {
    if (source[index] === '{') {
      depth += 1
    } else if (source[index] === '}') {
      depth -= 1
      if (depth === 0) {
        return index
      }
    }
  }
  throw new Error(`the block opened at ${openBrace} is never closed`)
}

/** Every rule written at one level of a block of stylesheet. */
function rulesIn(source: string): Rule[] {
  const found: Rule[] = []
  let index = 0
  while (index < source.length) {
    const openBrace = source.indexOf('{', index)
    if (openBrace === -1) {
      break
    }
    const closeBrace = closingBrace(source, openBrace)
    const prelude = source.slice(index, openBrace).trim()
    // An at-rule's block holds rules of its own, so its prelude is not a
    // selector list and its body is not a declaration list.
    if (!prelude.startsWith('@')) {
      found.push({
        selectors: prelude
          .split(',')
          .map((selector) => selector.trim())
          .filter((selector) => selector.length > 0),
        declarations: source
          .slice(openBrace + 1, closeBrace)
          .split(';')
          .map((declaration) => declaration.trim())
          .filter((declaration) => declaration.length > 0),
      })
    }
    index = closeBrace + 1
  }
  return found
}

/** The rules the system-level media query holds. */
function systemRules(): Rule[] {
  const found: Rule[] = []
  let index = 0
  for (;;) {
    const at = stylesheet.indexOf('@media', index)
    if (at === -1) {
      break
    }
    const openBrace = stylesheet.indexOf('{', at)
    const closeBrace = closingBrace(stylesheet, openBrace)
    if (stylesheet.slice(at, openBrace).includes('prefers-reduced-motion')) {
      found.push(...rulesIn(stylesheet.slice(openBrace + 1, closeBrace)))
    }
    index = closeBrace + 1
  }
  return found
}

/** The rule that keys off the application's own attribute. */
function applicationRule(): Rule | undefined {
  return rulesIn(stylesheet).find((rule) =>
    rule.selectors.every((selector) => selector.includes(`[${MOTION_ATTRIBUTE}`)),
  )
}

/**
 * What each path covers, sorted, so the two can be compared.
 *
 * The application path's selectors carry the attribute it keys off; the
 * system path's do not. The attribute is dropped here, because what the two
 * paths must agree about is **the elements they cover**, not the way each
 * path finds them.
 */
function covered(rule: Rule | undefined): string[] {
  return [...(rule?.selectors ?? [])]
    .map((selector) =>
      selector.replace(new RegExp(`^\\[${MOTION_ATTRIBUTE}\\s*=\\s*(['"]?)reduced\\1\\]\\s*`), ''),
    )
    .sort()
}

describe('the two paths to reduced motion', () => {
  it('both exist', () => {
    expect(systemRules().length).toBeGreaterThan(0)
    expect(applicationRule()).toBeDefined()
  })

  it('cover the same selectors', () => {
    expect(covered(applicationRule())).toEqual(covered(systemRules()[0]))
  })

  it('stand the motion down the same way', () => {
    expect(applicationRule()?.declarations).toEqual(systemRules()[0]?.declarations)
  })

  it('key off the attribute the module writes', () => {
    const selector = applicationRule()?.selectors[0] ?? ''
    const match = selector.match(/^\[([a-z-]+)\s*=\s*(['"]?)reduced\2\]/)

    expect(match?.[1]).toBe(MOTION_ATTRIBUTE)
  })
})
