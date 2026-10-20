/**
 * The preview of an artefact.
 *
 * **Where the preview is rendered, and why it is that way.** The preview is
 * an `<img>` or a sandboxed `<iframe>`, and it points at the service's own
 * bytes at `/artifacts/{id}/content`. It is never an inlined document: the
 * artefact's bytes are fetched by the browser from the service, and this
 * page never holds them.
 *
 * The reason is the one the artefact's own media type makes unavoidable.
 *
 * * **An SVG can carry script.** A figure in this project is an SVG, and an
 *   SVG document loaded *as a document* runs script. So an SVG is loaded
 *   through `<img>`, where the browser renders it as an image and scripting
 *   is off; the service's own `Content-Security-Policy: sandbox` and
 *   `X-Content-Type-Options: nosniff` are the second line under it.
 * * **An HTML artefact loaded as a document runs in the service's origin**,
 *   where every guard passes and `/session` is readable. So the report's own
 *   HTML form is loaded in a frame with `sandbox` and nothing else: no
 *   scripts, no forms, no popups, and no access to the origin it was
 *   loaded from. The report's form is self-contained, so it renders exactly
 *   as it did.
 *
 * The forms that cannot be shown as an image or a frame — the Markdown, the
 * DOCX, the PDF — are **linked**, not re-rendered. The workbench does not
 * compose a fifth wording of the report from the model; it shows what the
 * report produced. And a link is safe as well, because the service answers
 * artefact content with `Content-Security-Policy: sandbox` whatever the
 * media type is, so even a document opened in a new tab lands in an opaque
 * origin where it cannot reach the session token.
 */

import type { JSX } from 'react'

import { apiUrl } from '../api/base'
import type { ArtifactReceipt } from '../api/generated'
import { artifactContentPath } from '../api/paths'

interface ArtifactPreviewProps {
  /** The artefact to preview. */
  readonly receipt: ArtifactReceipt
}

/** The media type the receipt declares, or the empty string when it declares none. */
function mediaTypeOf(receipt: ArtifactReceipt): string {
  return receipt.media_type ?? ''
}

export function ArtifactPreview({ receipt }: ArtifactPreviewProps): JSX.Element {
  const mediaType = mediaTypeOf(receipt)
  // The service's own path, mounted the way this bundle was built: at the
  // root in production, behind the development proxy otherwise.
  const source = apiUrl(artifactContentPath(receipt.receipt_id))

  if (mediaType === 'text/html') {
    return (
      <iframe
        className="preview preview--frame"
        src={source}
        sandbox=""
        referrerPolicy="no-referrer"
        title={`Preview of ${receipt.relative_path}`}
      />
    )
  }

  if (mediaType.startsWith('image/')) {
    return (
      <img
        className="preview preview--image"
        src={source}
        alt={`Preview of ${receipt.relative_path}`}
        referrerPolicy="no-referrer"
      />
    )
  }

  return (
    <a className="preview preview--link" href={source} target="_blank" rel="noreferrer">
      Open {receipt.relative_path}
    </a>
  )
}
