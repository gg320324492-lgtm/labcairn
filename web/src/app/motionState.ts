/**
 * The motion state: what the reader has chosen about the workbench's motion,
 * and what the page is therefore doing.
 *
 * **What this is.** A display preference of this page and nothing else. It
 * names no task, no account and no capability: all it says is whether the
 * workbench's transitions are allowed to move. The workbench's own rule is
 * that a state is said twice — in text and in structure — so this preference
 * is held the same way: the effective state is an attribute on the document
 * root (`data-motion`), which the stylesheet reads, and a sentence on the
 * page, which the reader reads.
 *
 * **Why it is in the browser's storage, and why that does not contradict the
 * token's rule.** `api/session.ts` keeps the session token out of the
 * browser's storage for two reasons: a stored *secret* is a secret a later
 * change to this page could read out of the browser and send somewhere, and
 * the token is minted per service start, so a stored one is stale anyway. A
 * motion preference is neither kind of thing. It is not a secret — it grants
 * nothing, identifies nobody and says nothing about the task — and it is not
 * stale, because "reduce the motion" is true of this browser for as long as
 * the browser holds it. What the preference is worth is exactly what the
 * token must not be: it survives the tab, so a reader who has asked for less
 * motion does not have to ask again after a reload. The token stays where it
 * is, in a module variable and in no store at all.
 *
 * **Only a choice the reader actually made is written.** The default is not
 * written on the first visit: a page that stored "follow the system" at load
 * would freeze the answer at the moment of that visit, and a reader who
 * later changed their system's setting would be held to the old one. An
 * empty storage therefore means "no choice made", which is read as "follow
 * the system" — and an empty storage is what the workbench leaves behind
 * until the reader chooses something.
 *
 * **The default follows the system, and this path only ever takes motion
 * away.** The plan asks for a configurable entry point for *reducing* motion,
 * and this is that entry point; it never adds motion back. A reader whose
 * system asks for reduced motion cannot have that overridden here, because
 * the stylesheet's media query stands the motion down whatever this page
 * says. So the two paths can only ever agree in the direction of less motion:
 * the reader's choice and the system's ask are combined by an "or", and the
 * effective state is reduced when either one says so.
 */

/** What a reader has chosen about the workbench's motion. */
export type MotionChoice = 'system' | 'reduced'

/** How much motion the workbench actually shows. */
export type MotionState = 'full' | 'reduced'

/** The media query the system's own preference is read through. */
export const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'

/** The attribute the stylesheet keys the application-level path off. */
export const MOTION_ATTRIBUTE = 'data-motion'

/** Where a reader's own choice is remembered. */
export const MOTION_STORAGE_KEY = 'labcairn.motion'

/**
 * The browser's storage, when the browser has one and hands it over.
 *
 * A locked-down profile and a private window with storage disabled both
 * refuse; that is a browser the preference cannot be remembered in, not a
 * page that has failed.
 */
function browserStorage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}

/**
 * The choice the reader has made, or `null` when they have made none.
 *
 * `null` and `'system'` behave the same way — the workbench follows the
 * system — but they are not the same fact, and the difference is worth
 * keeping: `null` is the absence of a choice.
 */
export function readMotionChoice(storage?: Storage | null): MotionChoice | null {
  const store = storage === undefined ? browserStorage() : storage
  if (store === null) {
    return null
  }
  let raw: string | null
  try {
    raw = store.getItem(MOTION_STORAGE_KEY)
  } catch {
    return null
  }
  return raw === 'reduced' || raw === 'system' ? raw : null
}

/**
 * Remember the reader's choice.
 *
 * Returns whether the choice was remembered: a browser that refuses to
 * store it still gets the choice for this page, and the page says so rather
 * than promising a reload will keep it.
 */
export function writeMotionChoice(choice: MotionChoice, storage?: Storage | null): boolean {
  const store = storage === undefined ? browserStorage() : storage
  if (store === null) {
    return false
  }
  try {
    store.setItem(MOTION_STORAGE_KEY, choice)
    return true
  } catch {
    return false
  }
}

/**
 * The system's own answer to the motion question, when there is one.
 *
 * A browser without `matchMedia` — or one whose call throws — has no
 * preference to report, and a browser with no preference is a browser that
 * has not asked for less motion.
 */
export function reducedMotionQuery(query?: MediaQueryList | null): MediaQueryList | null {
  if (query !== undefined) {
    return query
  }
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return null
  }
  try {
    return window.matchMedia(REDUCED_MOTION_QUERY)
  } catch {
    return null
  }
}

/**
 * How much motion the workbench shows, given the reader's choice and the
 * system's ask.
 *
 * The two are combined by an "or" and never by a choice that takes motion
 * back: the system's ask stands the motion down on its own, so the most the
 * reader's choice can do is stand it down as well. This is the same rule the
 * stylesheet's two paths obey, which is why the state this reports and the
 * state the page is in are the same state.
 */
export function effectiveMotion(choice: MotionChoice | null, systemReduced: boolean): MotionState {
  if (choice === 'reduced') {
    return 'reduced'
  }
  return systemReduced ? 'reduced' : 'full'
}

/**
 * State the effective motion on the document root.
 *
 * The attribute is the structure half of the state: the stylesheet's
 * application-level path reads it, and a reader who reads the page's markup
 * can see which motion the workbench is in without watching it. The
 * attribute is left in place when the control goes away — the page's motion
 * did not change because the control did.
 */
export function applyMotionState(state: MotionState, root?: HTMLElement | null): void {
  const element =
    root === undefined ? (typeof document === 'undefined' ? null : document.documentElement) : root
  if (element === null) {
    return
  }
  element.setAttribute(MOTION_ATTRIBUTE, state)
}
