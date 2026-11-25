/**
 * The review desk: the three-column surface where a person answers the
 * advisor's opinions against the manuscript.
 *
 * **The three columns are one job, seen from three sides.** The left column
 * is the opinions' navigation; the middle is the manuscript as paragraphs;
 * the right is the opinion on the desk, its suggested rewrite, its ground,
 * and the four verdicts a person may record. What the desk holds is where
 * the reader is — which opinion is up, and which paragraph is under their
 * eye — and not the material itself: the material is the service's answer,
 * and it is the contract's shape.
 *
 * **The two columns meet at the paragraph.** The contract promises that an
 * opinion's `anchor_paragraph` and a manuscript paragraph's `index` are the
 * same 1-based count over the same document order, so the desk joins them by
 * equality and by nothing else. Scrolling the manuscript moves the eye, and
 * the eye's paragraph names the opinion the left column holds; clicking an
 * opinion puts its paragraph at the top of the pane, so the two stay in step
 * from either side.
 *
 * **The verdict is the person's, and the service holds it.** A click posts
 * `POST /review/decision` and the service's answer is the record — the desk
 * does not keep its own copy and call it saved. While the round is in
 * flight the buttons stand down, and a refusal is shown as what it is: the
 * service declined, and the desk says so.
 *
 * **The round the desk draws is the one the service names.** The service
 * holds the workspace's rounds, and `GET /review/rounds` says which they
 * are; the desk asks for that first and draws the opinions and the
 * manuscript of the round it was given. The sample fixture stands in when
 * the service does not answer — and the desk says which one it is looking
 * at either way, because a desk that draws a sample round without saying
 * so cannot be believed about the pilot paper.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { JSX } from 'react'

import { ApiRefusal } from '../api/client'
import {
  REVIEW_OPERATOR,
  readManuscript,
  readOpinions,
  recordDecision,
  runSuggestionLoop,
} from './reviewClient'
import type { ReviewData } from './reviewClient'
import { fixtureManuscript, fixtureOpinions } from './reviewFixture'
import type {
  ReviewManuscript,
  ReviewOpinion,
  ReviewOpinions,
  ReviewVerdict,
} from './reviewContract'
import type { ReviewSuggestRun } from '../api/generated'
import {
  REVIEW_VERDICTS,
  opinionAnchoredAt,
  opinionSummary,
  paragraphInView,
} from './reviewContract'
import { FIXTURE_ROUND, readWorkbenchRound } from './rounds'
import type { WorkbenchRound } from './rounds'

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

/** The two answerers the suggestion loop may ask, in the mode's own words. */
type SuggestMode = 'real' | 'substitute'

/**
 * The stop conditions the service names, in the words a reader acts on.
 *
 * **A run that stopped early is not a failure.** The loop stops when its
 * own ceiling fires — requests, tokens, or one opinion failing too many
 * times in a row — and the account says which; the opinions past the stop
 * are `skipped`, not lost, and the desk says so in words.
 */
const STOP_LABELS: Readonly<Record<string, string>> = {
  request_budget: 'request budget reached',
  token_budget: 'token budget reached',
  consecutive_failures: 'an opinion failed too many times in a row',
}

/** A run's own account, drawn as counts and reasons — never request text. */
function RunRecord({ run }: { readonly run: ReviewSuggestRun }): JSX.Element {
  return (
    <dl className="review-desk__run" aria-label="Suggestion run record">
      <div className="review-desk__run-item">
        <dt>Mode</dt>
        <dd>{run.mode}</dd>
      </div>
      <div className="review-desk__run-item">
        <dt>Model</dt>
        <dd>{run.model_id}</dd>
      </div>
      <div className="review-desk__run-item">
        <dt>Requests made</dt>
        <dd>{run.requests_made}</dd>
      </div>
      <div className="review-desk__run-item">
        <dt>Tokens estimated</dt>
        <dd>{run.tokens_estimated}</dd>
      </div>
      <div className="review-desk__run-item">
        <dt>Suggestions recorded</dt>
        <dd>{run.suggestions_recorded}</dd>
      </div>
      <div className="review-desk__run-item">
        <dt>Opinions skipped</dt>
        <dd>{run.opinions_skipped}</dd>
      </div>
      <div className="review-desk__run-item">
        <dt>Stopped by</dt>
        <dd>
          {run.stopped_reason === null
            ? 'nothing — every pending opinion was walked'
            : (STOP_LABELS[run.stopped_reason] ?? run.stopped_reason)}
        </dd>
      </div>
    </dl>
  )
}

