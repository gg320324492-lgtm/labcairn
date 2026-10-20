/**
 * Reading the task, and drawing it.
 *
 * **The workbench holds no state of its own.** Every fact it shows is the
 * API's answer, and the answer is read again on every render rather than
 * being the page's own copy. That is what makes the web refresh rule true
 * rather than asserted: after a reload the screen shows the database's
 * state, because there was no cached copy to show instead.
 *
 * The read is therefore scheduled by the render and not by a dependency
 * list. A hook that fetched once and kept the result would be a cached copy,
 * and a cached copy is a second source of truth about the task — the one that
 * a change to the API would not reach.
 *
 * **What is held between renders is the API's own answer.** React has to
 * hold it somewhere for the screen to show it, and it is held verbatim:
 * nothing is merged, nothing is derived, and nothing is decided here. The
 * comparison below is over the serialised form, so the page re-renders only
 * when what it would show has actually changed.
 *
 * **Why the reads are batched.** The workbench shows eight things, and
 * reading them one at a time would render the page eight times over on the
 * way in. One effect, eight requests, one comparison, one render.
 *
 * **Why a failed read does not blank the page.** Each read settles on its
 * own, so that a service which cannot answer one question still answers the
 * other seven, and the panel that could not be drawn says so.
 */

import { useCallback, useEffect, useReducer, useState } from 'react'

import { describeError } from '../api/client'
import type { ApiError, LabCairnClient } from '../api/client'
import type {
  ArtifactView,
  Health,
  SourceView,
  Task,
  TaskPlan,
  TaskState,
  TaskStep,
} from '../api/generated'
import { API_PATHS } from '../api/paths'

/** One read: what came back, or why it did not. */
export interface ApiRead<T> {
  /** The API's answer, or null when the read has not landed. */
  readonly data: T | null
  /** Why there is no answer, when there is none. */
  readonly error: ApiError | null
}

/**
 * Everything the workbench draws, one read per thing.
 *
 * The session is a path and not a token: the token stays in the client's
 * module-level holder, where React cannot see it.
 */
export interface WorkbenchReads {
  /** What the service is, and where it listens. */
  readonly health: ApiRead<Health>
  /** Where the service wrote the session token. */
  readonly session: ApiRead<string>
  /** Every task in this workspace's store. */
  readonly tasks: ApiRead<Task[]>
  /** The task, its runs, its stages, its artefacts and its approvals. */
  readonly state: ApiRead<TaskState>
  /** The declared workflow and how far this task has got through it. */
  readonly plan: ApiRead<TaskPlan>
  /** The runtime stages the store holds. */
  readonly steps: ApiRead<TaskStep[]>
  /** The material this task is bound to. */
  readonly sources: ApiRead<SourceView[]>
  /** The artefacts this task has produced. */
  readonly artifacts: ApiRead<ArtifactView[]>
}

/** The workbench's reads, and the way to ask for them again. */
export interface Workbench {
  readonly reads: WorkbenchReads
  /**
   * Read the task again.
   *
   * Called after something has changed. The read happens on the next render,
   * so what the screen shows afterwards is the database's state and not the
   * page's guess at it.
   */
  readonly readAgain: () => void
}

/**
 * Two reads, as one.
 *
 * A panel that draws two things needs one answer about whether the service
 * answered: an error in either is an error, and there is data only when both
 * landed. Without this a panel would have to choose which of its two reads
 * decides whether it is empty, and the one it did not choose would fail
 * silently.
 */
export function combineReads<A, B>(left: ApiRead<A>, right: ApiRead<B>): ApiRead<readonly [A, B]> {
  const error = left.error ?? right.error
  if (error !== null) {
    return { data: null, error }
  }
  if (left.data === null || right.data === null) {
    return { data: null, error: null }
  }
  return { data: [left.data, right.data], error: null }
}

/** A read that has not landed. */
function empty<T>(): ApiRead<T> {
  return { data: null, error: null }
}

/** The reads a workbench shows before the service has answered. */
function emptyReads(): WorkbenchReads {
  return {
    health: empty<Health>(),
    session: empty<string>(),
    tasks: empty<Task[]>(),
    state: empty<TaskState>(),
    plan: empty<TaskPlan>(),
    steps: empty<TaskStep[]>(),
    sources: empty<SourceView[]>(),
    artifacts: empty<ArtifactView[]>(),
  }
}

/** One read, settled: what came back, or why it did not. */
async function settle<T>(read: () => Promise<T>): Promise<ApiRead<T>> {
  try {
    return { data: await read(), error: null }
  } catch (error) {
    return { data: null, error: describeError(error) }
  }
}

/**
 * Every read the workbench draws, in one pass.
 *
 * The service's event stream is not one of them, on purpose: the workbench
 * reads the task's state and reads it again when something changes, and a
 * long-lived stream would be a second way to watch the task move. The reason
 * is in `api/paths.ts`, next to the list of paths that leaves it out.
 */
async function readEverything(client: LabCairnClient): Promise<WorkbenchReads> {
  const [health, session, tasks, state, plan, steps, sources, artifacts] = await Promise.all([
    settle(() => client.get<Health>(API_PATHS.health)),
    settle(() => client.sessionPath()),
    settle(() => client.get<Task[]>(API_PATHS.tasks)),
    settle(() => client.get<TaskState>(API_PATHS.task)),
    settle(() => client.get<TaskPlan>(API_PATHS.plan)),
    settle(() => client.get<TaskStep[]>(API_PATHS.steps)),
    settle(() => client.get<SourceView[]>(API_PATHS.sources)),
    settle(() => client.get<ArtifactView[]>(API_PATHS.artifacts)),
  ])
  return { health, session, tasks, state, plan, steps, sources, artifacts }
}

/**
 * Whether two sets of reads say the same thing.
 *
 * The comparison is over the serialised form, because that is the form the
 * screen shows: two reads that differ only in the order of an object's keys
 * say the same thing, and a difference that is not visible is not a change.
 */
function sameReads(left: WorkbenchReads, right: WorkbenchReads): boolean {
  return JSON.stringify(left) === JSON.stringify(right)
}

/**
 * Read the task, and draw it.
 *
 * @param client the client to read through; the API is the only thing this
 *   page talks to, and the client is what refuses to talk to anything else.
 */
export function useWorkbench(client: LabCairnClient): Workbench {
  const [reads, setReads] = useState<WorkbenchReads>(emptyReads)
  const [, ask] = useReducer((count: number) => count + 1, 0)

  const readAgain = useCallback(() => {
    ask()
  }, [])

  useEffect(() => {
    let live = true
    void readEverything(client).then((next) => {
      if (!live) {
        return
      }
      // Only a change is a render. Without this the read would be its own
      // reason to render, and the page would read the task for ever.
      setReads((previous) => (sameReads(previous, next) ? previous : next))
    })
    return () => {
      live = false
    }
    // No dependency list on purpose: the read is scheduled by the render,
    // not by a change in the inputs. A list here would make the last answer
    // a cached copy, and a cached copy is a second source of truth.
  })

  return { reads, readAgain }
}
