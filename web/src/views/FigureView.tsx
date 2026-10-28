/**
 * The figure: a consent question, and the run it authorises.
 *
 * **Why this is two buttons and not one.** A figure's consent binds the
 * material, the operator, its parameters **and the recipe's path**
 * (ADR-0012 constraint 7), so the service will not draw one under an
 * approval it has not been given. The first button asks the question and
 * leaves it pending; the Approval panel is where a human answers it; the
 * second button spends the answer. A single button that asked and granted
 * in one step would be a page minting its own consent.
 *
 * **What this page holds.** The form's text, the id of the question it just
 * asked, and the service's answer to the run. It does not hold the
 * approval's state — the task read is the answer to that — and it does not
 * mark anything granted. After either request it asks the workbench to read
 * the task again, so the screen shows the database rather than this page's
 * memory of the call.
 *
 * **The selection is built here, not typed.** The material's id and hash
 * come from the source the service reports, and the columns and rows come
 * from the fields above; the operator's own parameters are the one thing
 * typed as JSON, because they belong to the operator and this page must not
 * pretend to know its argument model. The same object is sent in the
 * approval's arguments and in the run, which is what makes the digest the
 * run recomputes the digest the approval signed.
 */

import { useId, useState } from 'react'
import type { JSX } from 'react'

import { api, describeError } from '../api/client'
import type { ApprovalRequested, FigureRun, MissingPolicy, SourceView } from '../api/generated'
import {
  ANALYSIS_RUN_PATH,
  APPROVAL_REQUEST_PATH,
  analysisApprovalBody,
  analysisBody,
} from '../api/paths'
import type { ApiRead } from '../app/useWorkbench'
import { Panel } from './Panel'

/** How long the question stays answerable. */
const APPROVAL_WINDOW_MINUTES = 10

interface FigureViewProps {
  /** The material this task is bound to, as the service reports it. */
  readonly sources: ApiRead<SourceView[]>
  /** Ask the workbench to read the task again after a request lands. */
  readonly onChanged: () => void
}

interface FigureForm {
  readonly rootId: string
  readonly sourceId: string
  readonly columns: string
  readonly start: string
  readonly end: string
  readonly missing: MissingPolicy
  readonly operatorId: string
  readonly recipe: string
  readonly parameters: string
}

const INITIAL_FORM: FigureForm = {
  rootId: 'source:0',
  sourceId: '',
  columns: 'group, value',
  start: '2',
  end: '17',
  missing: 'exclude',
  operatorId: 'labcairn.analysis.grouped_aggregate',
  recipe: 'recipe.json',
  parameters: '{"aggregate": "labcairn.analysis.mean@1.0.0", "by": "group", "of": "value"}',
}

interface ActionState {
  /** Which request is in flight, when one is. */
  readonly busy: 'ask' | 'draw' | null
  /** Why the last request was refused, when it was. */
  readonly refusal: string | null
  /** The question the last ask wrote down, so the run can name it. */
  readonly asked: string | null
  /** The service's answer to the last run. */
  readonly drawn: FigureRun | null
}

const IDLE: ActionState = { busy: null, refusal: null, asked: null, drawn: null }

/** When the question this page asks stops being answerable. */
function approvalExpiry(): string {
  return new Date(Date.now() + APPROVAL_WINDOW_MINUTES * 60_000).toISOString()
}

/** The operator's own parameters, or the reason this form cannot state them. */
function parametersOf(form: FigureForm, source: SourceView): Record<string, unknown> | string {
  let extra: unknown
  try {
    extra = JSON.parse(form.parameters)
  } catch (error) {
    return `the operator's parameters are not JSON: ${String(error)}`
  }
  if (typeof extra !== 'object' || extra === null || Array.isArray(extra)) {
    return "the operator's parameters must be one JSON object"
  }
  if ('selection' in extra) {
    // The selection is built from the fields above; a second one in the JSON
    // would be a second answer to the same question, and the approval would
    // bind whichever one this page happened to spread last.
    return 'the parameters must not carry a selection: the fields above state it'
  }
  const columns = form.columns
    .split(',')
    .map((column) => column.trim())
    .filter((column) => column !== '')
  if (columns.length === 0) {
    return 'name at least one column'
  }
  const start = Number(form.start)
  const end = Number(form.end)
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < start) {
    return 'the rows must be whole numbers with start at least 1 and end at least start'
  }
  return {
    ...(extra as Record<string, unknown>),
    selection: {
      source_id: source.source.source_id,
      content_sha256: source.source.content_sha256,
      columns,
      rows: { start, end },
      missing: form.missing,
    },
  }
}

