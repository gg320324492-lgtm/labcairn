/**
 * The source anchors: the material this task is bound to, and the key each
 * piece of material is addressed by.
 *
 * **What an anchor is here.** `docs/ARCHITECTURE.md` says a `SourceAnchor`
 * *"precisely locates source material with a content hash"*, and the two
 * things a reader needs in order to point at a piece of material are the
 * hash that identifies it and the key it is addressed by. The contract
 * carries both: the source's own `content_sha256` and the `resource_key`
 * the material has **in its own root** — which is not the workspace-
 * relative path, and is the key a policy rule is matched against.
 *
 * The contract exposes no separate list of anchors, and this view does not
 * invent one: it draws the material and the two facts that locate it.
 */

import type { JSX } from 'react'

import type { ApiRead } from '../app/useWorkbench'
import type { SourceView } from '../api/generated'
import { Panel, RecordList } from './Panel'

interface SourcesViewProps {
  /** The material this task is bound to, in the order it bound them. */
  readonly sources: ApiRead<SourceView[]>
}

export function SourcesView({ sources }: SourcesViewProps): JSX.Element {
  return (
    <Panel title="Source anchors" read={sources}>
      {(data) => (
        <>
          <p className="panel__note">
            The material this task is bound to. A task binds by content hash, not by path: a path
            moves, a content hash does not.
          </p>
          <RecordList>
            {data.map((view) => (
              <li className="record" key={view.source.source_id}>
                <span className="record__name">{view.source.display_name}</span>
                <span className="record__flag">{view.source.kind}</span>
                <span className="record__detail">anchor key {view.resource_key}</span>
                <span className="record__detail">path {view.source.relative_path}</span>
                <span className="record__detail">sha256 {view.source.content_sha256}</span>
                <span className="record__detail">{view.source.size_bytes} bytes</span>
                {view.source.readability !== undefined ? (
                  <span className="record__detail">readability {view.source.readability}</span>
                ) : null}
                {view.source.readability_disclosure !== undefined &&
                view.source.readability_disclosure !== null ? (
                  <span className="record__detail">{view.source.readability_disclosure}</span>
                ) : null}
                {(view.source.identifiers ?? []).map((identifier) => (
                  <span className="record__detail" key={`${identifier.kind}:${identifier.value}`}>
                    {identifier.kind} {identifier.value}
                  </span>
                ))}
              </li>
            ))}
          </RecordList>
        </>
      )}
    </Panel>
  )
}
