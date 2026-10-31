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
  EvidenceRecord,
  FigureRun,
  GuidanceRule,
  GuidanceRuleVerdictBody,
  Health,
  ProjectGraph,
  Selection,
  SessionInfo,
  Source,
  SourceView,
  Task,
  TaskPlan,
  TaskState,
  TaskStep,
  Trajectory,
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
  /** The chain's comments, the edits that answered them, and the states. */
  trajectory: Trajectory
  /** The project's versions and the accepted edges between them. */
  trajectoryGraph: ProjectGraph
  /** The guidance rules the memory holds. */
  guidanceRules: GuidanceRule[]
  /** The ledger's records for this task. */
  records: EvidenceRecord[]
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

/** The chain's own key for the issue the fake serves. */
export const ISSUE_KEY = 'issue-method'

/** The paper project the fake serves. */
export const PROJECT_ID = 'project-core'

/** The advisor's comment, and the change that answered it. */
export const FEEDBACK_ID = 'fb-method'

/** The rule the fake serves as a candidate, with a case against it. */
export const RULE_ID = 'rule-method'

/**
 * The chain's rows, as the mentor line's route serves them.
 *
 * **The states are the chain's own vocabulary** — pending, addressed,
 * partially addressed, not addressed — and the grades are observed,
 * inferred and human verified.
 */
export function trajectoryFixture(): Trajectory {
  return {
    comments: [
      {
        feedback_id: FEEDBACK_ID,
        issue_key: ISSUE_KEY,
        version_id: 'v1',
        comment_text: 'Name the method before its result.',
        anchor_text: 'the method was not named',
      },
      {
        feedback_id: 'fb-units',
        issue_key: ISSUE_KEY,
        version_id: 'v2',
        comment_text: 'Say which core the depth came from.',
        anchor_text: '4.2 mm of silt',
      },
    ],
    edits: [
      {
        edit_action_id: 'edit-method',
        feedback_id: FEEDBACK_ID,
        version_edge_id: 'edge-1',
        actor_kind: 'student',
        grade: 'observed',
      },
      {
        edit_action_id: 'edit-method-2',
        feedback_id: FEEDBACK_ID,
        version_edge_id: 'edge-1',
        actor_kind: 'model',
        grade: 'inferred',
      },
      {
        edit_action_id: 'edit-no-comment',
        feedback_id: null,
        version_edge_id: 'edge-2',
        actor_kind: 'advisor',
        grade: 'human_verified',
      },
    ],
    responses: [
      { feedback_id: FEEDBACK_ID, states: ['addressed'] },
      { feedback_id: 'fb-units', states: ['pending', 'partially_addressed'] },
    ],
  }
}

/** The project's versions and the accepted edges between them. */
export function projectGraphFixture(): ProjectGraph {
  return {
    version_ids: ['v1', 'v2'],
    edges: [{ edge_id: 'edge-1', parent_version_id: 'v1', child_version_id: 'v2' }],
  }
}

/**
 * The rules the memory holds.
 *
 * **One candidate with a case against it, and one that stands.** The
 * candidate is the one a person may settle; the confirmed one is the one
 * the memory refuses to settle twice.
 */
export function guidanceRulesFixture(): GuidanceRule[] {
  return [
    {
      rule_id: RULE_ID,
      version: 1,
      issue_type: 'method',
      statement: 'Name the method before its result.',
      context: 'A result with no method cannot be checked by anybody else.',
      scope: 'Every claim about a measurement.',
      example: 'The core was X-rayed before it was sectioned.',
      state: 'candidate',
      proposed_by: 'alice',
      proposed_at: '2026-10-20T09:00:00+00:00',
      confirmed_by: null,
      confirmed_at: null,
      resolution_reason: null,
      sources: [ISSUE_KEY],
      counterexamples: [
        {
          statement: 'A reading from a published protocol needs no naming.',
          issue_key: 'issue-protocol',
          recorded_by: 'bob',
          recorded_at: '2026-10-21T11:30:00+00:00',
        },
      ],
    },
    {
      rule_id: 'rule-units',
      version: 2,
      issue_type: 'units',
      statement: 'Give the unit with the number.',
      context: 'A number without a unit is not a quantity.',
      scope: 'Every numeric claim.',
      example: '4.2 mm, and not 4.2.',
      state: 'confirmed',
      proposed_by: 'bob',
      proposed_at: '2026-10-22T08:00:00+00:00',
      confirmed_by: 'carol',
      confirmed_at: '2026-10-22T09:00:00+00:00',
      resolution_reason: null,
      sources: ['issue-units'],
      counterexamples: [
        {
          statement: 'A dimensionless ratio needs no unit.',
          issue_key: 'issue-ratio',
          recorded_by: 'carol',
          recorded_at: '2026-10-23T10:00:00+00:00',
        },
      ],
    },
    {
      rule_id: 'rule-anchors',
      version: 1,
      issue_type: 'anchors',
      statement: 'Cite the anchor the claim rests on.',
      context: 'A claim with no address cannot be found again.',
      scope: 'Every claim.',
      example: 'Anchor the sentence that carries the number.',
      state: 'withdrawn',
      proposed_by: 'carol',
      proposed_at: '2026-10-18T08:00:00+00:00',
      confirmed_by: 'dave',
      confirmed_at: '2026-10-19T08:00:00+00:00',
      resolution_reason: 'the ledger cannot check an anchor yet',
      sources: ['issue-anchors'],
      counterexamples: [],
    },
  ]
}

