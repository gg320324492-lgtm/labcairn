/**
 * Metadata describing what this web package currently is.
 *
 * This is the single source of truth for the baseline placeholder text so that the
 * component and its tests cannot drift apart. It deliberately describes the ABSENCE of
 * product features: LC-P1-01/T10 ships a buildable skeleton only, and the Phase 1
 * research workspace is a later work order.
 */

export interface BaselineFacts {
  /** Work order that produced this skeleton. */
  readonly workOrder: string
  /** Human-facing release state. Must never be phrased as "working". */
  readonly status: 'under-construction'
  /** One-line statement of what the package does today. */
  readonly summary: string
  /** Capabilities a reader must NOT assume exist yet. */
  readonly notImplemented: readonly string[]
}

export const BASELINE_FACTS = {
  workOrder: 'LC-P1-01 / T10',
  status: 'under-construction',
  summary:
    'Placeholder only. This package is the buildable, type-checked and unit-tested React + TypeScript skeleton for the LabCairn local workbench. It renders no research functionality.',
  notImplemented: [
    'Research workspace, task list or run history',
    'Connection to any LabCairn Python API',
    'Source material, evidence or artifact views',
    'Model calls of any kind',
  ],
} as const satisfies BaselineFacts
