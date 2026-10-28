/**
 * A fake of the local API, at the network boundary.
 *
 * **Why the fake is at this boundary and not inside the components.** A test
 * that hands a component a made-up object is a test of the component's
 * drawing, and it proves nothing about the part that matters: whether the
 * component asks the service the right question and shows what it was told.
 * This fake answers `fetch`, so the component, the client, the paths and the
 * session scheme are all exercised exactly as they are in the browser.
 *
 * **The answers are the contract's shapes.** Every fixture below is built
 * from the generated types, so a change in the API's models breaks this
 * file at compile time rather than at a reader's convenience.
 *
 * **The data can be changed between reads.** That is the point of the fake:
 * a test that changes the service's answer and looks at the screen again is
 * how "the UI holds no state" is checked rather than asserted.
 */

import type {
  AnalysisBody,
  Approval,
  ApprovalBody,
  ApprovalGranted,
  ApprovalRequested,
  ArtifactReceipt,
  ArtifactView,
  FigureRun,
  Health,
  Selection,
  SessionInfo,
  Source,
  SourceView,
  Task,
  TaskPlan,
  TaskState,
  TaskStep,
} from '../api/generated'

/** The token the fake service mints. */
export const FAKE_TOKEN = 'fake-session-token-2f4a9c'

/** Where the fake service says it wrote the token. */
export const FAKE_TOKEN_PATH = 'C:/workspace/.labcairn/session-token'

/** A marker that would be visible if an artefact's bytes were ever read into the page. */
export const ARTEFACT_CONTENT_MARKER = 'ARTEFACT-BYTES-AS-TEXT'

/** One request the fake was asked to make. */
export interface RecordedRequest {
  /** The URL the client asked for. */
  readonly url: string
  /** The method. */
  readonly method: string
  /** The headers the client set. */
  readonly headers: Record<string, string>
  /** The body the client sent, when it sent one. */
  readonly body: string | null
  /**
   * What the client asked the browser to do about credentials.
   *
   * Recorded because the setting is the client's decision and the browser's
   * behaviour is not: a request that says `include` sends whatever cookie
   * the origin happens to hold, and the request itself would not show it.
   */
  readonly credentials: string | null
  /** What the client asked the browser to do about the referrer. */
  readonly referrerPolicy: string | null
}

/** What the fake service knows. Every field can be changed between reads. */
export interface FakeApiState {
  health: Health
  session: SessionInfo
  tasks: Task[]
  task: TaskState
  plan: TaskPlan
  steps: TaskStep[]
  sources: SourceView[]
  artifacts: ArtifactView[]
  /** The artefact bytes the service would serve. */
  artefactContent: string
}

/** The task the fake service is bound to. */
export const TASK_ID = '0193f0a1-0000-7000-8000-000000000001'

/** The pending approval the fake service holds. */
export const APPROVAL_ID = '0193f0a1-0000-7000-8000-0000000000c1'

/** The receipt of a figure: an SVG, which can carry script. */
export function figureReceipt(): ArtifactReceipt {
  return {
    receipt_id: '0193f0a1-0000-7000-8000-0000000000a1',
    task_id: TASK_ID,
    kind: 'figure',
    relative_path: 'figures/landscape.svg',
    content_sha256: 'a'.repeat(64),
    size_bytes: 2048,
    revision: 1,
    produced_by: 'stage',
    producer_id: 'inventory',
    staleness: 'current',
    media_type: 'image/svg+xml',
    created_at: '2026-10-20T09:00:00+00:00',
  }
}

/** The receipt of the report's own HTML form. */
export function reportReceipt(): ArtifactReceipt {
  return {
    receipt_id: '0193f0a1-0000-7000-8000-0000000000a2',
    task_id: TASK_ID,
    kind: 'report',
    relative_path: 'reports/report.html',
    content_sha256: 'b'.repeat(64),
    size_bytes: 4096,
    revision: 1,
    produced_by: 'stage',
    producer_id: 'draft',
    staleness: 'current',
    media_type: 'text/html',
    created_at: '2026-10-20T09:05:00+00:00',
  }
}

