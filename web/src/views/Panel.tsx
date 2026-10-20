/**
 * The frame every view is drawn in.
 *
 * A panel knows three things about the read it draws: it failed, it has not
 * landed, or it has an answer. The first two are stated here rather than in
 * each view, so that a view draws one thing — the data — and the frame says
 * the rest. A view that drew its own empty state would be a view that could
 * say "nothing to show" where the truth is "the service did not answer".
 */

import { useId } from 'react'
import type { JSX, ReactNode } from 'react'

import type { ApiRead } from '../app/useWorkbench'

interface PanelProps<T> {
  /** What the panel is called. */
  readonly title: string
  /** The read the panel draws. */
  readonly read: ApiRead<T>
  /** The answer, once there is one. */
  readonly children: (data: T) => ReactNode
}

export function Panel<T>({ title, read, children }: PanelProps<T>): JSX.Element {
  const headingId = useId()
  return (
    <section className="panel" aria-labelledby={headingId}>
      <h2 className="panel__title" id={headingId}>
        {title}
      </h2>
      {read.error !== null ? (
        <p className="panel__error" role="status">
          The service did not answer this: {read.error.message}
        </p>
      ) : read.data === null ? (
        <p className="panel__pending" role="status">
          Reading…
        </p>
      ) : (
        children(read.data)
      )}
    </section>
  )
}

/**
 * A row of a list, when the list is a list of records.
 *
 * The key is the record's own id where the contract gives one, because a
 * list keyed by its index reorders itself when the list does.
 */
export function RecordList({ children }: { readonly children: ReactNode }): JSX.Element {
  return <ul className="records">{children}</ul>
}