/**
 * The suggestion loop's panel: the desk's door to the model.
 *
 * **The substitute is the default, because it costs nothing.** A
 * substitute run sends nothing out of the machine and spends nothing, so
 * the desk starts there; the real model is one switch away and the
 * service's consent layer decides whether the switch may be thrown.
 */
function SuggestionLoopPanel({
  run,
  failure,
  refusedReason,
  busy,
  mode,
  onModeChange,
  onRun,
  onRetry,
  onSwitchToSubstitute,
}: {
  readonly run: ReviewSuggestRun | null
  readonly failure: string | null
  readonly refusedReason: string | null
  readonly busy: boolean
  readonly mode: SuggestMode
  readonly onModeChange: (mode: SuggestMode) => void
  readonly onRun: () => void
  readonly onRetry: () => void
  readonly onSwitchToSubstitute: () => void
}): JSX.Element {
  const noProvider = refusedReason === 'model_suggestion_no_provider'
  return (
    <div className="review-desk__suggest" aria-label="Suggestion loop">
      <h3 className="review-desk__column-title">Suggestion loop</h3>
      <p className="panel__note">
        Ask a model to propose rewrites for this version&rsquo;s pending opinions. The substitute
        answers locally and spends nothing; the real model sends the desensitised span and needs its
        authorisation in place.
      </p>
      <div className="review-desk__suggest-controls">
        <label className="review-desk__suggest-mode">
          <input
            type="radio"
            name="suggestion-mode"
            value="substitute"
            checked={mode === 'substitute'}
            disabled={busy}
            onChange={() => {
              onModeChange('substitute')
            }}
          />
          substitute (local, spends nothing)
        </label>
        <label className="review-desk__suggest-mode">
          <input
            type="radio"
            name="suggestion-mode"
            value="real"
            checked={mode === 'real'}
            disabled={busy}
            onChange={() => {
              onModeChange('real')
            }}
          />
          real model (authorised, spends approvals)
        </label>
        <button type="button" className="button" disabled={busy} onClick={onRun}>
          {busy ? 'Asking…' : 'Run suggestion loop'}
        </button>
      </div>
      {run !== null ? <RunRecord run={run} /> : null}
      {failure !== null ? (
        <div className="review-desk__suggest-failure" role="alert">
          <p className="review-desk__refusal">
            {noProvider ? 'The service refused the real run' : 'The suggestion run failed'}
            {refusedReason !== null ? ` (${refusedReason})` : ''}: {failure}
          </p>
          <div className="review-desk__buttons">
            {!noProvider ? (
              <button type="button" className="button" disabled={busy} onClick={onRetry}>
                Retry
              </button>
            ) : null}
            <button type="button" className="button" disabled={busy} onClick={onSwitchToSubstitute}>
              Switch to substitute
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

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
  if (opinion.location_state === 'uncertain_location') {
    return <span className="review-desk__flag review-desk__flag--unplaced">unplaced</span>
  }
  return <span className="review-desk__flag review-desk__flag--open">open</span>
}

/** One row of the left column: the opinion's name, its state, and its place. */
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

/** The desk's note about where the data it draws came from. */
function DataSourceNote({
  round,
  roundFromService,
  fromService,
}: {
  readonly round: WorkbenchRound
  readonly roundFromService: boolean
  readonly fromService: boolean
}): JSX.Element {
  if (fromService) {
    return (
      <p className="panel__note review-desk__fixture-note" role="note">
        Live data — read from the service&rsquo;s <code>/review</code> routes for{' '}
        <code>
          {round.projectId} / {round.versionId}
        </code>
        .
      </p>
    )
  }
  if (roundFromService) {
    return (
      <p className="panel__note review-desk__fixture-note" role="note">
        Fixture data — the service named the round{' '}
        <code>
          {round.projectId} / {round.versionId}
        </code>
        , but its <code>/review</code> routes did not answer, so this desk is drawn from the sample
        round (
        <code>
          {FIXTURE_ROUND.projectId} / {FIXTURE_ROUND.versionId}
        </code>
        ). Verdicts clicked here live on this page only.
      </p>
    )
  }
  return (
    <p className="panel__note review-desk__fixture-note" role="note">
      Fixture data — the service&rsquo;s <code>/review</code> routes did not answer, so this desk is
      drawn from <code>src/fixtures/</code> for the sample round{' '}
      <code>
        {round.projectId} / {round.versionId}
      </code>
      . Verdicts clicked here live on this page only.
    </p>
  )
}

/** What the desk is showing, and what it can do. */
export function ReviewDeskView(): JSX.Element {
  const [opinions, setOpinions] = useState<ReviewOpinions>(fixtureOpinions)
  const [manuscript, setManuscript] = useState<ReviewManuscript>(fixtureManuscript)
  const [fromService, setFromService] = useState<boolean | null>(null)
  const [round, setRound] = useState<WorkbenchRound>(FIXTURE_ROUND)
  const [roundFromService, setRoundFromService] = useState<boolean | null>(null)
  const [activeId, setActiveId] = useState<string | null>(
    fixtureOpinions.opinions[0]?.feedback_id ?? null,
  )
  const [actions, setActions] = useState<readonly DeskAction[]>([])
  const [posting, setPosting] = useState(false)
  const [refusal, setRefusal] = useState<string | null>(null)
  const [suggestMode, setSuggestMode] = useState<SuggestMode>('substitute')
  const [suggestRun, setSuggestRun] = useState<ReviewSuggestRun | null>(null)
  const [suggestFailure, setSuggestFailure] = useState<string | null>(null)
  const [suggestRefusal, setSuggestRefusal] = useState<string | null>(null)
  const [suggesting, setSuggesting] = useState(false)
  const paneRef = useRef<HTMLDivElement | null>(null)
  const rowsRef = useRef<Map<number, HTMLParagraphElement>>(new Map())
  const programmaticScroll = useRef(false)

  // The round is read first, from the service, and the desk's reads follow
  // it: the opinions and the manuscript belong to a round, so the round has
  // to be known before they are asked for. The sample round stands while
  // the service does not answer, and the note says which one is drawn.
  //
  // The read is not the workbench's cycle because the desk's question
  // carries no parameter the cycle moves: one round, read once, and re-read
  // only when a verdict changes it.
  useEffect(() => {
    let live = true
    const load = async (): Promise<void> => {
      const roundRead = await readWorkbenchRound()
      if (!live) {
        return
      }
      setRound(roundRead.round)
      setRoundFromService(roundRead.fromService)
      const [opinionsRead, manuscriptRead] = await Promise.all([
        readOpinions(roundRead.round.projectId, roundRead.round.versionId),
        readManuscript(roundRead.round.projectId, roundRead.round.versionId),
      ])
      if (!live) {
        return
      }
      setOpinions(opinionsRead.data)
      setManuscript(manuscriptRead.data)
      setFromService(opinionsRead.fromService && manuscriptRead.fromService)
      setActiveId((current) =>
        opinionsRead.data.opinions.some((opinion) => opinion.feedback_id === current)
          ? current
          : (opinionsRead.data.opinions[0]?.feedback_id ?? null),
      )
    }
    void load()
    return () => {
      live = false
    }
  }, [])

  const active = useMemo(
    () => opinions.opinions.find((opinion) => opinion.feedback_id === activeId) ?? null,
    [opinions, activeId],
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
    for (const row of rowsRef.current.values()) {
      const index = Number(row.dataset.paragraphIndex)
      const box = row.getBoundingClientRect()
      boxes.push({ index, top: box.top - paneTop, bottom: box.bottom - paneTop })
    }
    boxes.sort((left, right) => left.top - right.top)
    const seen = paragraphInView(boxes)
    if (seen === null) {
      return
    }
    const anchored = opinionAnchoredAt(opinions.opinions, seen)
    if (anchored !== null && anchored.feedback_id !== activeId) {
      setActiveId(anchored.feedback_id)
    }
  }, [opinions, activeId])

  /**
   * Record the verdict with the service, and take the service's word back.
   *
   * **The service's answer is the record.** The read is asked again after a
   * write — the same rule the workbench's own writes follow — so the desk's
   * next draw is the service's state, not a merge of it. A refusal is shown,
   * and the opinion's stored verdict stands.
   */
  const onDecide = useCallback(
    (opinion: ReviewOpinion, verdict: ReviewVerdict): void => {
      const held = actions.find((entry) => entry.feedbackId === opinion.feedback_id)
      setActions((previous) => {
        const next: DeskAction = {
          feedbackId: opinion.feedback_id,
          verdict,
          needsEvidence: held?.needsEvidence ?? false,
        }
        return [...previous.filter((entry) => entry.feedbackId !== opinion.feedback_id), next]
      })
      setPosting(true)
      setRefusal(null)
      void recordDecision(round.projectId, {
        feedback_id: opinion.feedback_id,
        verdict,
        operator: REVIEW_OPERATOR,
        needs_evidence: held?.needsEvidence ?? false,
      })
        .then(() => readOpinions(round.projectId, round.versionId))
        .then((read: ReviewData<ReviewOpinions>) => {
          setOpinions(read.data)
          setFromService(read.fromService)
        })
        .catch((error: unknown) => {
          setRefusal(error instanceof Error ? error.message : String(error))
        })
        .finally(() => {
          setPosting(false)
        })
    },
    [actions, round],
  )

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

  /**
   * Run the suggestion loop, and draw the run's own account.
   *
   * **The answer is an account, not the suggestions.** The suggestions land
   * in the store under their own route, so the opinions are read again after
   * a run — the same rule the verdict write follows — and the panel draws
   * what the run cost and where it stopped.
   *
   * **A refusal is shown with its reason, and the way out is on the panel.**
   * `model_suggestion_no_provider` means the real model is not wired in
   * here; the desk says so and offers the substitute. A retryable failure
   * keeps the retry on the same mode, with the substitute one switch away.
   */
  const onRunSuggestions = useCallback(
    (mode: SuggestMode): void => {
      setSuggesting(true)
      setSuggestFailure(null)
      setSuggestRefusal(null)
      void runSuggestionLoop({
        project_id: round.projectId,
        version_id: round.versionId,
        mode,
      })
        .then((run: ReviewSuggestRun) => {
          setSuggestRun(run)
          return readOpinions(round.projectId, round.versionId)
        })
        .then((read: ReviewData<ReviewOpinions>) => {
          setOpinions(read.data)
          setFromService(read.fromService)
        })
        .catch((error: unknown) => {
          setSuggestRun(null)
          if (error instanceof ApiRefusal) {
            setSuggestRefusal(error.reason)
            setSuggestFailure(error.message)
          } else {
            setSuggestRefusal(null)
            setSuggestFailure(error instanceof Error ? error.message : String(error))
          }
        })
        .finally(() => {
          setSuggesting(false)
        })
    },
    [round],
  )

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
      <DataSourceNote
        round={round}
        roundFromService={roundFromService === true}
        fromService={fromService === true}
      />
      {refusal !== null ? (
        <p className="review-desk__refusal" role="alert">
          The service refused that verdict: {refusal}
        </p>
      ) : null}
      <div className="review-desk__columns">
        <nav className="review-desk__column review-desk__column--opinions" aria-label="Opinions">
          <h3 className="review-desk__column-title">Opinions</h3>
          <ul className="review-desk__opinion-list">
            {opinions.opinions.map((opinion, position) => (
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
          <SuggestionLoopPanel
            run={suggestRun}
            failure={suggestFailure}
            refusedReason={suggestRefusal}
            busy={suggesting}
            mode={suggestMode}
            onModeChange={setSuggestMode}
            onRun={() => {
              onRunSuggestions(suggestMode)
            }}
            onRetry={() => {
              onRunSuggestions(suggestMode)
            }}
            onSwitchToSubstitute={() => {
              setSuggestMode('substitute')
              onRunSuggestions('substitute')
            }}
          />
        </nav>

        <div
          className="review-desk__column review-desk__column--manuscript"
          aria-label="Manuscript"
          onScroll={onScroll}
          ref={paneRef}
        >
          <h3 className="review-desk__column-title">Manuscript</h3>
          <div className="review-desk__paragraphs">
            {manuscript.paragraphs.map((paragraph) => (
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
                    disabled={posting}
                    className={`button review-desk__button${
                      deskAction?.verdict === verdict ? ' review-desk__button--chosen' : ''
                    }`}
                    onClick={() => {
                      onDecide(active, verdict)
                    }}
                  >
                    {posting && deskAction?.verdict === verdict
                      ? 'Recording…'
                      : VERDICT_LABELS[verdict]}
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
              {deskAction !== undefined && refusal === null ? (
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
