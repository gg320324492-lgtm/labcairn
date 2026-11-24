/**
 * The round the delivery centre works on, until the workbench names another.
 *
 * **The round is the fixtures' own.** The desk's reads are parameterless from
 * this seat — the round the fixtures name is the round this workspace holds —
 * so the addresses the centre sends are the fixture's project and version,
 * with the material and consent-window names the sample binding was built
 * with. A workbench that binds other rounds will name them here, in one
 * place, rather than at every read and write.
 */

import type { ApplyRound } from './deliveryCenterClient'
import { FIXTURE_INPUT_VERSION_ID, FIXTURE_PROJECT_ID } from './deliveryFixture'

/** The one round this workbench's delivery centre addresses. */
export const DELIVERY_ROUND: ApplyRound = {
  projectId: FIXTURE_PROJECT_ID,
  inputVersionId: FIXTURE_INPUT_VERSION_ID,
  sourceRootId: 'sources',
  sourceKey: 'binding-sample.docx',
  outputLabel: 'binding-sample-output.docx',
  windowEnd: '2026-12-31T23:59:59+00:00',
}
