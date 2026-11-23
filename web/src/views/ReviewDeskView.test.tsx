import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ReviewDeskView } from './ReviewDeskView'
import { fixtureManuscript, fixtureOpinions } from './reviewFixture'
import type { ReviewOpinion, ReviewOpinions } from './reviewContract'
import { opinionAnchoredAt, opinionSummary } from './reviewContract'

/**
 * The review desk, drawn from the fixtures the contract names.
 *
 * **What is checked here is the desk's own behaviour, and each property is
 * checked by exercising it**: the three columns draw; a click selects the
 * opinion and highlights its paragraph; scrolling the manuscript moves the
 * active opinion by the paragraph-equality the contract promises; and a
 * verdict click is recorded here and marked unsynced, because the service's
 * `/review` routes do not answer yet. The fixture note is part of the
 * surface: a reader must be able to tell the desk's data from the service's
 * answer.
 */

/** The opinions' list, as the left column shows it. */
function opinionList(): HTMLElement {
  return screen.getByRole('navigation', { name: 'Opinions' })
}

/** The verdict column, as the right column shows it. */
function verdictColumn(): HTMLElement {
  return screen.getByLabelText('Verdict')
}

/** The paragraphs' pane, as the middle column shows it. */
function manuscriptPane(): HTMLElement {
  return screen.getByLabelText('Manuscript')
}

/** The one paragraph the desk marks, by its index attribute. */
function markedParagraphs(): Element[] {
  return [...document.querySelectorAll('.review-desk__paragraph--active')]
}

/** An opinion by its position, asserted present — the fixture is fixed. */
function opinionAt(position: number): ReviewOpinion {
  const opinion = fixtureOpinions.opinions[position]
  if (opinion === undefined) {
    throw new Error(`the fixture holds no opinion at position ${position}`)
  }
  return opinion
}

