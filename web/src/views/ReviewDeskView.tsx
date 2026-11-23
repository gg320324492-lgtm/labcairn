/**
 * The review desk: the three-column surface where a person answers the
 * advisor's opinions against the manuscript.
 *
 * **The three columns are one job, seen from three sides.** The left column
 * is the opinions' navigation; the middle is the manuscript as paragraphs;
 * the right is the opinion on the desk, its suggested rewrite, its ground,
 * and the four verdicts a person may record. What the desk holds is where
 * the reader is — which opinion is up, and which paragraph is under their
 * eye — and not the material itself: the material is the fixture's, and the
 * fixture is the contract's shape.
 *
 * **The two columns meet at the paragraph.** The contract promises that an
 * opinion's `anchor_paragraph` and a manuscript paragraph's `index` are the
 * same 1-based count over the same document order, so the desk joins them by
 * equality and by nothing else. Scrolling the manuscript moves the eye, and
 * the eye's paragraph names the opinion the left column holds; clicking an
 * opinion puts its paragraph at the top of the pane, so the two stay in step
 * from either side.
 *
 * **The verdict is the person's, and it is not the service's yet.** A click
 * records the verdict in the desk's own state and marks it unsynced, because
 * `POST /review/decision` has no route to answer it while the service is
 * being built. **A button that said "saved" would be lying**, so the desk
 * says what is true: recorded here, not yet with the service. When the route
 * lands, the click posts, the service's answer replaces this state, and the
 * unsynced mark goes.
 */

import { useCallback, useMemo, useRef, useState } from 'react'
import type { JSX } from 'react'

import { fixtureManuscript, fixtureOpinions } from './reviewFixture'
import type { ReviewOpinion, ReviewVerdict } from './reviewContract'
import {
  REVIEW_VERDICTS,
  opinionAnchoredAt,
  opinionSummary,
  paragraphInView,
} from './reviewContract'

/** What a verdict click left behind, in the desk's own record. */
interface DeskAction {
  /** The opinion the click was on. */
  readonly feedbackId: string
  /** The verdict the person chose. */
  readonly verdict: ReviewVerdict
  /** Whether the verdict is flagged as waiting on evidence. */
  readonly needsEvidence: boolean
}

/** The labels the four verdicts carry on their buttons, in contract order. */
const VERDICT_LABELS: Readonly<Record<ReviewVerdict, string>> = {
  accepted: 'Accept',
  partly_accepted: 'Partly accept',
  rejected: 'Reject',
  pending: 'Hold as pending',
}

/** The verdicts, in the order the desk offers them. */
const VERDICTS: readonly ReviewVerdict[] = REVIEW_VERDICTS

/** A badge for the decision an opinion already carries, or its placement. */
function OpinionBadge({ opinion }: { readonly opinion: ReviewOpinion }): JSX.Element {
  const decision = opinion.decision
  if (decision !== null) {
    return (
      <span className={`review-desk__flag review-desk__flag--${decision.verdict}`}>
        {decision.verdict}
        {decision.needs_evidence ? ' · needs evidence' : ''}
      </span>
    )
  }
  return (
    <span className="review-desk__flag review-desk__flag--unreviewed">
      {opinion.location_state === 'needs_evidence' ? 'needs evidence' : 'not reviewed'}
    </span>
  )
}

/** One opinion's row in the left column: its number, its summary, its state. */
function OpinionRow({
  opinion,
  ordinal,
  active,
  onSelect,
}: {
  readonly opinion: ReviewOpinion
  readonly ordinal: number
  readonly active: boolean
  readonly onSelect: () => void
}): JSX.Element {
  return (
    <li className="review-desk__opinion">
      <button
        type="button"
        className={`review-desk__opinion-button${active ? ' review-desk__opinion-button--active' : ''}`}
        aria-current={active ? 'true' : undefined}
        onClick={onSelect}
      >
        <span className="review-desk__opinion-number">{ordinal}</span>
        <span className="review-desk__opinion-body">
          <span className="review-desk__opinion-summary">{opinionSummary(opinion)}</span>
          <span className="review-desk__opinion-meta">
            <OpinionBadge opinion={opinion} />
            {opinion.location_state !== 'located' ? (
              <span className="review-desk__flag review-desk__flag--state">
                {opinion.location_state}
              </span>
            ) : null}
            <span className="review-desk__opinion-place">
              {opinion.anchor_paragraph === null ? 'unplaced' : `¶${opinion.anchor_paragraph}`}
            </span>
          </span>
        </span>
      </button>
    </li>
  )
}

