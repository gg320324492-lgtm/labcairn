import { afterEach, describe, expect, it } from 'vitest'

import { forgetSessionToken, holdSessionToken, sessionToken } from './session'

/**
 * The token holder.
 *
 * The properties are small and the point of them is that they are
 * structural: the token is in a module variable and nowhere else, so there
 * is no store to inspect and no inspector that can show it.
 */

afterEach(() => {
  forgetSessionToken()
})

describe('the session token', () => {
  it('is held, and forgotten', () => {
    expect(sessionToken()).toBeNull()

    holdSessionToken('a-token')
    expect(sessionToken()).toBe('a-token')

    forgetSessionToken()
    expect(sessionToken()).toBeNull()
  })

  it("is not in the browser's storage", () => {
    holdSessionToken('a-token')

    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    expect(JSON.stringify(localStorage)).not.toContain('a-token')
    expect(JSON.stringify(sessionStorage)).not.toContain('a-token')
  })

  it('is not in the document', () => {
    holdSessionToken('a-token')

    expect(document.documentElement.outerHTML).not.toContain('a-token')
  })
})
