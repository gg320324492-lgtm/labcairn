/**
 * The artefacts and their preview.
 *
 * **The receipt is the record; the preview is the artefact.** This view draws
 * what the service holds about each artefact — its kind, its path, its hash,
 * its size, its lineage and whether it has gone stale — and then shows the
 * artefact's own bytes. It does not draw the report's claims: the report's
 * wording is drawn once, by the report, and a panel that composed a second
 * wording from the same material would be a second voice for it.
 *
 * **A report is shown with its limit.** The workbench must not hide that
 * every export is a first-pass report and not journal-ready, so a report
 * artefact carries the notice, and its preview is the report's own face —
 * where the report says the same thing in the report's own words.
 */

import type { JSX } from 'react'

import type { ApiRead } from '../app/useWorkbench'
import type { ArtifactView } from '../api/generated'
import { REPORT_FIRST_PASS_NOTICE } from '../report/firstPassNotice'
import { ArtifactPreview } from './ArtifactPreview'
import { Panel, RecordList } from './Panel'

interface ArtefactsViewProps {
  /** The artefacts this task has produced. */
  readonly artifacts: ApiRead<ArtifactView[]>
}

export function ArtefactsView({ artifacts }: ArtefactsViewProps): JSX.Element {
  return (
    <Panel title="Artefacts" read={artifacts}>
      {(data) => (
        <>
          <p className="panel__note">
            What this task has produced. The preview is the artefact&rsquo;s own bytes, served by
            the local service.
          </p>
          {data.length === 0 ? (
            <p className="panel__status">Nothing has been produced yet.</p>
          ) : null}
          <RecordList>
            {data.map((view) => (
              <li className="record record--artefact" key={view.receipt.receipt_id}>
                <span className="record__name">{view.receipt.relative_path}</span>
                <span className="record__flag">{view.receipt.kind}</span>
                <span className="record__detail">sha256 {view.receipt.content_sha256}</span>
                <span className="record__detail">{view.receipt.size_bytes} bytes</span>
                {view.receipt.revision !== undefined ? (
                  <span className="record__detail">revision {view.receipt.revision}</span>
                ) : null}
                <span className="record__detail">
                  made by {view.receipt.produced_by} {view.receipt.producer_id}
                </span>
                {view.receipt.staleness !== undefined ? (
                  <span className={`record__flag record__flag--${view.receipt.staleness}`}>
                    {view.receipt.staleness}
                  </span>
                ) : null}
                {view.receipt.staleness_reason !== undefined &&
                view.receipt.staleness_reason !== null ? (
                  <span className="record__detail">{view.receipt.staleness_reason}</span>
                ) : null}
                {view.receipt.kind === 'report' ? (
                  <p className="record__notice">{REPORT_FIRST_PASS_NOTICE}</p>
                ) : null}
                <ArtifactPreview receipt={view.receipt} />
              </li>
            ))}
          </RecordList>
        </>
      )}
    </Panel>
  )
}
