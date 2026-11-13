/**
 * The version-selection surface: which revision of the report this page shows.
 *
 * **What this panel is.** A report is re-rendered as a new revision, and the
 * receipts the service lists say which revisions exist. This panel lists
 * them and shows the one chosen — the report's own bytes, fetched by the
 * browser from the service's content route, exactly as the artefact preview
 * fetches them. It is a **view** surface: it selects what the reader sees,
 * and the reader can tell the revisions apart by the hashes the receipts
 * carry.
 *
 * **What it is not, said on the panel itself.** The service holds no
 * "current version" pointer: there is no route that stores a selection, so
 * choosing here changes this page's view and nothing else. The panel says
 * that in its own words, because a selection that looked like a write would
 * be the screen claiming what the service does not do. The same honesty
 * names the permission boundary: the content route serves an artefact only
 * where the workspace's policy allows reading it, so the panel shows the
 * service's refusal when it is refused rather than a blank that could be
 * mistaken for an empty report.
 */

import type { JSX } from 'react'
import { useState } from 'react'

import type { ApiRead } from '../app/useWorkbench'
import { reportVersions } from '../app/versions'
import type { ArtifactView } from '../api/generated'
import { ArtifactPreview } from './ArtifactPreview'
import { Panel, RecordList } from './Panel'

interface VersionSelectProps {
  /** The artefacts this task has produced. */
  readonly artifacts: ApiRead<ArtifactView[]>
}

export function VersionSelect({ artifacts }: VersionSelectProps): JSX.Element {
  const [chosen, setChosen] = useState<number | null>(null)

  return (
    <Panel title="Version select" read={artifacts}>
      {(data) => {
        const versions = reportVersions(data)
        // The latest revision is the default view, and the default is read
        // from the receipts rather than remembered: a reload that finds more
        // revisions shows the newest of what the service now lists.
        const numbers = versions.map((version) => version.revision)
        const shown = chosen !== null && numbers.includes(chosen) ? chosen : Math.max(...numbers)
        const current = versions.find((version) => version.revision === shown)
        return (
          <>
            <p className="panel__note">
              The report&rsquo;s revisions, each listed by the receipts the service holds. Choosing
              one changes what this page shows; the service holds no &ldquo;current version&rdquo;
              of its own, and nothing is written by choosing.
            </p>
            {versions.length === 0 ? (
              <p className="panel__status">The task has produced no report yet.</p>
            ) : (
              <>
                <RecordList>
                  {versions.map((version) => {
                    const document = version.receipts.find(
                      (view) => !view.receipt.media_type?.startsWith('image/'),
                    )
                    return (
                      <li className="record record--version" key={version.revision}>
                        <span className="record__name">revision {version.revision}</span>
                        {version.revision === shown ? (
                          <span className="record__flag">shown</span>
                        ) : (
                          <button
                            className="button"
                            type="button"
                            onClick={() => {
                              setChosen(version.revision)
                            }}
                          >
                            Show
                          </button>
                        )}
                        <span className="record__detail">
                          {version.receipts.length} file{version.receipts.length === 1 ? '' : 's'}
                        </span>
                        {document !== undefined ? (
                          <span className="record__detail">
                            sha256 {document.receipt.content_sha256}
                          </span>
                        ) : null}
                      </li>
                    )
                  })}
                </RecordList>
                {current !== undefined ? (
                  <div className="version__preview">
                    {current.receipts
                      .filter((view) => view.receipt.media_type !== null)
                      .map((view) => (
                        <div className="version__form" key={view.receipt.receipt_id}>
                          <h3 className="panel__subtitle">{view.receipt.relative_path}</h3>
                          <ArtifactPreview
                            receipt={view.receipt}
                            label={`Revision ${current.revision}: ${view.receipt.relative_path}`}
                          />
                        </div>
                      ))}
                  </div>
                ) : null}
              </>
            )}
          </>
        )
      }}
    </Panel>
  )
}
