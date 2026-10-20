/**
 * The revisions: what a path has been through.
 *
 * A report is re-rendered when the material under it changes, and each
 * rendering is a **new revision** — v1 is never altered. So the interesting
 * question about a path is not "what is it" but "what has it been", and this
 * view groups the artefacts by the path they occupy and shows each
 * revision's own hash, size and standing.
 *
 * **The standing is on the receipt, not on the file.** A file does not watch
 * itself, so a reader who opens a report on disk cannot tell from the file
 * that the material under it has changed. The receipt can, and that is what
 * this view draws.
 */

import type { JSX } from 'react'

import type { ApiRead } from '../app/useWorkbench'
import type { ArtifactView } from '../api/generated'
import { Panel, RecordList } from './Panel'

interface RevisionsViewProps {
  /** The artefacts this task has produced. */
  readonly artifacts: ApiRead<ArtifactView[]>
}

/** The artefacts grouped by the path they occupy, in the order they arrived. */
function groupByPath(artifacts: ArtifactView[]): Map<string, ArtifactView[]> {
  const groups = new Map<string, ArtifactView[]>()
  for (const artefact of artifacts) {
    const path = artefact.receipt.relative_path
    const group = groups.get(path)
    if (group === undefined) {
      groups.set(path, [artefact])
    } else {
      group.push(artefact)
    }
  }
  return groups
}

export function RevisionsView({ artifacts }: RevisionsViewProps): JSX.Element {
  return (
    <Panel title="Revisions" read={artifacts}>
      {(data) => {
        const groups = groupByPath(data)
        return (
          <>
            <p className="panel__note">
              What each path has been through. A re-rendering is a new revision; an earlier revision
              is never altered.
            </p>
            {groups.size === 0 ? (
              <p className="panel__status">Nothing has been produced yet.</p>
            ) : null}
            {[...groups.entries()].map(([path, revisions]) => (
              <div className="revisions__group" key={path}>
                <h3 className="panel__subtitle">{path}</h3>
                <RecordList>
                  {revisions.map((artefact) => (
                    <li className="record" key={artefact.receipt.receipt_id}>
                      <span className="record__name">
                        revision {artefact.receipt.revision ?? 1}
                      </span>
                      <span className="record__detail">
                        sha256 {artefact.receipt.content_sha256}
                      </span>
                      <span className="record__detail">{artefact.receipt.size_bytes} bytes</span>
                      <span className="record__detail">made {artefact.receipt.created_at}</span>
                      {artefact.receipt.staleness !== undefined ? (
                        <span
                          className={`record__flag record__flag--${artefact.receipt.staleness}`}
                        >
                          {artefact.receipt.staleness}
                        </span>
                      ) : null}
                      {artefact.receipt.staleness_reason !== undefined &&
                      artefact.receipt.staleness_reason !== null ? (
                        <span className="record__detail">{artefact.receipt.staleness_reason}</span>
                      ) : null}
                    </li>
                  ))}
                </RecordList>
              </div>
            ))}
          </>
        )
      }}
    </Panel>
  )
}