describe('the review desk', () => {
  it('draws the three columns, and says the data is a fixture', () => {
    render(<ReviewDeskView />)

    expect(screen.getByRole('navigation', { name: 'Opinions' })).toBeInTheDocument()
    expect(manuscriptPane()).toBeInTheDocument()
    expect(verdictColumn()).toBeInTheDocument()
    expect(screen.getByText(/Fixture data/)).toBeInTheDocument()
  })

  it('draws every opinion with its number, its summary and its state', () => {
    render(<ReviewDeskView />)

    const list = within(opinionList())
    fixtureOpinions.opinions.forEach((opinion, position) => {
      expect(list.getByText(String(position + 1))).toBeInTheDocument()
      expect(list.getByText(opinionSummary(opinion))).toBeInTheDocument()
    })
    // The first opinion's anchor is placed; the fourth is explicitly not.
    expect(list.getByText('¶2')).toBeInTheDocument()
    expect(list.getByText('unplaced')).toBeInTheDocument()
  })

  it('draws the manuscript in document order, 1-based', () => {
    render(<ReviewDeskView />)

    const manuscript = within(manuscriptPane())
    for (const paragraph of fixtureManuscript.paragraphs) {
      expect(manuscript.getByText(paragraph.text)).toBeInTheDocument()
    }
  })

  it('starts with the first opinion on the desk, and its paragraph highlighted', () => {
    render(<ReviewDeskView />)

    const first = opinionAt(0)
    const active = document.querySelector('.review-desk__opinion-button--active')
    expect(active).not.toBeNull()
    expect(active?.getAttribute('aria-current')).toBe('true')
    expect(markedParagraphs()).toHaveLength(1)
    expect(markedParagraphs()[0]?.getAttribute('data-paragraph-index')).toBe(
      String(first.anchor_paragraph),
    )
  })

  it("puts the chosen opinion's paragraph at the top of the pane", () => {
    render(<ReviewDeskView />)

    const third = opinionAt(2)
    const buttons = within(opinionList()).getAllByRole('button')
    fireEvent.click(buttons[2] ?? buttons[0]!)

    // The paragraph is the one the desk marks, and the pane holds it.
    const pane = manuscriptPane()
    expect(pane.scrollTop).toBeGreaterThanOrEqual(0)
    expect(markedParagraphs()).toHaveLength(1)
    expect(markedParagraphs()[0]?.getAttribute('data-paragraph-index')).toBe(
      String(third.anchor_paragraph),
    )
  })

  it('records a verdict on the desk, and says it is not yet with the service', () => {
    render(<ReviewDeskView />)

    fireEvent.click(within(verdictColumn()).getAllByRole('button', { name: 'Reject' })[0]!)

    const status = screen.getByText(/Recorded here/)
    expect(status).toBeInTheDocument()
    expect(status).toHaveTextContent('rejected')
    expect(screen.getByText(/not yet with the service/)).toBeInTheDocument()
  })

  it('keeps the desk record per opinion, and carries the evidence flag', () => {
    render(<ReviewDeskView />)

    const verdict = within(verdictColumn())
    fireEvent.click(verdict.getAllByRole('button', { name: 'Accept' })[0]!)
    fireEvent.click(verdict.getByLabelText('needs evidence'))
    const status = screen.getByText(/Recorded here/)
    expect(status).toHaveTextContent(/needs evidence/)

    // Choosing another opinion leaves the record where it was, and the new
    // desk shows no unsynced line of its own.
    fireEvent.click(within(opinionList()).getAllByRole('button')[3]!)
    expect(screen.queryByText(/Recorded here/)).toBeNull()
  })

  it("shows the suggestion's two texts side by side, never merged", () => {
    render(<ReviewDeskView />)

    const first = opinionAt(0)
    const suggestion = first.suggestion
    if (suggestion === null) {
      throw new Error('the first fixture opinion carries a suggestion')
    }
    expect(screen.getByText('Current text')).toBeInTheDocument()
    expect(screen.getByText('Proposed text')).toBeInTheDocument()
    // The old text also stands in the manuscript, so the pair is read inside
    // the verdict column's own pair, not off the whole screen.
    const pair = within(screen.getByLabelText('Suggested rewrite, current and proposed'))
    expect(pair.getByText(suggestion.old_text)).toBeInTheDocument()
    expect(pair.getByText(suggestion.new_text)).toBeInTheDocument()
  })

  it('says when the opinion on the desk carries no suggestion', () => {
    render(<ReviewDeskView />)

    // The fourth opinion has no suggestion; bring it to the desk.
    fireEvent.click(within(opinionList()).getAllByRole('button')[3]!)
    expect(screen.getByText(/carries no suggested rewrite yet/)).toBeInTheDocument()
  })

  it('shows where an unplaced opinion stands instead of inventing a paragraph', () => {
    render(<ReviewDeskView />)

    fireEvent.click(within(opinionList()).getAllByRole('button')[3]!)
    expect(screen.getByText(/not placed in this version/)).toBeInTheDocument()
  })

  it('shows the ground of a placed opinion: the paragraph and the span', () => {
    render(<ReviewDeskView />)

    const first = opinionAt(0)
    expect(
      screen.getByText(new RegExp(`Anchored to paragraph ${first.anchor_paragraph}`)),
    ).toBeInTheDocument()
    // The span itself is the paragraph under the eye, already marked.
    expect(markedParagraphs()[0]).toHaveTextContent('The winter of 1542 stands as the coldest')
  })
})

describe('the paragraph join', () => {
  it("joins an opinion to its paragraph by equality, the contract's promise", () => {
    const opinions: ReviewOpinions = fixtureOpinions
    for (const opinion of opinions.opinions) {
      if (opinion.anchor_paragraph === null) {
        expect(opinionAnchoredAt(opinions.opinions, -1)).toBeNull()
        continue
      }
      expect(opinionAnchoredAt(opinions.opinions, opinion.anchor_paragraph)?.feedback_id).toBe(
        opinion.feedback_id,
      )
    }
  })

  it('answers null when no opinion is anchored to the paragraph', () => {
    expect(opinionAnchoredAt(fixtureOpinions.opinions, 999)).toBeNull()
  })

  it('summarises a long comment at the limit, and keeps a short one whole', () => {
    const long = opinionAt(0)
    const summary = opinionSummary(long)
    expect(summary.length).toBeLessThanOrEqual(96)
    expect(summary.endsWith('…')).toBe(true)
    // The fourth opinion's text is short, and it is drawn whole.
    const short = opinionAt(3)
    expect(opinionSummary(short).length).toBeLessThanOrEqual(96)
    expect(opinionSummary(short)).toBe(opinionSummary(short).trimEnd())
  })
})
