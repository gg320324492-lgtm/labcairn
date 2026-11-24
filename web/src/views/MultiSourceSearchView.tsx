/**
 * The multi-source search: one question, asked of every index the service
 * holds, and each source's answer drawn beside its own provenance.
 *
 * **Three sources, and each is its own read.** The trajectory, the slide
 * decks and the meeting texts are three indexes with three routes, and the
 * panel asks each of them the same question. They are read independently on
 * purpose: one source failing is that source's answer — a service that lost
 * its meeting index has not lost its trajectory — and a panel that merged
 * the three into one request would have to fail all three together, which
 * is a claim the service never made.
 *
 * **The question is the panel's own, and an empty one is not asked.** The
 * search routes require at least one character, so a query that is only
 * spaces is refused here, in the panel's own words, and no request leaves
 * the page. A reader who sees no results then knows it is because nothing
 * was asked, not because the indexes are empty.
 *
 * **A hit says what it found and where it came from, and the two are drawn
 * as they arrive.** The contract carries the located text and the locator
 * that addresses it — the trajectory's own `source_locator` string, and the
 * deck and meeting indexes' `locator_json` beside their typed fields. The
 * panel does not rebuild a locator the service already wrote: it draws the
 * service's words, and a locator it cannot read is shown from the typed
 * fields rather than replaced with a guess.
 *
 * **What the panel does not decide.** It does not rank across the sources,
 * because the service ranks within each and the three answers are not one
 * list; and it does not filter the hits, because what matched is the
 * service's answer, not this page's opinion of it.
 */

import { useId, useState } from 'react'
import type { JSX } from 'react'

import type {
  MeetingHit,
  MeetingTextIngested,
  PptDeckIngested,
  PptHit,
  TrajectoryHit,
} from '../api/generated'
import { api, describeError } from '../api/client'
import {
  API_PATHS,
  meetingIngestBody,
  meetingSearchPath,
  pptIngestBody,
  pptSearchPath,
  trajectorySearchPath,
} from '../api/paths'
import { Panel, RecordList } from './Panel'
import type { PanelRead } from './usePanelRead'
import { usePanelRead } from './usePanelRead'

/** How many hits one source is asked for: a page's worth, not the index. */
const SOURCE_LIMIT = 20

/** One hit, drawn as the panel draws it: what matched, and where it came from. */
interface DrawnHit {
  /** The text the index matched. */
  readonly text: string
  /** The locator the service wrote for the text. */
  readonly locator: string
}

/**
 * What one source's answer is, in the panel's own words.
 *
 * **The idle state is the panel's, and the other three are the read's.** A
 * source with no question yet has neither failed nor landed, and the panel
 * says so rather than drawing an empty list that would read as "no hits".
 */
type SourceAnswer =
  | { readonly kind: 'idle' }
  | { readonly kind: 'pending' }
  | { readonly kind: 'hits'; readonly hits: readonly DrawnHit[] }
  | { readonly kind: 'failed'; readonly message: string }

/** One source's subsection: its name, what it holds, and its answer. */
function SourceBlock({
  title,
  note,
  answer,
}: {
  readonly title: string
  readonly note: string
  readonly answer: SourceAnswer
}): JSX.Element {
  return (
    <section aria-label={title}>
      {/* The source's name is a label, not a second panel heading: the
          panel's title is the section's own, and a second heading of the
          same name would be a second "Trajectory" on one page. */}
      <p className="panel__subtitle">{title}</p>
      <p className="panel__note">{note}</p>
      {answer.kind === 'idle' ? (
        <p className="panel__status">No question has been asked yet.</p>
      ) : answer.kind === 'pending' ? (
        <p className="panel__pending" role="status">
          Searching…
        </p>
      ) : answer.kind === 'failed' ? (
        <p className="panel__error" role="status">
          The service did not answer this source: {answer.message}
        </p>
      ) : answer.hits.length === 0 ? (
        <p className="panel__status">Nothing in this index matched.</p>
      ) : (
        <RecordList>
          {answer.hits.map((hit, index) => (
            <li className="record record--artefact" key={`${index}|${hit.text}`}>
              <span className="record__name">{hit.text}</span>
              <span className="record__detail">{hit.locator}</span>
            </li>
          ))}
        </RecordList>
      )}
    </section>
  )
}

