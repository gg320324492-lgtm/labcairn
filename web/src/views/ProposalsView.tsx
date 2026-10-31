/**
 * The proposals: the model's answer, and the person's verdict on it.
 *
 * **Whose words each thing is, is the whole point of this panel.** The
 * ledger's records say who wrote them — `created_by` says whether a person,
 * a rule or a model wrote it, and `created_by_id` says which — so the panel
 * draws a model's proposal beside the person's own record and keeps the two
 * apart. **A merged view that blurred them would be the second spelling this
 * work order exists to avoid**, and a reader would believe it.
 *
 * **Which one a report may cite.** A model's proposal is never promoted to
 * a person's word: the service keeps the proposal as the record of what was
 * claimed, and the person's own record stands beside it. So the panel says
 * which of the two a report may cite, and it says it because the record
 * says whose words it is.
 *
 * **How the two are found.** The proposal names the record that replaced it
 * in `superseded_by`, and that is the only link the contract carries — so
 * the panel follows it and does not pair them by their text, their anchor
 * or their order. A record the panel has already drawn beside its proposal
 * is not drawn a second time under its own heading.
 *
 * **What the panel does not draw.** The record carries no score, no weight
 * and no report's own verdict, so the panel draws none; and a record the
 * ledger holds that is neither a proposal nor a person's word beside one is
 * drawn as a record of its own, under its own heading, rather than folded
 * into a pair it does not belong to.
 *
 * **The panel offers no act, and that is a gap.** The ledger's door that
 * settles a proposal — the one a person answers a model's question with — is
 * a console command, and **the contract carries no route for it**: the
 * service serves `GET /records` and nothing that changes a record's
 * standing. So this panel draws the settlement and the person who made it,
 * and asks for nothing. The route that would open the door from the
 * workbench does not exist yet, and writing that here is better than letting
 * a reader wonder whether the panel forgot it.
 */

import type { JSX } from 'react'

import type { ApiRead } from '../app/useWorkbench'
import type { EvidenceRecord, VerificationRecord } from '../api/generated'
import { API_PATHS } from '../api/paths'
import { Panel, RecordList } from './Panel'
import { asApiRead, usePanelRead } from './usePanelRead'

/** What a record is called, by whose words it is. */
function whoseWords(record: EvidenceRecord): string {
  if (record.created_by === 'model_proposal') {
    return 'the model'
  }
  if (record.created_by === 'user') {
    return 'the person'
  }
  return 'the rule'
}

/**
 * What a report may do with a record, in the service's own rule.
 *
 * **The rule is about whose words the record carries.** A model's proposal
 * is never promoted to a person's word, so a report may cite the person's
 * record and not the model's proposal. The panel says this only where the
 * record's own creator settles it, and says nothing where it does not.
 */
function citability(record: EvidenceRecord): JSX.Element | null {
  if (record.created_by === 'user') {
    return (
      <span className="record__detail">
        a report may cite this one: the words are a person&rsquo;s
      </span>
    )
  }
  if (record.created_by === 'model_proposal') {
    return (
      <span className="record__detail">
        a report may not cite this one: the words are a model&rsquo;s
      </span>
    )
  }
  return null
}

/** One verification entry, as the ledger recorded it. */
function VerificationRow({ entry }: { readonly entry: VerificationRecord }): JSX.Element {
  return (
    <li className="record">
      <span className="record__name">{entry.check}</span>
      <span className={`record__flag record__flag--${entry.outcome}`}>{entry.outcome}</span>
      <span className="record__detail">
        by {entry.checker_id} at {entry.checked_at}
      </span>
      <span className="record__detail">{entry.detail}</span>
    </li>
  )
}