/** One manuscript paragraph, marked when it is the one on the desk. */
function ParagraphRow({
  index,
  text,
  active,
  measured,
}: {
  readonly index: number
  readonly text: string
  readonly active: boolean
  readonly measured: (element: HTMLParagraphElement | null) => void
}): JSX.Element {
  return (
    <p
      ref={measured}
      data-paragraph-index={index}
      className={`review-desk__paragraph${active ? ' review-desk__paragraph--active' : ''}`}
    >
      <span className="review-desk__paragraph-number">{index}</span>
      {text}
    </p>
  )
}

/**
 * The right column's paired texts: what the run says, and what it would say.
 *
 * **The two are drawn side by side and never merged.** The old text is the
 * run's own words and the new text is the model's proposal; a reader who saw
 * one blended text could not tell whose words they were reading.
 */
function SuggestionPair({ opinion }: { readonly opinion: ReviewOpinion }): JSX.Element {
  const suggestion = opinion.suggestion
  if (suggestion === null) {
    return (
      <p className="panel__note">
        This opinion carries no suggested rewrite yet. The verdict waits for a suggestion to answer,
        and the desk does not invent one.
      </p>
    )
  }
  return (
    <div className="review-desk__pair" aria-label="Suggested rewrite, current and proposed">
      <div className="review-desk__pair-side">
        <h4 className="review-desk__pair-title">Current text</h4>
        <blockquote className="review-desk__text review-desk__text--old">
          {suggestion.old_text}
        </blockquote>
      </div>
      <div className="review-desk__pair-side">
        <h4 className="review-desk__pair-title">Proposed text</h4>
        <blockquote className="review-desk__text review-desk__text--new">
          {suggestion.new_text}
        </blockquote>
      </div>
    </div>
  )
}

/** Where the desk says an opinion's anchor was found. */
function GroundNote({ opinion }: { readonly opinion: ReviewOpinion }): JSX.Element {
  if (opinion.anchor_status === 'unknown' || opinion.anchor_paragraph === null) {
    return (
      <p className="panel__note">
        This opinion is not placed in this version
        {opinion.anchor_reason === null ? '.' : `: ${opinion.anchor_reason}`}
      </p>
    )
  }
  return (
    <p className="panel__note">
      Anchored to paragraph {opinion.anchor_paragraph}
      {opinion.anchor_text !== null ? ' (see the span shown below)' : ''}.
    </p>
  )
}