/** The text a trajectory hit matched: what was said, or what changed. */
function trajectoryText(hit: TrajectoryHit): string {
  return hit.comment_text ?? hit.change_text ?? hit.anchor_text ?? 'an entry with no text'
}

/**
 * The trajectory's locator, as the service wrote it.
 *
 * **The string is the provenance.** The contract carries `source_locator`
 * whole — `paragraph:2:start:12:end:40` for an anchored comment,
 * `comment:fb-method` for one that was never anchored — and the panel draws
 * it as it is, because a locator reworded here would be a second spelling
 * of the one the service resolves against the chain. The anchor the comment
 * was located at travels beside it, because it is part of the same answer.
 */
function trajectoryLocator(hit: TrajectoryHit): string {
  const parts: string[] = []
  if (hit.entry_kind === 'comment') {
    parts.push(hit.feedback_id === null ? 'comment' : `comment ${hit.feedback_id}`)
    if (hit.issue_key !== null) {
      parts.push(`issue ${hit.issue_key}`)
    }
    if (hit.anchor_text !== null) {
      parts.push(
        hit.anchor_paragraph === null
          ? `anchored at "${hit.anchor_text}"`
          : `anchored at "${hit.anchor_text}" (paragraph ${hit.anchor_paragraph})`,
      )
    }
  } else {
    parts.push(hit.edit_action_id === null ? 'edit' : `edit ${hit.edit_action_id}`)
    if (hit.change_kind !== null) {
      parts.push(hit.change_kind)
    }
  }
  parts.push(`at ${hit.source_locator}`)
  return parts.join(' — ')
}

/** The text a deck hit matched: the object's own words. */
function pptText(hit: PptHit): string {
  return hit.text
}

/**
 * One deck object's locator, read out of the JSON the service wrote.
 *
 * **The JSON is the service's locator, and the typed fields are the same
 * facts.** The contract carries both — `locator_json` and the slide, the
 * position and the kind beside it — so the panel reads the JSON where it
 * can and falls back to the typed fields where it cannot: a locator the
 * panel could not read at all would be provenance the reader could not
 * check. The object's kind is part of the address, because a title and a
 * note on the same slide are different things a reader may want to tell
 * apart.
 */
function pptLocator(hit: PptHit): string {
  const parts: string[] = [`slide ${hit.slide_no}`]
  const parsed = parseLocator(hit.locator_json)
  const position = numberAt(parsed, 'position') ?? hit.object_position
  const kind = textAt(parsed, 'object_kind') ?? hit.object_kind
  if (Number.isFinite(position)) {
    parts.push(`position ${String(position)}`)
  }
  if (kind !== null && kind !== '') {
    parts.push(`a ${kind}`)
  }
  return parts.join(' — ')
}

/** The text a meeting hit matched: the record's own words. */
function meetingText(hit: MeetingHit): string {
  return hit.text
}

/**
 * One meeting record's locator, read out of the JSON the service wrote.
 *
 * **The record's shape is part of the address.** A timestamped entry and an
 * organised paragraph are indexed by the same route and addressed
 * differently — the timestamp when the container has one, the record's
 * index in either case — so the locator names the shape as well as the
 * place.
 */
function meetingLocator(hit: MeetingHit): string {
  const parts: string[] = [hit.record_format === '' ? 'record' : `a ${hit.record_format}`]
  const parsed = parseLocator(hit.locator_json)
  const timestamp = textAt(parsed, 'timestamp') ?? hit.timestamp_label
  if (timestamp !== null && timestamp !== '') {
    parts.push(`at ${timestamp}`)
  }
  parts.push(`record ${hit.record_index}`)
  return parts.join(' — ')
}

