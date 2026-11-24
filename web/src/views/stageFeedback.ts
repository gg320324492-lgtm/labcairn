/**
 * The stage feedback bar's reading of the service's state.
 *
 * **The phases are read, not declared.** Everything here maps the service's
 * own answers — the declared plan's steps and the runtime stages — onto the
 * workbench's phases, and nothing here invents a stage the service has not
 * named. The module is separate from the bar's component so that both the
 * mapping and the component can be witnessed apart.
 */

import type { TaskPlan, TaskState } from '../api/generated'

/** The phases the workbench follows, in the order a round runs. */
export const WORKBENCH_PHASES = [
  'import',
  'locate',
  'suggest',
  'review',
  'apply',
  'deliver',
] as const

export type WorkbenchPhase = (typeof WORKBENCH_PHASES)[number]

/** How a phase stands, in the service's own vocabulary. */
export type PhaseStatus = 'pending' | 'active' | 'completed'

/** What one bar segment is drawn from. */
export interface PhaseSegment {
  /** The workbench phase the segment names. */
  readonly phase: WorkbenchPhase
  /** The declared stage names the phase stands for. */
  readonly stageNames: readonly string[]
  /** How far the phase has got, read off its stages. */
  readonly status: PhaseStatus
}

/**
 * Which declared stages stand behind each workbench phase.
 *
 * The plan's stage vocabulary is the service's (`StageName`): the intake and
 * inventory stages import the material, the retrieve and evidence stages
 * locate what the comments anchor to, the propose stage generates the
 * suggestions, the draft and validate stages are the desk's review work, and
 * the deliver stage applies and publishes. A plan that names none of these
 * maps to no phase — and the bar says so rather than guessing.
 */
const PHASE_STAGE_NAMES: Readonly<Record<WorkbenchPhase, readonly string[]>> = {
  import: ['intake', 'inventory'],
  locate: ['retrieve', 'evidence'],
  suggest: ['propose'],
  review: ['draft', 'validate'],
  apply: [],
  deliver: ['deliver'],
}

/** The declared statuses that mean a stage has finished. */
const COMPLETED_STATUSES: ReadonlySet<string> = new Set(['completed'])

/** The declared statuses that mean a stage is running or blocked on work. */
const ACTIVE_STATUSES: ReadonlySet<string> = new Set(['entered', 'blocked'])

/**
 * Read the workbench's phases off the service's own answers.
 *
 * **A phase is its stages.** A phase whose stages have all completed is
 * complete; a phase with any stage entered or blocked is active; and a phase
 * whose stages are all still pending is pending. The plan's steps carry the
 * declared order and the service's own derivation of each step's status, and
 * the task's runtime stages carry the store's record — a step the plan
 * declares but the store has not run yet is a pending stage, not a missing
 * one.
 */
export function phaseSegments(plan: TaskPlan | null, state: TaskState | null): PhaseSegment[] {
  const declared: string[] = []
  for (const step of plan?.steps ?? []) {
    if (!declared.includes(step.stage)) {
      declared.push(step.stage)
    }
  }
  // The runtime stages are the store's own record; a stage that ran without
  // being in the plan read is still the service's word, and it is drawn.
  for (const stage of state?.stages ?? []) {
    if (!declared.includes(stage.name)) {
      declared.push(stage.name)
    }
  }

  const statuses = new Map<string, string>()
  // The plan's steps already carry the service's derivation — read_plan sets
  // each declared step's status from the store's latest stage — so they are
  // read first, and the runtime stages (which may name a stage the plan read
  // has not) are laid over them.
  for (const step of plan?.steps ?? []) {
    statuses.set(step.stage, step.status)
  }
  for (const stage of state?.stages ?? []) {
    if (stage.status !== undefined) {
      statuses.set(stage.name, stage.status)
    }
  }

  return WORKBENCH_PHASES.map((phase) => {
    const stageNames = PHASE_STAGE_NAMES[phase].filter((name) => declared.includes(name))
    if (stageNames.length === 0) {
      return { phase, stageNames, status: 'pending' as const }
    }
    const stageStatuses = stageNames.map((name) => statuses.get(name) ?? 'pending')
    if (stageStatuses.every((status) => COMPLETED_STATUSES.has(status))) {
      return { phase, stageNames, status: 'completed' as const }
    }
    if (stageStatuses.some((status) => ACTIVE_STATUSES.has(status))) {
      return { phase, stageNames, status: 'active' as const }
    }
    return { phase, stageNames, status: 'pending' as const }
  })
}

/**
 * The phase the workbench is in: the first active one, or the last completed
 * one, or none.
 *
 * **A round at rest is at its last finished phase.** When every stage has
 * completed — or when none has started — the bar does not invent motion: the
 * current phase is the furthest one the service has actually reached, and a
 * bar that showed "active" for a finished round would be decorating.
 */
export function currentPhase(segments: readonly PhaseSegment[]): WorkbenchPhase | null {
  const active = segments.find((segment) => segment.status === 'active')
  if (active !== undefined) {
    return active.phase
  }
  let reached: WorkbenchPhase | null = null
  for (const segment of segments) {
    if (segment.status === 'completed') {
      reached = segment.phase
    }
  }
  return reached
}