/** The state the fake service starts in. */
export function initialState(): FakeApiState {
  const task: Task = {
    task_id: TASK_ID,
    title: 'What the sediment record says about the winter',
    goal: {
      objective: 'Reconstruct the winter temperature from the sediment record.',
      success_criterion: 'Every claim in the report names the record it rests on.',
    },
    bound_source_ids: ['0193f0a1-0000-7000-8000-0000000000b1'],
    revision: 1,
    created_at: '2026-10-20T08:00:00+00:00',
    updated_at: '2026-10-20T09:05:00+00:00',
  }
  const source: Source = {
    source_id: '0193f0a1-0000-7000-8000-0000000000b1',
    kind: 'pdf',
    display_name: 'Sediment core 04.pdf',
    relative_path: 'material/core-04.pdf',
    content_sha256: 'c'.repeat(64),
    size_bytes: 1048576,
    readability: 'readable',
    readability_disclosure: null,
    identifiers: [{ kind: 'doi', value: '10.0000/labcairn.04' }],
    ingested_at: '2026-10-20T08:30:00+00:00',
  }
  const approval: Approval = {
    approval_id: APPROVAL_ID,
    task_id: TASK_ID,
    operation_id: '0193f0a1-0000-7000-8000-0000000000c2',
    capability: 'model.request',
    resource_key: 'material/core-04.pdf',
    args_digest: 'd'.repeat(64),
    state: 'pending',
    expires_at: '2026-10-20T10:00:00+00:00',
  }
  return {
    health: {
      status: 'ok',
      host: '127.0.0.1',
      port: 8000,
      origins: ['http://127.0.0.1:8000'],
      task_id: TASK_ID,
    },
    session: { token: FAKE_TOKEN, path: FAKE_TOKEN_PATH },
    tasks: [task],
    task: {
      task,
      runs: [],
      stages: [],
      artifacts: [figureReceipt(), reportReceipt()],
      approvals: [approval],
      last_event_seq: 12,
    },
    plan: {
      task_id: TASK_ID,
      skill_id: 'research-report',
      skill_digest: 'e'.repeat(64),
      steps: [
        { stage: 'intake', status: 'completed' },
        { stage: 'inventory', status: 'completed' },
        { stage: 'retrieve', status: 'entered' },
        { stage: 'evidence', status: 'pending' },
      ],
    },
    steps: [
      {
        stage: {
          stage_id: '0193f0a1-0000-7000-8000-0000000000d1',
          task_id: TASK_ID,
          run_id: '0193f0a1-0000-7000-8000-0000000000d2',
          name: 'retrieve',
          status: 'entered',
        },
        attempt: 1,
      },
    ],
    sources: [{ source, resource_key: 'core-04.pdf' }],
    artifacts: [
      { receipt: figureReceipt(), resource_key: 'figures/landscape.svg' },
      { receipt: reportReceipt(), resource_key: 'reports/report.html' },
    ],
    artefactContent: `<html><body><p>${ARTEFACT_CONTENT_MARKER}</p></body></html>`,
  }
}

/**
 * The fake service.
 *
 * It answers the routes the workbench uses, records every request, and
 * serves the state it holds — which a test may change between reads.
 */
export class FakeApi {
  /** Everything the fake knows. Change it and the next read sees the change. */
  state: FakeApiState = initialState()

  /** Every request the client has made. */
  readonly requests: RecordedRequest[] = []

  /** How many times the artefact's bytes have been asked for as a value. */
  artefactContentReads = 0

  /** Whether the service refuses a grant, without changing the approval. */
  refuseGrants = false

  /**
   * Whether the service refuses a report render.
   *
   * **This is the normal case, not the unusual one**: no operation writes an
   * evidence record, so a task the workbench is showing usually has nothing a
   * report may carry, and the honest answer is a refusal that writes nothing.
   */
  refuseReport = false

  /** How many report renders the service has been asked for. */
  reportRenders = 0

  /**
   * Whether the service refuses the figure run.
   *
   * A run is refused before anything is written — a consent that does not
   * cover the exact request, a policy that says no, or a material that moved —
   * so the page's only correct response is to show the service's reason.
   */
  refuseAnalysis = false

  /** Whether the operator's result produces no figure, as a scalar's does. */
  figureless = false

  /** How many figure runs the service has been asked for. */
  analysisRuns = 0

