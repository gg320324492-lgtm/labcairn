/**
 * The guidance rules: what the memory holds, and the door that settles one.
 *
 * **The cases come with the rule.** A counterexample is part of the answer
 * and not a footnote beside it, and the layer's read returns both in one go
 * — so this panel draws each rule's counterexamples **inside that rule's own
 * block**, and a rule that has none says so rather than being drawn as
 * though it had.
 *
 * **The verdict is a person's act, and the door is the service's.** A rule
 * distilled from cases is a candidate until a person confirms it, and the
 * panel offers exactly that act: the name of the person whose word it is,
 * the verdict, and the reason a dispute carries. **The panel does not decide
 * which rules may be settled** — the state machine is the memory's, and a
 * panel that hid the action for a rule it thought was settled would be a
 * second spelling of it. The action is offered on every rule, and the
 * service's refusal is what the reader sees.
 *
 * **The three refusals are kept apart, because they are three things.**
 *
 * * **The panel's own.** An empty `user_id`, or a dispute with no reason:
 * the panel refuses before it sends anything, and says in its own words
 * that no request was made. A reader who took that for the service's
 * answer would think the service had refused a request it never saw.
 * * **The route's own.** The service answers `403` with a reason and a
 *   message — `arguments_invalid` for the two the route checks itself, and
 *   the memory's own reasons for the rest. The panel shows that reason and
 *   that message, **as they are**.
 * * **The schema's.** The route's body check answers `422` in the schema's
 *   own vocabulary, which is not the layer's refusal vocabulary: it carries
 *   no reason, and the panel says so rather than inventing one. The client
 *   keeps the body, so the schema's own lines are shown beside the status.
 *
 * **What the panel does not draw.** The rule carries no score, no weight and
 * no owner beyond the two people it names, so the panel draws none; and the
 * fields are named as the contract names them — the memory settles a rule
 * with `confirmed_by` and `confirmed_at` whatever the verdict was, so a
 * dispute records its disputer in the same field, and a panel that renamed
 * them would be a second spelling of the rule.
 */

import { useId, useState } from 'react'
import type { JSX } from 'react'

import { ApiFailure, ApiRefusal, api } from '../api/client'
import type { GuidanceRule, GuidanceRuleVerdictBody } from '../api/generated'
import { API_PATHS, guidanceRuleConfirmPath } from '../api/paths'
import { Panel, RecordList } from './Panel'
import { asApiRead, usePanelRead } from './usePanelRead'

/**
 * What a verdict met.
 *
 * **The kinds are kept apart on purpose.** A panel that drew the panel's own
 * refusal and the service's refusal the same way would be telling a reader
 * that a request nobody sent was refused by the service.
 */
type VerdictOutcome =
  /** The panel refused to send anything. */
  | { readonly kind: 'panel'; readonly message: string }
  /** The service refused the request, in its own vocabulary. */
  | { readonly kind: 'service'; readonly reason: string; readonly message: string }
  /** The schema did not accept the body, in its own vocabulary. */
  | { readonly kind: 'schema'; readonly status: number; readonly lines: readonly string[] }
  /** The request failed for another reason. */
  | { readonly kind: 'failure'; readonly message: string }

/** What the panel is doing, and what the last verdict met. */
interface ActionState {
  /** The rule being settled, while the request is in flight. */
  readonly busy: string | null
  /** What the last verdict met, when it met anything. */
  readonly outcome: VerdictOutcome | null
}

const IDLE: ActionState = { busy: null, outcome: null }

/** The label each shape of refusal is drawn with. */
const LABELS: Record<VerdictOutcome['kind'], string> = {
  panel: 'This panel did not send that: ',
  service: 'The service refused that: ',
  schema: 'The service did not accept the body: ',
  failure: 'The service did not answer: ',
}

/**
 * The schema's own lines, when the body carried them.
 *
 * **The contract's shape, read as it is.** The schema answers a body it will
 * not accept with its own vocabulary — where the body was wrong and what it
 * wanted — and the panel shows that rather than translating it into the
 * layer's refusal vocabulary, which it is not.
 */
