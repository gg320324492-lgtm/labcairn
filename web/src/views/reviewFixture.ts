/**
 * The review desk's data, while the service's `/review` routes are being
 * built.
 *
 * **These are fixtures, and they say so.** The two JSON files carry the
 * contract's exact shapes — `ReviewOpinions` and `ReviewManuscript` — read
 * here once and asserted at the type level: a fixture that drifted from the
 * contract would fail this cast's compile-time check rather than mislead the
 * desk at runtime. When the service answers, this module is replaced by the
 * real reads and the JSON files are deleted; the paths below are already the
 * routes' names, so the swap touches this one file.
 */

import manuscriptJson from '../fixtures/manuscript-sample.json'
import opinionsJson from '../fixtures/review-sample.json'
import type { ReviewManuscript, ReviewOpinions } from './reviewContract'

/** `GET /review/opinions` — the left column's list. */
export const REVIEW_OPINIONS_PATH = '/review/opinions'

/** `GET /review/manuscript` — the middle column's text. */
export const REVIEW_MANUSCRIPT_PATH = '/review/manuscript'

/** `POST /review/decision` — the right column's verdict. */
export const REVIEW_DECISION_PATH = '/review/decision'

/** The opinion list, in the contract's shape. */
export const fixtureOpinions = opinionsJson as unknown as ReviewOpinions

/** The manuscript, in the contract's shape. */
export const fixtureManuscript = manuscriptJson as unknown as ReviewManuscript
