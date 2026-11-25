/**
 * The round the workbench works on, as the service names it.
 *
 * **The round used to be the fixture's, and the fixture said so.** The
 * review desk took its project and version from a sample fixture, and so
 * did the delivery centre. So every condition the workbench was supposed
 * to hold — the opinions of the pilot paper, the preview before applying,
 * the four deliverables in one delivery centre — was exercised against a
 * sample round, and the pilot paper itself was never addressed.
 *
 * **So the round is read, not assumed.** `GET /review/rounds` names the
 * rounds this workspace holds, and the workbench draws the first one,
 * which is the most recent. The naming is ids and versions and never the
 * material behind them: the words are reached through the service's own
 * review routes, which apply the policy.
 *
 * **The fixture stays, and it is a fallback.** When the service does not
 * answer, the sample round stands and the caller says so — a fallback that
 * hid itself would be a fixture that lied about being the service. And a
 * reader is told *which* round they are looking at either way, because a
 * desk that draws a sample round without saying so is a desk that cannot
 * be believed about the pilot paper.
 */

import { api } from '../api/client'
import type { ReviewRoundListed } from '../api/generated'
import { API_PATHS } from '../api/paths'
import { fixtureOpinions } from './reviewFixture'

/** `GET /review/rounds` — the rounds this workspace holds. */
export const REVIEW_ROUNDS_PATH = API_PATHS.reviewRounds

/** One round, as the workbench addresses it. */
export interface WorkbenchRound {
  /** The project the round belongs to. */
  readonly projectId: string
  /** The version the round works from. */
  readonly versionId: string
  /** When the version was recorded, in the service's own spelling. */
  readonly createdAt: string
}

/** What the service named, and which side named it. */
export interface RoundData {
  /** The round the workbench addresses. */
  readonly round: WorkbenchRound
  /** Whether the service named it, rather than the sample fixture. */
  readonly fromService: boolean
}

/**
 * The sample round, used when the service does not answer.
 *
 * **It is the review fixture's own round**, so the fixture's opinions and
 * the fixture's manuscript belong to it — a fallback that named a
 * different round would put the fixture's material under the wrong
 * address.
 */
export const FIXTURE_ROUND: WorkbenchRound = {
  projectId: fixtureOpinions.project_id,
  versionId: fixtureOpinions.version_id,
  createdAt: '',
}

/**
 * Read the round the workbench addresses, falling back to the sample.
 *
 * **The service's answer wins, and an empty answer is not an answer.** A
 * workspace with no round the caller may reach names none, and the sample
 * stands in its place — with the caller saying which it drew.
 */
export async function readWorkbenchRound(): Promise<RoundData> {
  try {
    const rounds = await api.get<ReviewRoundListed[]>(REVIEW_ROUNDS_PATH)
    const newest = rounds[0]
    if (newest === undefined) {
      return { round: FIXTURE_ROUND, fromService: false }
    }
    return {
      round: {
        projectId: newest.project_id,
        versionId: newest.version_id,
        createdAt: newest.created_at,
      },
      fromService: true,
    }
  } catch {
    return { round: FIXTURE_ROUND, fromService: false }
  }
}