function schemaLines(payload: unknown): string[] {
  if (typeof payload !== 'object' || payload === null) {
    return []
  }
  const detail = (payload as { detail?: unknown }).detail
  if (!Array.isArray(detail)) {
    return []
  }
  return detail.map((entry) => {
    if (typeof entry !== 'object' || entry === null) {
      return String(entry)
    }
    const { loc, msg } = entry as { loc?: unknown; msg?: unknown }
    const where = Array.isArray(loc) ? loc.map((part) => String(part)).join('.') : ''
    const what = typeof msg === 'string' ? msg : ''
    return where === '' ? what : `${where}: ${what}`
  })
}

/**
 * What a failed verdict met.
 *
 * **The error classes are read directly, and not through `describeError`.**
 * That helper flattens a failure to a reason and a message, and the reason
 * is exactly what tells the three shapes apart: the layer's refusals carry
 * one, the schema's answer does not, and the panel's own never left the
 * page.
 */
function classify(error: unknown): VerdictOutcome {
  if (error instanceof ApiRefusal) {
    return { kind: 'service', reason: error.reason, message: error.message }
  }
  if (error instanceof ApiFailure) {
    if (error.status === 422) {
      return { kind: 'schema', status: error.status, lines: schemaLines(error.payload) }
    }
    return { kind: 'failure', message: error.message }
  }
  return { kind: 'failure', message: error instanceof Error ? error.message : String(error) }
}

/** The outcome, as the reader sees it: the server's words, or the panel's. */
function outcomeText(outcome: VerdictOutcome): string {
  if (outcome.kind === 'service') {
    return `${LABELS.service}${outcome.reason} — ${outcome.message}`
  }
  if (outcome.kind === 'schema') {
    const lines = outcome.lines.length === 0 ? '' : ` ${outcome.lines.join('; ')}`
    return `${LABELS.schema}${outcome.status}.${lines}`
  }
  return `${LABELS[outcome.kind]}${outcome.message}`
}

/** One counterexample, inside the rule that cites it. */
function Counterexample({
  statement,
  issueKey,
  recordedBy,
  recordedAt,
}: {
  readonly statement: string
  readonly issueKey: string | null
  readonly recordedBy: string
  readonly recordedAt: string
}): JSX.Element {
  return (
    <li className="record">
      <span className="record__name">{statement}</span>
      <span className="record__detail">
        issue {issueKey === null ? 'no chain material names it' : issueKey}
      </span>
      <span className="record__detail">
        recorded by {recordedBy} at {recordedAt}
      </span>
    </li>
  )
}

interface GuidanceViewProps {
  /**
   * The workbench's cycle.
   *
   * **The panel reads again when the workbench reads again**, so a rule
   * settled elsewhere is on the screen when the page refreshes rather than
   * only after a reload.
   */
  readonly cycle: number
  /**
   * Ask the workbench to read again after a verdict lands.
   *
   * **The service's record is the answer, and this page's guess at it is
   * not**: a verdict writes a rule and an event, so the page reads the task
   * again rather than marking the rule settled here. The cycle turns with
   * that read, and the panel reads its own list again with it.
   */
  readonly onChanged: () => void
}

