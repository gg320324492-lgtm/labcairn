/**
 * The pilot's issue record: what the trial met, and the four states one issue
 * walks.
 *
 * **The list is the service's answer, and the service asks for the project.**
 * `GET /issues` refuses a listing without a `project_id` — an issue is
 * recorded about a project, so a listing without one would be a listing of
 * nothing — so the panel asks for the project first and draws what the
 * service answered for it. The two filters (`status`, `severity`) narrow the
 * answer rather than changing it, and an empty answer is a fact about the
 * project, not a failure.
 *
 * **A record is the trial's own words, kept as they were seen.** The step,
 * the error text, the severity and the type are what the trial named; the
 * duration and the retry count are the two numbers the record carries, and
 * either may be absent — the contract makes them nullable, and the panel says
 * "not recorded" rather than drawing a zero for a number nobody gave.
 *
 * **The states are walked, not set, and the walk is the service's.** A
 * recorded issue is `open`; `open` is confirmed; `confirmed` is fixed —
 * naming the version that fixed it — or wontfix. A closed issue moves
 * nowhere. The panel offers exactly the moves the state machine allows for
 * the status the service answered with, and the service's refusal is what
 * the reader sees when a move is refused: the panel does not keep a second
 * copy of the walk.
 *
 * **A fixed move names the fix version, and the panel asks for it before the
 * move is sent.** The layer refuses a `fixed` move that names no version, so
 * the panel's own refusal says the same thing before anything is sent — and
 * it says that no request was made, which is not the service's answer.
 *
 * **The three kinds of refusal are kept apart**, as the guidance panel keeps
 * them: the panel's own, the service's (the layer's refusal vocabulary), and
 * the schema's (a `422` that carries the schema's lines and no reason). A
 * reader who could not tell them apart would think a request nobody sent had
 * been refused by the service.
 */

import { useId, useState } from 'react'
import type { JSX } from 'react'

import { ApiFailure, ApiRefusal, api } from '../api/client'
import type {
  IssueData,
  IssueRecordBody,
  IssueStatusBody,
  IssueStatusUpdate,
} from '../api/generated'
import { API_PATHS, issueStatusPath, issuesPath } from '../api/paths'
import { Panel, RecordList } from './Panel'
import type { PanelRead } from './usePanelRead'
import { usePanelRead } from './usePanelRead'

/** The severities the service's closed vocabulary accepts, in its own order. */
const SEVERITIES = ['blocker', 'serious', 'minor', 'suggestion'] as const

/** The categories the service's closed vocabulary accepts, in its own order. */
const CATEGORIES = ['function', 'interface', 'performance', 'model', 'documentation'] as const

/**
 * The walk, as the service holds it.
 *
 * **This is the layer's own table, spelled once, here.** The service refuses
 * a move this table does not name, so the buttons the panel draws are the
 * moves that will be accepted — and a move that is refused anyway is refused
 * in the service's own words, which is the answer the reader sees.
 */
const MOVES: Record<string, readonly string[]> = {
  open: ['confirmed'],
  confirmed: ['fixed', 'wontfix'],
  fixed: [],
  wontfix: [],
}

/** What a write met, in the same four shapes the guidance panel draws. */
type Outcome =
  /** The panel refused to send anything. */
  | { readonly kind: 'panel'; readonly message: string }
  /** The service refused the request, in its own vocabulary. */
  | { readonly kind: 'service'; readonly reason: string; readonly message: string }
  /** The schema did not accept the body, in its own vocabulary. */
  | { readonly kind: 'schema'; readonly status: number; readonly lines: readonly string[] }
  /** The request failed for another reason. */
  | { readonly kind: 'failure'; readonly message: string }

/** What the panel is doing, and what the last write met. */
interface ActionState {
  /** The issue or form being written, while the request is in flight. */
  readonly busy: string | null
  /** What the last write met. */
  readonly outcome: Outcome | null
}

const IDLE: ActionState = { busy: null, outcome: null }