/** The JSON the service wrote, when it is an object this panel can read. */
function parseLocator(locatorJson: string): Record<string, unknown> {
  try {
    const parsed: unknown = JSON.parse(locatorJson)
    if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>
    }
    return {}
  } catch {
    return {}
  }
}

/** One locator field's text, when the service wrote it as text. */
function textAt(locator: Record<string, unknown>, field: string): string | null {
  const value = locator[field]
  return typeof value === 'string' ? value : null
}

/** One locator field's number, when the service wrote it as a number. */
function numberAt(locator: Record<string, unknown>, field: string): number | null {
  const value = locator[field]
  return typeof value === 'number' ? value : null
}

/**
 * One source's read, drawn as the panel's own answer.
 *
 * **The read's states are kept, and the hits are drawn from the contract's
 * fields.** The panel does not merge the sources here: each answer is this
 * source's, and a source that failed is shown as failed while the others
 * stand.
 */
function sourceAnswer<T>(
  read: PanelRead<T[]>,
  textOf: (hit: T) => string,
  locatorOf: (hit: T) => string,
): SourceAnswer {
  if (read.kind === 'idle') {
    return { kind: 'idle' }
  }
  if (read.kind === 'pending') {
    return { kind: 'pending' }
  }
  if (read.kind === 'failed') {
    return { kind: 'failed', message: read.error.message }
  }
  return {
    kind: 'hits',
    hits: read.data.map((hit) => ({ text: textOf(hit), locator: locatorOf(hit) })),
  }
}

/**
 * What one ingest is doing, in the panel's own words.
 *
 * **The idle state is the panel's.** A source that has not been asked to
 * index anything has neither failed nor landed, and the panel says so rather
 * than drawing a success nobody earned. The other three are the write's: a
 * request in flight, the service's count of what it indexed, and a refusal
 * or failure carrying the service's own words.
 */
type IngestState =
  | { readonly kind: 'idle' }
  | { readonly kind: 'pending' }
  | { readonly kind: 'done'; readonly summary: string }
  | { readonly kind: 'failed'; readonly message: string }

/** The fields one ingest asks for, in the form's own words. */
interface IngestInputs {
  /** The paper project the material is bound to. */
  readonly projectId: string
  /** The workspace root the material stands in. */
  readonly rootId: string
  /** The material's key inside its root. */
  readonly resourceKey: string
}

/**
 * The ingest form's three fields, shared by both sources.
 *
 * **The form is one set of fields, not two.** Both ingests take the same
 * three names — project, root, resource key — and the button the operator
 * clicks decides which route reads them. A shared form is the honest
 * drawing of that: the names are the material's, and the source is the
 * operator's choice.
 */