/**
 * The ledger's records: a model's proposal, and the person's own record
 * beside it.
 *
 * **The proposal is marked as superseded by the person's record**, which is
 * the only link the contract carries between them.
 */
export function recordsFixture(): EvidenceRecord[] {
  return [
    {
      schema_version: 1,
      evidence_id: 'rec-model',
      task_id: TASK_ID,
      kind: 'claim',
      text: 'The core records 4.2 mm of silt.',
      value: null,
      unit: null,
      tolerance: null,
      anchor_ids: ['anchor-core-1'],
      extracted_span: '4.2 mm of silt',
      extracted_span_sha256: 'e'.repeat(64),
      status: 'extracted',
      verification_log: [],
      created_by: 'model_proposal',
      created_by_id: 'model-1',
      source_content_hash: 'c'.repeat(64),
      created_at: '2026-10-25T09:00:00+00:00',
      superseded_by: 'rec-person',
    },
    {
      schema_version: 1,
      evidence_id: 'rec-person',
      task_id: TASK_ID,
      kind: 'claim',
      text: 'The core records 4.2 mm of silt.',
      value: null,
      unit: null,
      tolerance: null,
      anchor_ids: ['anchor-core-1'],
      extracted_span: '4.2 mm of silt',
      extracted_span_sha256: 'e'.repeat(64),
      status: 'user_attested',
      verification_log: [
        {
          schema_version: 1,
          check: 'c4',
          checker_id: 'alice',
          outcome: 'not_checked',
          detail: 'confirmed. I read the core log.',
          checked_at: '2026-10-25T10:00:00+00:00',
        },
      ],
      created_by: 'user',
      created_by_id: 'alice',
      source_content_hash: 'c'.repeat(64),
      created_at: '2026-10-25T09:30:00+00:00',
      superseded_by: null,
    },
    {
      schema_version: 1,
      evidence_id: 'rec-rule',
      task_id: TASK_ID,
      kind: 'result',
      text: 'The core holds 4.2 mm of silt.',
      value: 4.2,
      unit: 'mm',
      tolerance: 0.1,
      anchor_ids: ['anchor-core-1'],
      extracted_span: '4.2 mm of silt',
      extracted_span_sha256: 'e'.repeat(64),
      status: 'verified_by_rule',
      verification_log: [
        {
          schema_version: 1,
          check: 'c2',
          checker_id: 'rule-units',
          outcome: 'pass',
          detail: 'the number carries its unit',
          checked_at: '2026-10-24T09:00:00+00:00',
        },
      ],
      created_by: 'rule',
      created_by_id: 'rule-units',
      source_content_hash: 'c'.repeat(64),
      created_at: '2026-10-24T08:00:00+00:00',
      superseded_by: null,
    },
  ]
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
    trajectory: trajectoryFixture(),
    trajectoryGraph: projectGraphFixture(),
    guidanceRules: guidanceRulesFixture(),
    records: recordsFixture(),
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

  /** How many verdicts the service has been asked for. */
  ruleConfirmations = 0

  /**
   * Whether the service refuses the verdict in the route's own vocabulary.
   *
   * **This is the route's own refusal**, the one it makes before the memory
   * is asked: `arguments_invalid`, with the message the route writes.
   */
  refuseWithArguments = false

  /**
   * Whether the service answers the verdict in the schema's vocabulary.
   *
   * **The schema's answer, not the layer's refusal**: a status, and the
   * schema's own lines about which part of the body it would not accept.
   */
  refuseWithSchema = false

  /**
   * Whether the trajectory's answer carries a change that answers no
   * comment.
   *
   * **The service cannot send one**: it reads its changes by the comments it
   * read, so every change it answers with answers a comment. The flag
   * exists so that the panel's handling of the contract's nullable field is
   * watched rather than assumed.
   */
  serveLooseEdits = false

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
      ['/records', () => this.state.records],
      ['/guidance/rules', () => this.state.guidanceRules],
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

    if (method === 'POST' && path.startsWith('/guidance/rules/') && path.endsWith('/confirm')) {
      return this.settleTheRule(path, init)
    }

    if (method === 'GET' && path.startsWith('/trajectory/graph')) {
      return this.answerTheGraph(path)
    }

    if (method === 'GET' && path.startsWith('/trajectory')) {
      return this.answerTheTrajectory(path)
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

  /**
   * The verdict on one rule, and the rule as it stands afterwards.
   *
   * **The refusals are the service's own, in the service's own order.** The
   * route checks its body before the memory is asked, so an empty `user_id`
   * and a reason given with a confirmation are `arguments_invalid` — and the
   * memory's own reasons come after: the second reader, the closed state
   * machine, and the reason a dispute must carry.
   */
  private settleTheRule(path: string, init?: RequestInit): Response {
    const ruleId = decodeURIComponent(path.slice('/guidance/rules/'.length, -'/confirm'.length))
    const body = JSON.parse(init?.body as string) as GuidanceRuleVerdictBody
    this.ruleConfirmations += 1
    if (this.refuseWithSchema) {
      return jsonResponse(422, {
        detail: [
          {
            loc: ['body', 'verdict'],
            msg: "Input should be 'confirmed' or 'disputed'",
            type: 'literal_error',
            input: body.verdict,
          },
        ],
      })
    }
    if (this.refuseWithArguments) {
      return jsonResponse(403, {
        reason: 'arguments_invalid',
        message:
          'a confirmation nobody signs is not a confirmation. Name the person whose word it is.',
      })
    }
    if (body.verdict === 'confirmed' && (body.reason ?? '').trim() !== '') {
      return jsonResponse(403, {
        reason: 'arguments_invalid',
        message:
          'a reason belongs to a dispute, and a confirmed rule carries none: the memory holds ' +
          'no reason on a rule that stands. Dispute the rule with the reason instead.',
      })
    }
    const rule = this.state.guidanceRules.find((entry) => entry.rule_id === ruleId)
    if (rule === undefined) {
      return jsonResponse(403, {
        reason: 'guidance_rule_not_found',
        message: `no rule carries the id ${JSON.stringify(ruleId)}`,
      })
    }
    if (body.verdict === 'disputed' && (body.reason ?? '').trim() === '') {
      return jsonResponse(403, {
        reason: 'guidance_resolution_without_reason',
        message: 'a dispute without a reason is a shrug.',
      })
    }
    if (rule.proposed_by === body.user_id) {
      return jsonResponse(403, {
        reason: 'guidance_confirmer_is_proposer',
        message:
          'the person who proposed a rule cannot be the one who confirms it: one person ' +
          'reading twice is one person reading once with extra steps.',
      })
    }
    if (body.verdict === 'confirmed' && rule.state !== 'candidate') {
      return jsonResponse(403, {
        reason: 'guidance_transition_not_possible',
        message: `a rule in state ${JSON.stringify(rule.state)} cannot be confirmed; only a candidate can`,
      })
    }
    if (body.verdict === 'disputed' && rule.state === 'withdrawn') {
      return jsonResponse(403, {
        reason: 'guidance_transition_not_possible',
        message: 'a withdrawn rule cannot be disputed; propose a new version instead',
      })
    }
    rule.state = body.verdict
    rule.confirmed_by = rule.confirmed_by ?? body.user_id
    rule.confirmed_at = rule.confirmed_at ?? '2026-11-01T09:00:00+00:00'
    if (body.verdict === 'disputed') {
      rule.resolution_reason = body.reason ?? null
    }
    return jsonResponse(200, rule)
  }

  /**
   * The project's versions among the ones named, and the accepted edges
   * between them.
   *
   * **Only the versions named are answered with**, and only the edges whose
   * two ends were both named — the service's own rule.
   */
  private answerTheGraph(path: string): Response {
    const query = queryOf(path)
    const named = query.getAll('version_id')
    const versionIds = this.state.trajectoryGraph.version_ids.filter((id) => named.includes(id))
    const edges = this.state.trajectoryGraph.edges.filter(
      (edge) => named.includes(edge.parent_version_id) && named.includes(edge.child_version_id),
    )
    return jsonResponse(200, { version_ids: versionIds, edges })
  }

  /**
   * The chain's comments under the issues named, the edits that answered
   * them, and the states of the responses.
   *
   * **The edits are read by the comments, as the service reads them**, so an
   * edit that answers no comment is not among them — unless the flag says
   * the service sent one anyway.
   */
  private answerTheTrajectory(path: string): Response {
    const query = queryOf(path)
    const keys = query.getAll('issue_key')
    const comments = this.state.trajectory.comments.filter((comment) =>
      keys.includes(comment.issue_key),
    )
    const feedbackIds = comments.map((comment) => comment.feedback_id)
    const edits = this.state.trajectory.edits.filter(
      (edit) => edit.feedback_id !== null && feedbackIds.includes(edit.feedback_id),
    )
    if (this.serveLooseEdits) {
      edits.push(...this.state.trajectory.edits.filter((edit) => edit.feedback_id === null))
    }
    const responses = this.state.trajectory.responses.filter((response) =>
      feedbackIds.includes(response.feedback_id),
    )
    return jsonResponse(200, { comments, edits, responses })
  }

  /** The requests the client made to one path. */
  requestsTo(path: string): RecordedRequest[] {
    return this.requests.filter((request) => request.url.replace(/^\/api/, '') === path)
  }
}

/**
 * The query parameters of the path the fake was asked for.
 *
 * **The query is part of the question**, so the fake reads it: the route
 * that takes an issue key answers about that issue and no other.
 */
function queryOf(path: string): URLSearchParams {
  const [, query = ''] = path.split('?')
  return new URLSearchParams(query)
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
