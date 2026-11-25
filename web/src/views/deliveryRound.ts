/**
 * The round the delivery centre works on, until the workbench names another.
 *
 * **The round is read, not assumed.** The centre used to address the
 * fixtures' sample round: the fixture's project and version, with the
 * sample binding's material and consent-window names. So the centre's
 * conditions — the preview before applying, the four deliverables in one
 * delivery centre — were exercised against a sample round and never
 * against the pilot paper. The service names the workspace's rounds, and
 * the centre asks it.
 *
 * **The material's address, the output label and the window are the sample
 * binding's, and they stay so.** A round names *which* paper and *which*
 * revision of it; it does not say what the output file shall be called, nor
 * how long the consent window shall run — those are the apply's own
 * arguments, and a route that invented them would be inventing policy. So
 * the centre addresses the service's round and carries the sample binding's
 * remaining arguments, and **it says so**, because a centre that applied a
 * real project under a sample's arguments without saying which was which
 * could not be believed about either.
 *
 * **The fixture stays, and it is a fallback.** When the service does not
 * answer, the sample round stands and the caller says so.
 */

import type { ApplyRound } from './deliveryCenterClient'
import { FIXTURE_INPUT_VERSION_ID, FIXTURE_PROJECT_ID } from './deliveryFixture'
import { readWorkbenchRound } from './rounds'
import type { RoundData } from './rounds'

/** The sample round, with the arguments the sample binding was built with. */
export const FIXTURE_APPLY_ROUND: ApplyRound = {
  projectId: FIXTURE_PROJECT_ID,
  inputVersionId: FIXTURE_INPUT_VERSION_ID,
  sourceRootId: 'sources',
  sourceKey: 'binding-sample.docx',
  outputLabel: 'binding-sample-output.docx',
  windowEnd: '2026-12-31T23:59:59+00:00',
}

/** The round the delivery centre addresses, and which side named it. */
export interface DeliveryRoundData {
  /** The round, with the arguments the apply needs. */
  readonly round: ApplyRound
  /** Whether the service named the round, rather than the sample. */
  readonly fromService: boolean
}

/**
 * Read the round the delivery centre addresses.
 *
 * **The service's round wins; the sample's stands in when it does not
 * answer.** The caller says which it drew, because the centre's own note
 * has to tell a reader whether the numbers on the screen are the
 * workspace's or the sample's.
 */
export async function readDeliveryRound(): Promise<DeliveryRoundData> {
  const read: RoundData = await readWorkbenchRound()
  return {
    round: {
      ...FIXTURE_APPLY_ROUND,
      projectId: read.round.projectId,
      inputVersionId: read.round.versionId,
    },
    fromService: read.fromService,
  }
}