  /** How many consent questions the service has been asked to write down. */
  approvalRequests = 0

  /** How long a grant takes to answer, in milliseconds. */
  grantDelayMs = 0

  /** The route table, keyed by path. */
  private readonly routes: Map<string, () => unknown>

  constructor(state?: FakeApiState) {
    if (state !== undefined) {
      this.state = state
    }
    this.routes = new Map<string, () => unknown>([
      ['/health', () => this.state.health],
      ['/session', () => this.state.session],
      ['/tasks', () => this.state.tasks],
      ['/task', () => this.state.task],
      ['/plan', () => this.state.plan],
      ['/steps', () => this.state.steps],
      ['/sources', () => this.state.sources],
      ['/artifacts', () => this.state.artifacts],
    ])
  }

  /** The fetch the client calls. Bound, so it can be handed to a stub. */
  readonly fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = urlOf(input)
    const method = (init?.method ?? 'GET').toUpperCase()
    const path = url.replace(/^\/api/, '')
    this.requests.push({
      url,
      method,
      headers: headersOf(init?.headers),
      body: typeof init?.body === 'string' ? init.body : null,
      credentials: init?.credentials ?? null,
      referrerPolicy: init?.referrerPolicy ?? null,
    })

    if (method === 'POST' && path.endsWith('/grant')) {
      const approvalId = path.replace('/approvals/', '').replace('/grant', '')
      const approval = this.state.task.approvals.find((item) => item.approval_id === approvalId)
      if (this.grantDelayMs > 0) {
        await new Promise((resolve) => {
          setTimeout(resolve, this.grantDelayMs)
        })
      }
      if (this.refuseGrants) {
        return jsonResponse(403, {
          reason: 'permission_denied',
          message: 'the policy denied this capability.',
        })
      }
      if (approval === undefined) {
        return jsonResponse(403, {
          reason: 'approval_not_found',
          message: `the store holds no approval with the id ${approvalId}.`,
        })
      }
      approval.state = 'granted'
      approval.granted_at = '2026-10-20T09:30:00+00:00'
      const granted: ApprovalGranted = { approval }
      return jsonResponse(200, granted)
    }

    if (method === 'POST' && path === '/approvals') {
      this.approvalRequests += 1
      const body = JSON.parse(init?.body as string) as ApprovalBody
      const approval: Approval = {
        approval_id: '0193f0a1-0000-7000-8000-0000000000c3',
        task_id: TASK_ID,
        operation_id: '0193f0a1-0000-7000-8000-0000000000c4',
        capability: body.capability,
        resource_key: body.resource_key,
        args_digest: 'f'.repeat(64),
        state: 'pending',
        expires_at: body.expires_at,
      }
      // Adding it to the task is what lets the Approval panel show it: the
      // question the page asked is a record, and the screen reads records.
      this.state.task.approvals.push(approval)
      const requested: ApprovalRequested = {
        operation: {
          task_id: TASK_ID,
          run_id: '0193f0a1-0000-7000-8000-0000000000d2',
          stage_id: '0193f0a1-0000-7000-8000-0000000000d1',
          state: 'awaiting_approval',
          capability: body.capability,
          resource_key: body.resource_key,
          depends_on: body.depends_on ?? [],
          args_digest: approval.args_digest,
        },
        approval,
      }
      return jsonResponse(201, requested)
    }

