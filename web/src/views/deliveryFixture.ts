/**
 * The delivery centre's data, while the service's `/review` routes are being
 * built out on this machine.
 *
 * **These are fixtures, and they say so.** The two objects carry the
 * service's exact wire shapes — `ReviewPreview` and `DeliverablesExportWire`,
 * from the generated types — and are asserted at the type level: a fixture
 * that drifted from the wire would fail this cast's compile-time check rather
 * than mislead the centre at runtime. When the service answers, the fixture
 * is deleted and the reads stand alone; the paths are already the routes'
 * names, so the swap touches the client only.
 *
 * **The digests are honest.** Each `sha256` below is the digest of the very
 * bytes its `content_base64` decodes to, so a test that decodes, hashes and
 * compares exercises the same check a client does against the service — and
 * a fixture whose digest disagreed with its bytes would teach the wrong
 * property.
 */

import type {
  DeliverableFileWire,
  DeliverablesExportWire,
  PreviewEditSummary,
  ReviewPreview,
} from '../api/generated'

/** The round the fixtures name: the review fixtures' own project. */
export const FIXTURE_PROJECT_ID = 'proj-lc-p4-cap'

/** The version the fixtures' round works from. */
export const FIXTURE_INPUT_VERSION_ID = 'ver-baseline-04'

/** The dossier the fixtures' export is bound to. */
export const FIXTURE_DOSSIER_ARTIFACT_ID = '0193f0a1-0000-7000-8000-00000000d001'

/** The task the fixtures' export is bound to. */
export const FIXTURE_TASK_ID = '0193f0a1-0000-7000-8000-00000000b001'

/** The version the fixtures' round published. */
export const FIXTURE_OUTPUT_VERSION_ID = 'ver-applied-05'

/** The edges and receipts the fixtures' binding holds. */
export const FIXTURE_EDGE_ID = '0193f0a1-0000-7000-8000-00000000e001'
export const FIXTURE_MARKED_RECEIPT_ID = '0193f0a1-0000-7000-8000-00000000a101'
export const FIXTURE_CLEAN_RECEIPT_ID = '0193f0a1-0000-7000-8000-00000000a102'

/** The per-suggestion summaries the preview carries, old against new. */
export const fixturePreviewEdits: readonly PreviewEditSummary[] = [
  {
    feedback_id: 'fb-0193f0a1-0000-7000-8000-00000000c101',
    part: 'word/document.xml',
    paragraph: 2,
    old_text:
      'The winter of 1542 stands as the coldest on record for the basin, with a mean ' +
      'temperature reconstructed well below the series’ long-run average.',
    new_text:
      'The winter of 1542 stands as the coldest on record for the basin in the reconstructed ' +
      'series (core 04, table 3), with a mean temperature well below the series’ long-run ' +
      'average.',
    author: 'model:labcairn-suggest-01',
  },
  {
    feedback_id: 'fb-0193f0a1-0000-7000-8000-00000000c102',
    part: 'word/document.xml',
    paragraph: 4,
    old_text:
      'Sediment accumulation rates were estimated from varve counting across the entire ' +
      'sequence.',
    new_text:
      'Sediment accumulation rates were estimated from varve counting for the counted ' +
      'intervals; the 1823–1826 interval is interpolated and carries no counted years.',
    author: 'model:labcairn-suggest-01',
  },
  {
    feedback_id: 'fb-0193f0a1-0000-7000-8000-00000000c103',
    part: 'word/document.xml',
    paragraph: 7,
    old_text: 'Figure 2 shows the reconstructed winter temperature anomaly for the full period.',
    new_text:
      'Figure 2 shows the reconstructed winter temperature anomaly (°C, anomalies from the ' +
      '1961–1990 mean) for the full period.',
    author: 'model:labcairn-suggest-01',
  },
]

/**
 * `POST /review/preview` — what the apply round would do.
 *
 * Three suggestions stand approved, one opinion waits and one was rejected,
 * and the preview names the paragraphs those three touch and the digests the
 * committed apply will publish.
 */