/** The label each shape of refusal is drawn with. */
const LABELS: Record<Outcome['kind'], string> = {
  panel: 'This panel did not send that: ',
  service: 'The service refused that: ',
  schema: 'The service did not accept the body: ',
  failure: 'The service did not answer: ',
}

/**
 * The schema's own lines, when the body carried them.
 *
 * The schema answers a body it will not accept with its own vocabulary —
 * where the body was wrong and what it wanted — and the panel shows that
 * rather than translating it into the layer's refusal vocabulary.
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

/** What a failed write met, read from the error's own class. */
function classify(error: unknown): Outcome {
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

/** The outcome, as the reader sees it: the service's words, or the panel's. */
function outcomeText(outcome: Outcome): string {
  if (outcome.kind === 'service') {
    return `${LABELS.service}${outcome.reason} — ${outcome.message}`
  }
  if (outcome.kind === 'schema') {
    const lines = outcome.lines.length === 0 ? '' : ` ${outcome.lines.join('; ')}`
    return `${LABELS.schema}${outcome.status}.${lines}`
  }
  return `${LABELS[outcome.kind]}${outcome.message}`
}

/** The new-issue form's fields, as the panel holds them between keystrokes. */
interface Draft {
  readonly projectId: string
  readonly step: string
  readonly errorText: string
  readonly severity: string
  readonly category: string
  readonly taskId: string
  readonly versionId: string
  readonly feedbackId: string
  readonly durationSeconds: string
  readonly retryCount: string
  readonly reportedBy: string
}

const EMPTY_DRAFT: Draft = {
  projectId: '',
  step: '',
  errorText: '',
  severity: 'minor',
  category: 'function',
  taskId: '',
  versionId: '',
  feedbackId: '',
  durationSeconds: '',
  retryCount: '',
  reportedBy: '',
}

/** One issue, as the service's record carries it. */
function IssueRow({
  issue,
  busy,
  onMove,
  onFixVersion,
  fixVersion,
}: {
  readonly issue: IssueData
  readonly busy: boolean
  readonly onMove: (issue: IssueData, status: string) => void
  readonly onFixVersion: (issueId: string, version: string) => void
  readonly fixVersion: string
}): JSX.Element {
  const moves = MOVES[issue.status] ?? []
  const fixFieldId = `fix-version-${issue.issue_id}`
  return (
    <li className="record record--artefact">
      <span className="record__name">{issue.error_text}</span>
      <span className={`record__flag record__flag--${issue.status}`}>{issue.status}</span>
      <span className="record__detail">issue {issue.issue_id}</span>
      <span className="record__detail">project {issue.project_id}</span>
      <span className="record__detail">
        severity {issue.severity}, type {issue.category}
      </span>
      <span className="record__detail">step {issue.step}</span>
      <span className="record__detail">
        {issue.duration_seconds === null
          ? 'duration not recorded'
          : `duration ${issue.duration_seconds}s`}
        {', '}
        {issue.retry_count === null ? 'retries not recorded' : `${issue.retry_count} retries`}
      </span>
      <span className="record__detail">
        task {issue.task_id ?? '—'}, version {issue.version_id ?? '—'}, feedback{' '}
        {issue.feedback_id ?? '—'}
      </span>
      <span className="record__detail">
        reported by {issue.reported_by} at {issue.reported_at}
      </span>
      {issue.fix_version !== null ? (
        <span className="record__detail">fixed in {issue.fix_version}</span>
      ) : null}
      {issue.regression_note !== null ? (
        <span className="record__detail">regression note {issue.regression_note}</span>
      ) : null}
      {moves.length > 0 ? (
        <p className="panel__actions">
          {moves.map((status) =>
            status === 'fixed' ? (
              <span key={status}>
                <label htmlFor={fixFieldId}>Fixed in version </label>
                <input
                  id={fixFieldId}
                  value={fixVersion}
                  onChange={(event) => {
                    onFixVersion(issue.issue_id, event.target.value)
                  }}
                />{' '}
                <button
                  className="button"
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    onMove(issue, status)
                  }}
                >
                  Mark fixed
                </button>{' '}
              </span>
            ) : (
              <button
                key={status}
                className="button"
                type="button"
                disabled={busy}
                onClick={() => {
                  onMove(issue, status)
                }}
              >
                Mark {status}
              </button>
            ),
          )}
        </p>
      ) : (
        <span className="record__detail">this issue is closed; its states are walked, not set</span>
      )}
    </li>
  )
}