/** One record, with the fields the contract carries for it. */
function RecordBody({
  record,
  label,
}: {
  readonly record: EvidenceRecord
  /** What the panel calls this record, by whose words it is. */
  readonly label: string
}): JSX.Element {
  const log = record.verification_log ?? []
  const anchors = record.anchor_ids ?? []
  return (
    <li className="record record--artefact">
      <span className="record__name">{label}</span>
      <span className="record__flag">{record.created_by}</span>
      <span className="record__detail">written by {record.created_by_id}</span>
      <span className="record__detail">status {record.status}</span>
      <span className="record__detail">kind {record.kind}</span>
      <span className="record__detail">record {record.evidence_id}</span>
      {record.text !== null ? <span className="record__detail">text {record.text}</span> : null}
      {record.value !== undefined && record.value !== null ? (
        <span className="record__detail">value {record.value}</span>
      ) : null}
      {record.unit !== undefined && record.unit !== null ? (
        <span className="record__detail">unit {record.unit}</span>
      ) : null}
      {record.tolerance !== undefined && record.tolerance !== null ? (
        <span className="record__detail">tolerance {record.tolerance}</span>
      ) : null}
      <span className="record__detail">
        anchors {anchors.length === 0 ? 'none' : anchors.join(', ')}
      </span>
      {record.extracted_span !== undefined && record.extracted_span !== null ? (
        <span className="record__detail">span {record.extracted_span}</span>
      ) : null}
      <span className="record__detail">created at {record.created_at}</span>
      {record.superseded_by !== undefined && record.superseded_by !== null ? (
        <span className="record__detail">superseded by {record.superseded_by}</span>
      ) : null}
      {citability(record)}
      {log.length === 0 ? null : (
        <RecordList>
          {log.map((entry) => (
            <VerificationRow
              entry={entry}
              key={`${entry.check}|${entry.checked_at}|${entry.checker_id}|${entry.outcome}`}
            />
          ))}
        </RecordList>
      )}
    </li>
  )
}

/**
 * The records the ledger holds, and the proposals among them.
 *
 * **The proposals are the model's records, and nothing else is.** A record a
 * person wrote is a claim of their own, and a rule's record is the rule's:
 * neither is a proposal, and neither is drawn as one.
 */
function split(records: EvidenceRecord[]): {
  readonly proposals: EvidenceRecord[]
  readonly others: EvidenceRecord[]
} {
  const proposals: EvidenceRecord[] = []
  const others: EvidenceRecord[] = []
  // The records the proposals were settled by, in one pass: a record the
  // panel draws beside its proposal is not drawn again under its own
  // heading, and the order the ledger answered in does not decide that.
  const settled = new Set<string>()
  for (const record of records) {
    if (
      record.created_by === 'model_proposal' &&
      record.superseded_by !== undefined &&
      record.superseded_by !== null
    ) {
      settled.add(record.superseded_by)
    }
  }
  for (const record of records) {
    if (record.created_by === 'model_proposal') {
      proposals.push(record)
    } else if (!settled.has(record.evidence_id)) {
      others.push(record)
    }
  }
  return { proposals, others }
}

interface ProposalsViewProps {
  /**
   * The workbench's cycle.
   *
   * **The panel reads again when the workbench reads again**, so a proposal
   * the roles wrote after the panel last looked is on the screen when the
   * page refreshes rather than only after a reload.
   */
  readonly cycle: number
}

export function ProposalsView({ cycle }: ProposalsViewProps): JSX.Element {
  const records = usePanelRead<EvidenceRecord[]>(API_PATHS.records, cycle)
  const panel: ApiRead<EvidenceRecord[]> = asApiRead(records)
  return (
    <Panel title="Proposals" read={panel}>
      {(data) => {
        const { proposals, others } = split(data)
        const byId = new Map(data.map((record) => [record.evidence_id, record]))
        return (
          <>
            <p className="panel__note">
              The ledger&rsquo;s records, each labelled with whose words it is. A report may cite a
              person&rsquo;s record and not a model&rsquo;s proposal: the service keeps the proposal
              as the record of what was claimed, and the person&rsquo;s own record stands beside it.
            </p>
            {proposals.length === 0 ? (
              <p className="panel__status">The ledger holds no model&rsquo;s proposal.</p>
            ) : null}
            {proposals.map((proposal) => {
              const superseded = proposal.superseded_by ?? null
              const verdict = superseded === null ? null : (byId.get(superseded) ?? null)
              return (
                <div key={proposal.evidence_id}>
                  <h3 className="panel__subtitle">Proposal {proposal.evidence_id}</h3>
                  <ul className="records proposals__pair">
                    <RecordBody label={`${whoseWords(proposal)}\u2019s answer`} record={proposal} />
                    {verdict === null ? (
                      <li className="panel__status">
                        {superseded === null
                          ? 'No record supersedes this proposal, so no person\u2019s word stands beside it.'
                          : 'The record this proposal was superseded by is not among the records the service returned.'}
                      </li>
                    ) : (
                      <RecordBody
                        label={`${whoseWords(verdict)}\u2019s verdict`}
                        record={verdict}
                      />
                    )}
                  </ul>
                </div>
              )
            })}
            {others.length === 0 ? null : (
              <>
                <h3 className="panel__subtitle">Records that are not proposals</h3>
                <RecordList>
                  {others.map((record) => (
                    <RecordBody
                      key={record.evidence_id}
                      label={`${whoseWords(record)}\u2019s record`}
                      record={record}
                    />
                  ))}
                </RecordList>
              </>
            )}
          </>
        )
      }}
    </Panel>
  )
}