export const fixturePreview: ReviewPreview = {
  project_id: FIXTURE_PROJECT_ID,
  input_version_id: FIXTURE_INPUT_VERSION_ID,
  applied: 3,
  pending: 1,
  rejected: 1,
  affected_paragraphs: [2, 4, 7],
  edits: [...fixturePreviewEdits],
  marked_sha256: '6391f487e9faf5f7d1ca58fe53a4dd5a5a2f94540285d8fbb524374887f63d22',
  marked_size_bytes: 47,
  clean_sha256: '411f74570be29293c187f41927d0b0f32cc3ff695003f9c5013767cac9098a80',
  clean_size_bytes: 46,
  original_sha256: '9d307360c16c1c51ec85b93af9816c1fa77f9e02a4d55cc5f0bb0c4a7e2a6e11',
  original_size_bytes: 49,
}

/**
 * One deliverable on the wire: the bytes, their digest and their size.
 *
 * **The digest is over the decoded bytes**, the same check a client runs
 * after saving — so the fixture's fields are derived from its bytes, not
 * invented beside them.
 */
function deliverable(
  kind: string,
  relativePath: string,
  contentBase64: string,
  sha256: string,
  sizeBytes: number,
): DeliverableFileWire {
  return {
    kind,
    relative_path: relativePath,
    content_base64: contentBase64,
    sha256,
    size_bytes: sizeBytes,
  }
}

/** `GET /review/deliverables` — one closed binding, four files. */
export const fixtureDeliverablesExport: DeliverablesExportWire = {
  project_id: FIXTURE_PROJECT_ID,
  dossier_artifact_id: FIXTURE_DOSSIER_ARTIFACT_ID,
  task_id: FIXTURE_TASK_ID,
  input_version_id: FIXTURE_INPUT_VERSION_ID,
  output_version_id: FIXTURE_OUTPUT_VERSION_ID,
  marked_receipt_id: FIXTURE_MARKED_RECEIPT_ID,
  clean_receipt_id: FIXTURE_CLEAN_RECEIPT_ID,
  edge_id: FIXTURE_EDGE_ID,
  deliverables: [
    deliverable(
      'marked',
      'deliverables/binding-sample-marked.docx',
      'TGFiQ2Fpcm4gZml4dHVyZSBtYXJrZWQgZHJhZnQgKG5vdCBhIHJlYWwgRE9DWCk=',
      '6391f487e9faf5f7d1ca58fe53a4dd5a5a2f94540285d8fbb524374887f63d22',
      47,
    ),
    deliverable(
      'clean',
      'deliverables/binding-sample-clean.docx',
      'TGFiQ2Fpcm4gZml4dHVyZSBjbGVhbiBkcmFmdCAobm90IGEgcmVhbCBET0NYKQ==',
      '411f74570be29293c187f41927d0b0f32cc3ff695003f9c5013767cac9098a80',
      46,
    ),
    deliverable(
      'response_table',
      'deliverables/response-table.md',
      'IyBSZXNwb25zZSB0YWJsZSAoZml4dHVyZSkKCkV2ZXJ5IG9waW5pb24gb2YgdGhpcyByb3VuZCwgYW5zd2VyZWQuCg==',
      '3c4aa748e935b36631b0475751ca614179af5baacda4699cf90d0e6bbe003e78',
      67,
    ),
    deliverable(
      'quality_report',
      'deliverables/quality-report.md',
      'IyBRdWFsaXR5IHJlcG9ydCAoZml4dHVyZSkKCkJpbmRpbmc6IHByb2otbGMtcDQtY2FwIC8gdmVyLWJhc2VsaW5lLTA0Lgo=',
      '496dcb485518df1aea0161f043bcc6fef17d1ff413896d6d12ef30c3aaf23d2b',
      71,
    ),
  ],
}