function IngestForm({
  onIngest,
  state,
  label,
  buttonLabel,
  busyLabel,
  fieldId,
}: {
  readonly onIngest: (inputs: IngestInputs) => void
  readonly state: IngestState
  readonly label: string
  readonly buttonLabel: string
  readonly busyLabel: string
  readonly fieldId: (name: string) => string
}): JSX.Element {
  const [projectId, setProjectId] = useState('')
  const [rootId, setRootId] = useState('')
  const [resourceKey, setResourceKey] = useState('')
  const [submitted, setSubmitted] = useState<IngestInputs | null>(null)

  const ready = projectId.trim() !== '' && rootId.trim() !== '' && resourceKey.trim() !== ''

  const submit = (): void => {
    if (!ready) {
      return
    }
    const inputs: IngestInputs = {
      projectId: projectId.trim(),
      rootId: rootId.trim(),
      resourceKey: resourceKey.trim(),
    }
    setSubmitted(inputs)
    onIngest(inputs)
  }

  return (
    <section aria-label={label} className="figure-form">
      <label htmlFor={fieldId('project')}>
        Project id
        <input
          id={fieldId('project')}
          value={projectId}
          onChange={(event) => {
            setProjectId(event.target.value)
          }}
        />
      </label>
      <label htmlFor={fieldId('root')}>
        Root id
        <input
          id={fieldId('root')}
          value={rootId}
          onChange={(event) => {
            setRootId(event.target.value)
          }}
        />
      </label>
      <label htmlFor={fieldId('resource')}>
        Resource key
        <input
          id={fieldId('resource')}
          value={resourceKey}
          onChange={(event) => {
            setResourceKey(event.target.value)
          }}
        />
      </label>
      <p className="panel__actions">
        <button className="button" type="button" disabled={!ready} onClick={submit}>
          {buttonLabel}
        </button>
      </p>
      {state.kind === 'idle' ? (
        <p className="panel__status">
          {submitted === null
            ? 'Nothing has been indexed from this form yet.'
            : 'The request has been sent.'}
        </p>
      ) : state.kind === 'pending' ? (
        <p className="panel__pending" role="status">
          {busyLabel}
        </p>
      ) : state.kind === 'failed' ? (
        <p className="panel__error" role="alert">
          The service refused this ingest: {state.message}
        </p>
      ) : (
        <p className="panel__status" role="status">
          {state.summary}
        </p>
      )}
    </section>
  )
}

interface MultiSourceSearchViewProps {
  /**
   * The workbench's cycle.
   *
   * **The panel reads again when the workbench reads again**, so material
   * ingested elsewhere is searchable when the page refreshes rather than
   * only after a reload.
   */
  readonly cycle: number
  /**
   * Ask the workbench to read again.
   *
   * **An ingest changes what the searches can find**, so the panel asks the
   * workbench to re-read after one lands — the same hand the panel's own
   * writes elsewhere use. Without it, the searches would answer from the
   * cycle the ingest began in, and a hit the deck now holds would wait for
   * some other panel's write before it appeared.
   */
  readonly onChanged?: () => void
}

