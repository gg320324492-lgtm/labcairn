// @vitest-environment node
import { describe, expect, it } from 'vitest'

import { fixtureManuscript, fixtureOpinions } from './reviewFixture'

/**
 * The fixtures are the contract, and they are checked as the contract.
 *
 * **The desk is built against shapes the service will one day answer with**,
 * so a fixture that drifted from `docs/plans/LC-P4-CAP-review-api-contract.md`
 * would teach the desk a shape the service never sent, and the drift would
 * surface as a misread screen instead of a failing test. These checks hold
 * the fixture to the contract's own words: the discriminants carry the
 * contract's values, the 1-based counts start at one, and the ordered lists
 * keep the order the contract promises.
 */

describe('the review fixtures', () => {
  it('carry the identifiers the contract names', () => {
    expect(fixtureOpinions.project_id).toBe(fixtureManuscript.project_id)
    expect(fixtureOpinions.version_id).toBe(fixtureManuscript.version_id)
    expect(fixtureManuscript.sha256).toMatch(/^[0-9a-f]{64}$/)
  })

  it('use only the discriminant values the contract names', () => {
    const anchorStatuses = new Set(['resolved', 'unknown', 'position'])
    const locationStates = new Set(['located', 'needs_evidence', 'uncertain_location'])
    const responseStates = new Set(['addressed', 'partially_addressed', 'not_addressed', 'pending'])
    const verdicts = new Set(['accepted', 'partly_accepted', 'rejected', 'pending'])

    for (const opinion of fixtureOpinions.opinions) {
      expect(anchorStatuses.has(opinion.anchor_status)).toBe(true)
      expect(locationStates.has(opinion.location_state)).toBe(true)
      for (const state of opinion.response_states) {
        expect(responseStates.has(state)).toBe(true)
      }
      if (opinion.decision !== null) {
        expect(verdicts.has(opinion.decision.verdict)).toBe(true)
        expect(typeof opinion.decision.operator).toBe('string')
        expect(typeof opinion.decision.needs_evidence).toBe('boolean')
      }
    }
  })

  it('keep the anchors 1-based and inside the manuscript they name', () => {
    const indexes = fixtureManuscript.paragraphs.map((paragraph) => paragraph.index)
    expect(indexes).toEqual(indexes.map((_, position) => position + 1))

    for (const opinion of fixtureOpinions.opinions) {
      if (opinion.anchor_paragraph !== null) {
        expect(opinion.anchor_paragraph).toBeGreaterThanOrEqual(1)
        expect(indexes).toContain(opinion.anchor_paragraph)
        expect(opinion.anchor_start).toBeGreaterThanOrEqual(0)
        expect(opinion.anchor_end).toBeGreaterThanOrEqual(opinion.anchor_start)
      } else {
        expect(opinion.anchor_status === 'unknown' || opinion.location_state !== 'located').toBe(
          true,
        )
      }
    }
  })

  it('keep the opinions in document order, as the contract promises', () => {
    const placed = fixtureOpinions.opinions.filter((opinion) => opinion.anchor_paragraph !== null)
    const anchors = placed.map((opinion) => opinion.anchor_paragraph)
    expect([...anchors].sort((left, right) => (left ?? 0) - (right ?? 0))).toEqual(anchors)
  })

  it('write every suggestion against the paragraph it names', () => {
    for (const opinion of fixtureOpinions.opinions) {
      if (opinion.suggestion !== null) {
        expect(opinion.suggestion.part).toBe('word/document.xml')
        expect(opinion.suggestion.paragraph).toBe(opinion.anchor_paragraph)
        expect(opinion.suggestion.author.startsWith('model:')).toBe(true)
      }
    }
  })

  it('carry a decision only where the opinion has been reviewed', () => {
    // The fixture is a working desk: some opinions answered, some not.
    const answered = fixtureOpinions.opinions.filter((opinion) => opinion.decision !== null)
    const open = fixtureOpinions.opinions.filter((opinion) => opinion.decision === null)
    expect(answered.length).toBeGreaterThan(0)
    expect(open.length).toBeGreaterThan(0)
  })
})