export function IssuesView({ cycle, onChanged }: IssuesViewProps): JSX.Element {
  const [listProject, setListProject] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [severityFilter, setSeverityFilter] = useState('')
  const [question, setQuestion] = useState<string | null>(null)
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT)
  const [fixVersions, setFixVersions] = useState<Record<string, string>>({})
  const [action, setAction] = useState<ActionState>(IDLE)
  const headingId = useId()
  const field = (name: string): string => `${headingId}-${name}`

  const askedProject = question ?? ''
  const issues = usePanelRead<IssueData[]>(
    askedProject === '' ? null : issuesPath(askedProject, statusFilter, severityFilter),
    cycle,
  )

  const list = (): void => {
    const project = listProject.trim()
    if (project === '') {
      setAction({
        busy: null,
        outcome: { kind: 'panel', message: 'name the project whose issues to list.' },
      })
      return
    }
    setAction(IDLE)
    setQuestion(project)
  }

  const change = (part: Partial<Draft>): void => {
    setDraft((current) => ({ ...current, ...part }))
  }

  const record = (): void => {
    // **The panel's own refusals, and they are the panel's.** Nothing is
    // sent: a request the panel knows is unusable would only ask the
    // service to say what the panel already knows.
    const projectId = draft.projectId.trim()
    const step = draft.step.trim()
    const errorText = draft.errorText.trim()
    const reportedBy = draft.reportedBy.trim()
    if (projectId === '') {
      setAction({ busy: null, outcome: { kind: 'panel', message: 'name the project.' } })
      return
    }
    if (step === '') {
      setAction({ busy: null, outcome: { kind: 'panel', message: 'name the step.' } })
      return
    }
    if (errorText === '') {
      setAction({ busy: null, outcome: { kind: 'panel', message: 'say what was seen.' } })
      return
    }
    if (reportedBy === '') {
      setAction({ busy: null, outcome: { kind: 'panel', message: 'name who saw it.' } })
      return
    }
    const retryRaw = draft.retryCount.trim()
    const durationRaw = draft.durationSeconds.trim()
    const body: IssueRecordBody = {
      // The record's id is the caller's to mint: the service takes it in the
      // body, and the panel names one so that a double click is one record.
      issue_id: `issue-${Math.random().toString(36).slice(2, 10)}`,
      project_id: projectId,
      step,
      error_text: errorText,
      severity: draft.severity as IssueRecordBody['severity'],
      category: draft.category as IssueRecordBody['category'],
      reported_by: reportedBy,
      task_id: draft.taskId.trim() === '' ? null : draft.taskId.trim(),
      version_id: draft.versionId.trim() === '' ? null : draft.versionId.trim(),
      feedback_id: draft.feedbackId.trim() === '' ? null : draft.feedbackId.trim(),
      duration_seconds: durationRaw === '' ? null : Number(durationRaw),
      retry_count: retryRaw === '' ? null : Number(retryRaw),
    }
    setAction({ busy: 'record', outcome: null })
    void api.post<IssueData>(API_PATHS.issues, body).then(
      () => {
        // The list is the answer, and the list is read again rather than
        // appended to: the service's record is what the screen shows. The
        // form is cleared, because the record has been made.
        setAction(IDLE)
        setDraft(EMPTY_DRAFT)
        setQuestion(projectId)
        onChanged()
      },
      (error: unknown) => {
        setAction({ busy: null, outcome: classify(error) })
      },
    )
  }

  const move = (issue: IssueData, status: string): void => {
    const fixVersion = (fixVersions[issue.issue_id] ?? '').trim()
    if (status === 'fixed' && fixVersion === '') {
      setAction({
        busy: null,
        outcome: {
          kind: 'panel',
          message: 'a fixed issue names the version that fixed it. No request was sent.',
        },
      })
      return
    }
    const body: IssueStatusBody = {
      project_id: issue.project_id,
      status: status as IssueStatusBody['status'],
      fix_version: status === 'fixed' ? fixVersion : null,
      regression_note: null,
    }
    setAction({ busy: issue.issue_id, outcome: null })
    void api.post<IssueStatusUpdate>(issueStatusPath(issue.issue_id), body).then(
      () => {
        // The listing is read again rather than patched: the walk is the
        // service's, and the service's answer is what the screen shows.
        setAction(IDLE)
        onChanged()
      },
      (error: unknown) => {
        setAction({ busy: null, outcome: classify(error) })
      },
    )
  }

  const setFixVersion = (issueId: string, version: string): void => {
    setFixVersions((current) => ({ ...current, [issueId]: version }))
  }

  const listPanel: PanelRead<IssueData[]> =
    question === null
      ? { kind: 'answered', data: [] }
      : issues.kind === 'idle'
        ? { kind: 'pending' }
        : issues

  return (
    <>
      <Panel title="Issue record" read={{ data: true, error: null }}>
        {() => (
          <>
            <p className="panel__note">
              The pilot&rsquo;s issue record: the problems the trial met, as they were seen. The
              record names the step it happened at, the severity and type the trial tagged it with,
              and the two numbers it measured — either may be absent, and an absent number is not a
              zero.
            </p>
            <div className="figure-form">
              <label htmlFor={field('listProject')}>
                Project id
                <input
                  id={field('listProject')}
                  value={listProject}
                  onChange={(event) => {
                    setListProject(event.target.value)
                  }}
                />
              </label>
              <label htmlFor={field('statusFilter')}>
                Status filter
                <select
                  id={field('statusFilter')}
                  value={statusFilter}
                  onChange={(event) => {
                    setStatusFilter(event.target.value)
                  }}
                >
                  <option value="">any</option>
                  {Object.keys(MOVES).map((status) => (
                    <option key={status} value={status}>
                      {status}
                    </option>
                  ))}
                </select>
              </label>
              <label htmlFor={field('severityFilter')}>
                Severity filter
                <select
                  id={field('severityFilter')}
                  value={severityFilter}
                  onChange={(event) => {
                    setSeverityFilter(event.target.value)
                  }}
                >
                  <option value="">any</option>
                  {SEVERITIES.map((severity) => (
                    <option key={severity} value={severity}>
                      {severity}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="panel__actions">
              <button className="button" type="button" onClick={list}>
                List the issues
              </button>
            </p>
            {action.outcome !== null ? (
              <p className="panel__error" role="status">
                {outcomeText(action.outcome)}
              </p>
            ) : null}
            {question === null ? (
              <p className="panel__status">
                No project has been named, so nothing has been asked. The service lists a
                project&rsquo;s issues, and an issue is recorded about a project.
              </p>
            ) : listPanel.kind === 'pending' ? (
              <p className="panel__pending" role="status">
                Reading…
              </p>
            ) : listPanel.kind === 'failed' ? (
              <p className="panel__error" role="status">
                The service did not answer this: {listPanel.error.message}
              </p>
            ) : listPanel.data.length === 0 ? (
              <p className="panel__status">
                The service lists no issue for project {askedProject}
                {statusFilter !== '' ? ` with status ${statusFilter}` : ''}
                {severityFilter !== '' ? ` and severity ${severityFilter}` : ''}. An empty answer is
                a fact about the project, not a failure.
              </p>
            ) : (
              <RecordList>
                {listPanel.data.map((issue) => (
                  <IssueRow
                    fixVersion={fixVersions[issue.issue_id] ?? ''}
                    key={issue.issue_id}
                    issue={issue}
                    busy={action.busy === issue.issue_id}
                    onMove={move}
                    onFixVersion={setFixVersion}
                  />
                ))}
              </RecordList>
            )}
          </>
        )}
      </Panel>
      <Panel title="Record an issue" read={{ data: true, error: null }}>
        {() => (
          <>
            <p className="panel__note">
              One problem the trial met, recorded as it was seen. A recorded issue is
              &ldquo;open&rdquo;; the states after that are the listing&rsquo;s buttons to walk. The
              severity and the type are closed vocabularies, and the service refuses a word outside
              either. What a write met is drawn beside the listing, above.
            </p>
            <div className="figure-form">
              <label htmlFor={field('projectId')}>
                Project the record is about
                <input
                  id={field('projectId')}
                  value={draft.projectId}
                  onChange={(event) => {
                    change({ projectId: event.target.value })
                  }}
                />
              </label>
              <label htmlFor={field('step')}>
                Step
                <input
                  id={field('step')}
                  value={draft.step}
                  onChange={(event) => {
                    change({ step: event.target.value })
                  }}
                />
              </label>
              <label htmlFor={field('errorText')}>
                What was seen
                <input
                  id={field('errorText')}
                  value={draft.errorText}
                  onChange={(event) => {
                    change({ errorText: event.target.value })
                  }}
                />
              </label>
              <label htmlFor={field('severity')}>
                Severity
                <select
                  id={field('severity')}
                  value={draft.severity}
                  onChange={(event) => {
                    change({ severity: event.target.value })
                  }}
                >
                  {SEVERITIES.map((severity) => (
                    <option key={severity} value={severity}>
                      {severity}
                    </option>
                  ))}
                </select>
              </label>
              <label htmlFor={field('category')}>
                Type
                <select
                  id={field('category')}
                  value={draft.category}
                  onChange={(event) => {
                    change({ category: event.target.value })
                  }}
                >
                  {CATEGORIES.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </select>
              </label>
              <label htmlFor={field('taskId')}>
                Task id, when there is one
                <input
                  id={field('taskId')}
                  value={draft.taskId}
                  onChange={(event) => {
                    change({ taskId: event.target.value })
                  }}
                />
              </label>
              <label htmlFor={field('versionId')}>
                Version id, when there is one
                <input
                  id={field('versionId')}
                  value={draft.versionId}
                  onChange={(event) => {
                    change({ versionId: event.target.value })
                  }}
                />
              </label>
              <label htmlFor={field('feedbackId')}>
                Feedback id, when there is one
                <input
                  id={field('feedbackId')}
                  value={draft.feedbackId}
                  onChange={(event) => {
                    change({ feedbackId: event.target.value })
                  }}
                />
              </label>
              <label htmlFor={field('durationSeconds')}>
                Duration in seconds, when measured
                <input
                  id={field('durationSeconds')}
                  value={draft.durationSeconds}
                  onChange={(event) => {
                    change({ durationSeconds: event.target.value })
                  }}
                />
              </label>
              <label htmlFor={field('retryCount')}>
                Retry count, when counted
                <input
                  id={field('retryCount')}
                  value={draft.retryCount}
                  onChange={(event) => {
                    change({ retryCount: event.target.value })
                  }}
                />
              </label>
              <label htmlFor={field('reportedBy')}>
                Who saw it
                <input
                  id={field('reportedBy')}
                  value={draft.reportedBy}
                  onChange={(event) => {
                    change({ reportedBy: event.target.value })
                  }}
                />
              </label>
            </div>
            <p className="panel__actions">
              <button
                className="button"
                type="button"
                disabled={action.busy === 'record'}
                onClick={record}
              >
                {action.busy === 'record' ? 'Recording…' : 'Record the issue'}
              </button>
            </p>
          </>
        )}
      </Panel>
    </>
  )
}

interface IssuesViewProps {
  /**
   * The workbench's cycle.
   *
   * **The panel reads again when the workbench reads again**, so an issue
   * recorded or moved elsewhere is on the screen when the page refreshes
   * rather than only after a reload.
   */
  readonly cycle: number
  /**
   * Ask the workbench to read again after a write lands.
   *
   * **The service's record is the answer, and this page's guess at it is
   * not**: a write changes the listing, so the page reads the task again
   * rather than patching the list here. The cycle turns with that read, and
   * the panel reads its own list again with it.
   */
  readonly onChanged: () => void
}