/** What the desk is showing, and what it can do. */
export function ReviewDeskView(): JSX.Element {
  const [activeId, setActiveId] = useState<string | null>(
    fixtureOpinions.opinions[0]?.feedback_id ?? null,
  )
  const [actions, setActions] = useState<readonly DeskAction[]>([])
  const paneRef = useRef<HTMLDivElement | null>(null)
  const rowsRef = useRef<Map<number, HTMLParagraphElement>>(new Map())
  const programmaticScroll = useRef(false)

  const active = useMemo(
    () => fixtureOpinions.opinions.find((opinion) => opinion.feedback_id === activeId) ?? null,
    [activeId],
  )

  /** Put the opinion's paragraph at the top of the pane. */
  const scrollToOpinion = useCallback((opinion: ReviewOpinion): void => {
    if (opinion.anchor_paragraph === null) {
      return
    }
    const pane = paneRef.current
    const row = rowsRef.current.get(opinion.anchor_paragraph)
    if (pane === null || row === undefined) {
      return
    }
    // This scroll is the desk's own move, not the reader's eye; the scroll
    // handler lets it pass without re-deriving the active opinion from it.
    programmaticScroll.current = true
    pane.scrollTop = row.offsetTop - pane.offsetTop
    programmaticScroll.current = false
  }, [])

  const onSelect = useCallback(
    (opinion: ReviewOpinion): void => {
      setActiveId(opinion.feedback_id)
      scrollToOpinion(opinion)
    },
    [scrollToOpinion],
  )

  /** The eye's paragraph, read off the pane's own boxes. */
  const onScroll = useCallback((): void => {
    if (programmaticScroll.current) {
      return
    }
    const pane = paneRef.current
    if (pane === null) {
      return
    }
    const paneTop = pane.getBoundingClientRect().top
    const boxes: Array<{ index: number; top: number; bottom: number }> = []
    for (const [index, element] of rowsRef.current) {
      const box = element.getBoundingClientRect()
      boxes.push({ index, top: box.top - paneTop, bottom: box.bottom - paneTop })
    }
    boxes.sort((left, right) => left.index - right.index)
    const seen = paragraphInView(boxes)
    if (seen === null) {
      return
    }
    const anchored = opinionAnchoredAt(fixtureOpinions.opinions, seen)
    if (anchored !== null && anchored.feedback_id !== activeId) {
      setActiveId(anchored.feedback_id)
    }
  }, [activeId])

  /** Record the verdict here, and say that it has not reached the service. */
  const onDecide = useCallback((opinion: ReviewOpinion, verdict: ReviewVerdict): void => {
    setActions((previous) => {
      const held = previous.find((entry) => entry.feedbackId === opinion.feedback_id)
      const next: DeskAction = {
        feedbackId: opinion.feedback_id,
        verdict,
        needsEvidence: held?.needsEvidence ?? false,
      }
      return [...previous.filter((entry) => entry.feedbackId !== opinion.feedback_id), next]
    })
  }, [])

  /** Toggle the evidence flag on the desk's own record of the verdict. */
  const onToggleEvidence = useCallback((opinion: ReviewOpinion): void => {
    setActions((previous) => {
      const held = previous.find((entry) => entry.feedbackId === opinion.feedback_id)
      if (held === undefined) {
        return [
          ...previous,
          { feedbackId: opinion.feedback_id, verdict: 'pending', needsEvidence: true },
        ]
      }
      return [
        ...previous.filter((entry) => entry.feedbackId !== opinion.feedback_id),
        { ...held, needsEvidence: !held.needsEvidence },
      ]
    })
  }, [])

  const measure = useCallback((index: number, element: HTMLParagraphElement | null): void => {
    if (element === null) {
      rowsRef.current.delete(index)
    } else {
      rowsRef.current.set(index, element)
    }
  }, [])

  const deskAction =
    active === null ? undefined : actions.find((entry) => entry.feedbackId === active.feedback_id)
  const activeParagraph =
    active === null || active.anchor_paragraph === null ? null : active.anchor_paragraph

  return (
    <section className="panel review-desk" aria-label="Review desk">
      <h2 className="panel__title">Review desk</h2>
      <p className="panel__note review-desk__fixture-note" role="note">
        Fixture data — the service&rsquo;s <code>/review</code> routes are not up yet, so this desk
        is drawn from <code>src/fixtures/</code>. Verdicts clicked here live on this page only.
      </p>
      <div className="review-desk__columns">
        <nav className="review-desk__column review-desk__column--opinions" aria-label="Opinions">
          <h3 className="review-desk__column-title">Opinions</h3>
          <ul className="review-desk__opinion-list">
            {fixtureOpinions.opinions.map((opinion, position) => (
              <OpinionRow
                key={opinion.feedback_id}
                opinion={opinion}
                ordinal={position + 1}
                active={opinion.feedback_id === activeId}
                onSelect={() => {
                  onSelect(opinion)
                }}
              />
            ))}
          </ul>
        </nav>

        <div
          className="review-desk__column review-desk__column--manuscript"
          aria-label="Manuscript"
          onScroll={onScroll}
          ref={paneRef}
        >
          <h3 className="review-desk__column-title">Manuscript</h3>
          <div className="review-desk__paragraphs">
            {fixtureManuscript.paragraphs.map((paragraph) => (
              <ParagraphRow
                key={paragraph.index}
                index={paragraph.index}
                text={paragraph.text}
                active={paragraph.index === activeParagraph}
                measured={(element) => {
                  measure(paragraph.index, element)
                }}
              />
            ))}
          </div>
        </div>

        <div className="review-desk__column review-desk__column--verdict" aria-label="Verdict">
          <h3 className="review-desk__column-title">Verdict</h3>
          {active === null ? (
            <p className="panel__note">Choose an opinion from the left; the desk has none up.</p>
          ) : (
            <div className="review-desk__verdict">
              <p className="review-desk__comment">
                <span className="review-desk__comment-author">
                  {active.author ?? 'The advisor'}
                </span>
                {active.comment_text}
              </p>
              <SuggestionPair opinion={active} />
              <GroundNote opinion={active} />
              <div className="review-desk__buttons" role="group" aria-label="Record a verdict">
                {VERDICTS.map((verdict) => (
                  <button
                    key={verdict}
                    type="button"
                    className={`button review-desk__button${
                      deskAction?.verdict === verdict ? ' review-desk__button--chosen' : ''
                    }`}
                    onClick={() => {
                      onDecide(active, verdict)
                    }}
                  >
                    {VERDICT_LABELS[verdict]}
                  </button>
                ))}
                <label className="review-desk__evidence">
                  <input
                    type="checkbox"
                    checked={deskAction?.needsEvidence ?? false}
                    onChange={() => {
                      onToggleEvidence(active)
                    }}
                  />
                  needs evidence
                </label>
              </div>
              {deskAction !== undefined ? (
                <p className="review-desk__unsynced" role="status">
                  Recorded here: <strong>{deskAction.verdict}</strong>
                  {deskAction.needsEvidence ? ' · needs evidence' : ''} — not yet with the service.
                </p>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