export function FigureView({ sources, onChanged }: FigureViewProps): JSX.Element {
  const [form, setForm] = useState<FigureForm>(INITIAL_FORM)
  const [action, setAction] = useState<ActionState>(IDLE)
  const headingId = useId()
  const field = (name: keyof FigureForm): string => `${headingId}-${name}`

  const change = (patch: Partial<FigureForm>): void => {
    setForm({ ...form, ...patch })
  }

  const failure = (error: unknown): void => {
    setAction({ ...IDLE, refusal: describeError(error).message })
  }

  const onAsk = (source: SourceView): void => {
    const parameters = parametersOf(form, source)
    if (typeof parameters === 'string') {
      setAction({ ...IDLE, refusal: parameters })
      return
    }
    setAction({ ...IDLE, busy: 'ask' })
    const expiresAt = approvalExpiry()
    void api
      .post<ApprovalRequested>(
        APPROVAL_REQUEST_PATH,
        analysisApprovalBody({
          rootId: form.rootId,
          expiresAt,
          arguments: {
            path: source.resource_key,
            operatorId: form.operatorId,
            recipe: form.recipe,
            parameters,
          },
        }),
      )
      .then((asked) => {
        setAction({ ...IDLE, asked: asked.approval.approval_id ?? '' })
        onChanged()
      }, failure)
  }

  const onDraw = (source: SourceView): void => {
    if (action.asked === null || action.asked === '') {
      setAction({ ...IDLE, refusal: 'ask for consent first: a figure runs under an approval' })
      return
    }
    const parameters = parametersOf(form, source)
    if (typeof parameters === 'string') {
      setAction({ ...IDLE, refusal: parameters })
      return
    }
    setAction({ ...action, busy: 'draw', refusal: null })
    void api
      .post<FigureRun>(
        ANALYSIS_RUN_PATH,
        analysisBody({
          rootId: form.rootId,
          approvalId: action.asked,
          path: source.resource_key,
          operatorId: form.operatorId,
          recipe: form.recipe,
          parameters,
        }),
      )
      .then((drawn) => {
        setAction({ ...IDLE, drawn })
        onChanged()
      }, failure)
  }

  return (
    <Panel title="Figure" read={sources}>
      {(items) => {
        const source = items.find((item) => item.source.source_id === form.sourceId) ?? null
        return (
          <>
            <p className="panel__note">
              A figure is a consent question and a run: ask, grant it in the Approval panel, then
              draw. The approval covers the material, the operator, its parameters and the
              recipe&rsquo;s path.
            </p>
            {items.length === 0 ? (
              <p className="panel__note">This task is bound to no material.</p>
            ) : (
              <>
                <div className="figure-form">
                  <label htmlFor={field('sourceId')}>
                    Material
                    <select
                      id={field('sourceId')}
                      value={form.sourceId}
                      onChange={(event) => {
                        change({ sourceId: event.target.value })
                      }}
                    >
                      <option value="">Choose a source</option>
                      {items.map((item) => (
                        <option key={item.source.source_id} value={item.source.source_id}>
                          {item.source.display_name} ({item.resource_key})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label htmlFor={field('rootId')}>
                    Source root
                    <input
                      id={field('rootId')}
                      value={form.rootId}
                      onChange={(event) => {
                        change({ rootId: event.target.value })
                      }}
                    />
                  </label>
                  <label htmlFor={field('columns')}>
                    Columns
                    <input
                      id={field('columns')}
                      value={form.columns}
                      onChange={(event) => {
                        change({ columns: event.target.value })
                      }}
                    />
                  </label>
                  <label htmlFor={field('start')}>
                    First row
                    <input
                      id={field('start')}
                      inputMode="numeric"
                      value={form.start}
                      onChange={(event) => {
                        change({ start: event.target.value })
                      }}
                    />
                  </label>
                  <label htmlFor={field('end')}>
                    Last row
                    <input
                      id={field('end')}
                      inputMode="numeric"
                      value={form.end}
                      onChange={(event) => {
                        change({ end: event.target.value })
                      }}
                    />
                  </label>
                  <label htmlFor={field('missing')}>
                    Missing cells
                    <select
                      id={field('missing')}
                      value={form.missing}
                      onChange={(event) => {
                        change({ missing: event.target.value as MissingPolicy })
                      }}
                    >
                      <option value="exclude">exclude</option>
                      <option value="refuse">refuse</option>
                    </select>
                  </label>
                  <label htmlFor={field('operatorId')}>
                    Operator
                    <input
                      id={field('operatorId')}
                      value={form.operatorId}
                      onChange={(event) => {
                        change({ operatorId: event.target.value })
                      }}
                    />
                  </label>
                  <label htmlFor={field('recipe')}>
                    Recipe
                    <input
                      id={field('recipe')}
                      value={form.recipe}
                      onChange={(event) => {
                        change({ recipe: event.target.value })
                      }}
                    />
                  </label>
                  <label htmlFor={field('parameters')}>
                    Operator parameters (JSON, without the selection)
                    <textarea
                      id={field('parameters')}
                      value={form.parameters}
                      onChange={(event) => {
                        change({ parameters: event.target.value })
                      }}
                    />
                  </label>
                </div>
                <p className="panel__actions">
                  <button
                    className="button"
                    type="button"
                    disabled={source === null || action.busy !== null}
                    onClick={() => {
                      if (source !== null) {
                        onAsk(source)
                      }
                    }}
                  >
                    {action.busy === 'ask' ? 'Asking…' : 'Ask for consent'}
                  </button>{' '}
                  <button
                    className="button"
                    type="button"
                    disabled={source === null || action.busy !== null || action.asked === null}
                    onClick={() => {
                      if (source !== null) {
                        onDraw(source)
                      }
                    }}
                  >
                    {action.busy === 'draw' ? 'Drawing…' : 'Draw the figure'}
                  </button>
                </p>
                {action.asked !== null ? (
                  <p className="panel__status" role="status">
                    Approval <code>{action.asked}</code> is pending. Grant it in the Approval panel,
                    then draw.
                  </p>
                ) : null}
              </>
            )}
            {action.refusal !== null ? (
              <p className="panel__error" role="status">
                The service refused that: {action.refusal}
              </p>
            ) : null}
            {action.drawn !== null ? (
              <div className="panel__status" role="status">
                <p>
                  <strong>{action.drawn.result_kind}</strong>{' '}
                  {action.drawn.figure_receipt === null
                    ? '— no figure (the operator\u2019s result is not one)'
                    : `— ${action.drawn.figure_receipt.relative_path}`}
                </p>
                <p className="record__detail">
                  The derivation is recorded in {action.drawn.manifest_receipt.relative_path}.
                </p>
              </div>
            ) : null}
          </>
        )
      }}
    </Panel>
  )
}