export function MultiSourceSearchView({
  cycle,
  onChanged,
}: MultiSourceSearchViewProps): JSX.Element {
  const [query, setQuery] = useState('')
  const [asked, setAsked] = useState<string | null>(null)
  const [pptIngest, setPptIngest] = useState<IngestState>({ kind: 'idle' })
  const [meetingIngest, setMeetingIngest] = useState<IngestState>({ kind: 'idle' })
  const headingId = useId()
  const field = (name: string): string => `${headingId}-${name}`

  // The three reads stand or fall separately, because they are three routes.
  // An empty query is no question at all: the panel refuses it here rather
  // than asking a route that will refuse it there.
  const trimmed = asked?.trim() ?? ''
  const question = trimmed === '' ? null : { q: trimmed, limit: SOURCE_LIMIT }
  const trajectory = usePanelRead<TrajectoryHit[]>(
    question === null ? null : trajectorySearchPath(question),
    cycle,
  )
  const ppt = usePanelRead<PptHit[]>(question === null ? null : pptSearchPath(question), cycle)
  const meeting = usePanelRead<MeetingHit[]>(
    question === null ? null : meetingSearchPath(question),
    cycle,
  )

  const ask = (): void => {
    setAsked(query)
  }

  /**
   * Index one deck, and say what the service indexed.
   *
   * **The count is the service's, and so are its limits.** The answer
   * carries how many objects were indexed and how many limitations were
   * recorded — a chart the reader does not parse is a disclosure, not a
   * silence — so the summary draws both. A refusal is drawn with the
   * service's reason, and nothing is invented to look like success.
   */
  const ingestDeck = (inputs: IngestInputs): void => {
    setPptIngest({ kind: 'pending' })
    void api
      .post<PptDeckIngested>(API_PATHS.pptIngest, pptIngestBody(inputs))
      .then((answer) => {
        setPptIngest({
          kind: 'done',
          summary:
            `Indexed ${answer.objects_indexed} objects (${answer.title_objects} title, ` +
            `${answer.body_objects} body, ${answer.notes_objects} notes, ` +
            `${answer.table_objects} table, ${answer.image_objects} image) from the deck; ` +
            `${answer.limitations_recorded} limitation(s) recorded.`,
        })
        onChanged?.()
      })
      .catch((error: unknown) => {
        setPptIngest({ kind: 'failed', message: describeError(error).message })
      })
  }

  /**
   * Index one meeting container, and say what the service indexed.
   *
   * **The record's shape is part of the count.** The answer separates the
   * timestamped entries from the organised paragraphs, because the two are
   * addressed differently, and the limitations are the cues the reader
   * could not time — disclosed, never smoothed over.
   */
  const ingestMeeting = (inputs: IngestInputs): void => {
    setMeetingIngest({ kind: 'pending' })
    void api
      .post<MeetingTextIngested>(API_PATHS.meetingIngest, meetingIngestBody(inputs))
      .then((answer) => {
        setMeetingIngest({
          kind: 'done',
          summary:
            `Indexed ${answer.records_indexed} records (${answer.entry_records} entries, ` +
            `${answer.paragraph_records} paragraphs) from the container; ` +
            `${answer.limitations_recorded} limitation(s) recorded.`,
        })
        onChanged?.()
      })
      .catch((error: unknown) => {
        setMeetingIngest({ kind: 'failed', message: describeError(error).message })
      })
  }

  return (
    <Panel title="Multi-source search" read={{ data: true, error: null }}>
      {() => (
        <>
          <p className="panel__note">
            One question, asked of every index the service holds: the advisor&rsquo;s trajectory,
            the slide decks and the meeting texts. Each source answers for itself, with the text it
            matched and the locator that says where it came from — so a hit can be traced to its
            version, its slide or its record without leaving the page.
          </p>
          <div className="figure-form">
            <label htmlFor={field('query')}>
              Search for
              <input
                id={field('query')}
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value)
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    ask()
                  }
                }}
              />
            </label>
          </div>
          <p className="panel__actions">
            <button className="button" type="button" onClick={ask}>
              Search the sources
            </button>
          </p>
          {trimmed === '' ? (
            <p className="panel__status">Nothing has been asked yet: name what to search for.</p>
          ) : null}
          <SourceBlock
            title="Trajectory"
            note="What the advisor said and what changed in answer, each at its own address in the chain."
            answer={sourceAnswer(trajectory, trajectoryText, trajectoryLocator)}
          />
          <SourceBlock
            title="Slide decks"
            note="What a slide or its notes say, at its slide and position in the deck."
            answer={sourceAnswer(ppt, pptText, pptLocator)}
          />
          <SourceBlock
            title="Meeting texts"
            note="What a transcript entry or an organised paragraph says, at its record in the container."
            answer={sourceAnswer(meeting, meetingText, meetingLocator)}
          />
          <h3 className="panel__subtitle">Index new material</h3>
          <p className="panel__note">
            Ask the service to read a deck or a meeting container from the workspace and write its
            objects into the search index. The body names where to read; the bytes come from the
            workspace, through the same gate every reader uses.
          </p>
          <IngestForm
            label="Ingest a slide deck"
            buttonLabel="Ingest the deck"
            busyLabel="Indexing the deck…"
            state={pptIngest}
            onIngest={ingestDeck}
            fieldId={(name) => field(`ppt-ingest-${name}`)}
          />
          <IngestForm
            label="Ingest a meeting text"
            buttonLabel="Ingest the meeting text"
            busyLabel="Indexing the meeting text…"
            state={meetingIngest}
            onIngest={ingestMeeting}
            fieldId={(name) => field(`meeting-ingest-${name}`)}
          />
        </>
      )}
    </Panel>
  )
}
