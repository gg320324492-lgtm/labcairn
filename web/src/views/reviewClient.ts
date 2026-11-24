/**
 * The review desk's reads and writes, against the service's `/review` routes.
 *
 * **One seam, named for the desk.** The desk draws what the service answers —
 * `GET /review/opinions` and `GET /review/manuscript` — and records a
 * person's verdict with `POST /review/decision`. The paths live in
 * `../api/paths` so the drift check can compare them with the service's own
 * route table, and the request shapes are the service's
 * (`ReviewDecisionBody`, from the generated types) rather than re-spelled
 * here.
 *
 * **The fixture stays, and it is a fallback.** When the service does not
 * answer, the desk draws the fixtures and says so; the caller decides that,
 * because a fallback that hid itself would be a fixture that lied about
 * being the service.
 */

import { api } from '../api/client'
import { API_PATHS, reviewManuscriptPath, reviewOpinionsPath } from '../api/paths'
import type {
  ReviewDecisionBody,
  ReviewDecisionData,
  ReviewSuggestBody,
  ReviewSuggestRun,
} from '../api/generated'
import type { ReviewManuscript, ReviewOpinions } from './reviewContract'

/**
 * The desk's data, as the service answered it.
 *
 * `fromService` says which side answered: the desk labels what it draws, so
 * a reader can tell the service's word from the fixture's.
 */
export interface ReviewData<T> {
  /** The answer, in the contract's shape. */
  readonly data: T
  /** Whether the service answered, rather than the fixture. */
  readonly fromService: boolean
}

/** The workbench operator whose handle travels with every decision. */
export const REVIEW_OPERATOR = 'user'

/**
 * Read one review round's opinions, falling back to the fixture.
 *
 * The service's answer is taken verbatim; a refusal or a failure leaves the
 * fixture standing, and the caller says which it drew.
 */
export async function readOpinions(
  projectId: string,
  versionId: string,
): Promise<ReviewData<ReviewOpinions>> {
  try {
    const data = await api.get<ReviewOpinions>(reviewOpinionsPath(projectId, versionId))
    return { data, fromService: true }
  } catch {
    const { fixtureOpinions } = await import('./reviewFixture')
    return { data: fixtureOpinions, fromService: false }
  }
}

/**
 * Read one review round's manuscript, falling back to the fixture.
 *
 * The same rule the opinions read follows: the service's answer wins, and a
 * service that is not there leaves the fixture.
 */
export async function readManuscript(
  projectId: string,
  versionId: string,
): Promise<ReviewData<ReviewManuscript>> {
  try {
    const data = await api.get<ReviewManuscript>(reviewManuscriptPath(projectId, versionId))
    return { data, fromService: true }
  } catch {
    const { fixtureManuscript } = await import('./reviewFixture')
    return { data: fixtureManuscript, fromService: false }
  }
}

/**
 * Record one verdict, and answer with the service's own record of it.
 *
 * **The verdict is the person's word, posted once.** The service writes the
 * row and answers with what it wrote — the desk does not hold a copy of the
 * verdict as state and call it saved.
 */
export function recordDecision(
  projectId: string,
  body: Omit<ReviewDecisionBody, 'project_id'>,
): Promise<ReviewDecisionData> {
  const request: ReviewDecisionBody = { ...body, project_id: projectId }
  return api.post<ReviewDecisionData>(API_PATHS.reviewDecision, request)
}

/**
 * Run the suggestion loop over one version's pending opinions.
 *
 * **The mode names who answers, and the desk offers both.** `substitute`
 * spends nothing and sends nothing out of the machine, so it is the desk's
 * default; `real` asks the authorised model and is refused by the service
 * with `model_suggestion_no_provider` when no transport is wired in. The
 * answer is the run's own account — counts, not suggestions — and the
 * suggestions themselves are read back through `GET /review/opinions`.
 */
export function runSuggestionLoop(body: ReviewSuggestBody): Promise<ReviewSuggestRun> {
  return api.post<ReviewSuggestRun>(API_PATHS.reviewSuggest, body)
}