    if (method === 'POST' && path === '/analysis') {
      this.analysisRuns += 1
      const body = JSON.parse(init?.body as string) as AnalysisBody
      const first = this.state.sources[0]
      if (first === undefined) {
        return jsonResponse(404, {
          reason: 'source_not_found',
          message: 'this task is bound to no source.',
        })
      }
      if (this.refuseAnalysis) {
        return jsonResponse(403, {
          reason: 'approval_missing',
          message:
            'analysis refused (approval_missing): the approval does not cover this exact ' +
            'request. Nothing was written.',
        })
      }
      const selection: Selection = {
        source_id: first.source.source_id,
        content_sha256: first.source.content_sha256,
        columns: ['value'],
        rows: { start: 2, end: 3 },
        missing: 'exclude',
      }
      const figure = this.figureless
        ? null
        : {
            ...figureReceipt(),
            receipt_id: '0193f0a1-0000-7000-8000-0000000000a4',
            relative_path: 'analysis/figure.svg',
            content_sha256: 'd'.repeat(64),
          }
      if (figure !== null) {
        this.state.task.artifacts.push(figure)
        this.state.artifacts.push({ receipt: figure, resource_key: figure.relative_path })
      }
      const drawn: FigureRun = {
        source: first.source,
        selection,
        result: { groups: [] },
        result_kind: 'GroupedResult',
        manifest: {
          input_file: {
            relative_path: body.path,
            content_sha256: first.source.content_sha256,
          },
          operator: body.operator_id,
          locator: {
            operator_id: body.operator_id,
            operator_version: '1.0.0',
            parameters: {},
            input_hashes: [first.source.content_sha256],
          },
          recipe: { relative_path: body.recipe, content_sha256: 'e'.repeat(64) },
          output: {},
          output_sha256: 'f'.repeat(64),
          environment: {
            matplotlib_version: '3.10.0',
            svg_hashsalt: '0',
            font_families: ['DejaVu Sans'],
            platform: 'win32',
          },
        },
        manifest_receipt: {
          receipt_id: '0193f0a1-0000-7000-8000-0000000000a3',
          task_id: TASK_ID,
          kind: 'manifest',
          relative_path: 'analysis/manifest.json',
          content_sha256: 'e'.repeat(64),
          size_bytes: 512,
          produced_by: 'analysis_operator',
          producer_id: body.operator_id,
          created_at: '2026-10-27T09:10:00+00:00',
        },
        figure_receipt: figure,
      }
      return jsonResponse(201, drawn)
    }

    if (method === 'POST' && path === '/report') {
      this.reportRenders += 1
      if (this.refuseReport) {
        return jsonResponse(403, {
          reason: 'report_content_refused',
          message:
            'application refused (report_content_refused): the task has nothing a report ' +
            'may carry. Nothing was written.',
        })
      }
      return jsonResponse(201, {
        receipt: {
          receipt_id: 'report-receipt-1',
          task_id: this.state.task.task.task_id,
          kind: 'report',
          relative_path: 'report/v1/report.md',
          content_sha256: 'a'.repeat(64),
          size_bytes: 2048,
          revision: 1,
          produced_by: 'report_template',
          producer_id: 'default',
          derived_from: [],
          staleness: 'current',
          staleness_reason: null,
          media_type: 'text/markdown',
          created_at: '2026-10-27T09:00:00+00:00',
          schema_version: 1,
        },
        resource_key: 'report',
        schema_version: 1,
      })
    }

    if (path.startsWith('/artifacts/') && path.endsWith('/content')) {
      this.artefactContentReads += 1
      return new Response(this.state.artefactContent, {
        status: 200,
        headers: { 'Content-Type': 'text/html' },
      })
    }

    const route = this.routes.get(path)
    if (route === undefined) {
      return jsonResponse(404, {
        reason: 'not_found',
        message: `the fake service has no route for ${path}.`,
      })
    }
    return jsonResponse(200, route())
  }

  /** The requests the client made to one path. */
  requestsTo(path: string): RecordedRequest[] {
    return this.requests.filter((request) => request.url.replace(/^\/api/, '') === path)
  }
}

/** The URL a request was made to. */
export function urlOf(input: RequestInfo | URL): string {
  if (typeof input === 'string') {
    return input
  }
  if (input instanceof URL) {
    return input.href
  }
  return input.url
}

/** The headers of a request, as plain pairs. */
function headersOf(headers: HeadersInit | undefined): Record<string, string> {
  const plain: Record<string, string> = {}
  if (headers === undefined) {
    return plain
  }
  if (headers instanceof Headers) {
    headers.forEach((value, name) => {
      plain[name.toLowerCase()] = value
    })
    return plain
  }
  if (Array.isArray(headers)) {
    for (const [name, value] of headers) {
      plain[name.toLowerCase()] = value
    }
    return plain
  }
  for (const [name, value] of Object.entries(headers)) {
    plain[name.toLowerCase()] = value
  }
  return plain
}

/** A JSON response, as the service would send it. */
function jsonResponse(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}