export function GuidanceView({ cycle, onChanged }: GuidanceViewProps): JSX.Element {
  const rules = usePanelRead<GuidanceRule[]>(API_PATHS.guidanceRules, cycle)
  const [userId, setUserId] = useState('')
  const [reason, setReason] = useState('')
  const [action, setAction] = useState<ActionState>(IDLE)
  const headingId = useId()
  const field = (name: string): string => `${headingId}-${name}`

  const settle = (rule: GuidanceRule, verdict: 'confirmed' | 'disputed'): void => {
    // **The panel's own refusals, and they are the panel's.** Nothing is
    // sent: a request the panel knows is unusable would only ask the
    // service to say what the panel already knows.
    const who = userId.trim()
    if (who === '') {
      setAction({
        busy: null,
        outcome: { kind: 'panel', message: 'name the person whose word it is.' },
      })
      return
    }
    const why = reason.trim()
    if (verdict === 'disputed' && why === '') {
      setAction({
        busy: null,
        outcome: { kind: 'panel', message: 'a dispute needs its reason.' },
      })
      return
    }
    const body: GuidanceRuleVerdictBody =
      verdict === 'confirmed' ? { verdict, user_id: who } : { verdict, user_id: who, reason: why }
    setAction({ busy: rule.rule_id, outcome: null })
    void api.post<GuidanceRule>(guidanceRuleConfirmPath(rule.rule_id), body).then(
      () => {
        // The list is the answer, and the list is read again rather than
        // patched: the service's record is what the screen shows. The
        // workbench reads again too, and its cycle turns with it.
        setAction(IDLE)
        onChanged()
      },
      (error: unknown) => {
        setAction({ busy: null, outcome: classify(error) })
      },
    )
  }

  return (
    <Panel title="Guidance" read={asApiRead(rules)}>
      {(data) => (
        <>
          <p className="panel__note">
            The rules the memory holds, each with its state, its scope, its counterexamples, and the
            two people behind it: the one who proposed it and the one who settled it. A rule
            distilled from cases is a candidate until a person confirms it, and the service refuses
            a confirmation the proposer gave themselves.
          </p>
          {action.outcome !== null ? (
            <p className="panel__error" role="status">
              {outcomeText(action.outcome)}
            </p>
          ) : null}
          <div className="figure-form">
            <label htmlFor={field('userId')}>
              Whose word is it
              <input
                id={field('userId')}
                value={userId}
                onChange={(event) => {
                  setUserId(event.target.value)
                }}
              />
            </label>
            <label htmlFor={field('reason')}>
              The reason, for a dispute
              <input
                id={field('reason')}
                value={reason}
                onChange={(event) => {
                  setReason(event.target.value)
                }}
              />
            </label>
          </div>
          {data.length === 0 ? (
            <p className="panel__status">The memory holds no rule.</p>
          ) : (
            <RecordList>
              {data.map((rule) => (
                <li className="record record--artefact" key={rule.rule_id}>
                  <span className="record__name">{rule.statement}</span>
                  <span className={`record__flag record__flag--${rule.state}`}>{rule.state}</span>
                  <span className="record__detail">
                    rule {rule.rule_id} version {rule.version}
                  </span>
                  <span className="record__detail">issue type {rule.issue_type}</span>
                  <span className="record__detail">context {rule.context}</span>
                  <span className="record__detail">scope {rule.scope}</span>
                  <span className="record__detail">example {rule.example}</span>
                  <span className="record__detail">
                    proposed by {rule.proposed_by} at {rule.proposed_at}
                  </span>
                  <span className="record__detail">
                    confirmed by {rule.confirmed_by ?? 'nobody'} at {rule.confirmed_at ?? 'never'}
                  </span>
                  {rule.resolution_reason !== null ? (
                    <span className="record__detail">reason {rule.resolution_reason}</span>
                  ) : null}
                  <span className="record__detail">
                    sources {rule.sources.length === 0 ? 'none' : rule.sources.join(', ')}
                  </span>
                  {rule.counterexamples.length === 0 ? (
                    <span className="record__detail">
                      the memory holds no case against this rule
                    </span>
                  ) : (
                    <RecordList>
                      {rule.counterexamples.map((counterexample) => (
                        <Counterexample
                          issueKey={counterexample.issue_key}
                          key={`${counterexample.recorded_at}|${counterexample.recorded_by}|${counterexample.statement}`}
                          recordedAt={counterexample.recorded_at}
                          recordedBy={counterexample.recorded_by}
                          statement={counterexample.statement}
                        />
                      ))}
                    </RecordList>
                  )}
                  <p className="panel__actions">
                    <button
                      className="button"
                      type="button"
                      disabled={action.busy !== null}
                      onClick={() => {
                        settle(rule, 'confirmed')
                      }}
                    >
                      Confirm
                    </button>{' '}
                    <button
                      className="button"
                      type="button"
                      disabled={action.busy !== null}
                      onClick={() => {
                        settle(rule, 'disputed')
                      }}
                    >
                      Dispute
                    </button>
                  </p>
                </li>
              ))}
            </RecordList>
          )}
        </>
      )}
    </Panel>
  )
}
