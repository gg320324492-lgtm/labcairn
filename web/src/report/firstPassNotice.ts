/**
 * The report's own limit, in the report's own words.
 *
 * Every export the report produces is a first-pass report and says so on its
 * own face: *"This is a first-pass report produced by LabCairn. It is not
 * journal-ready."* The workbench must not hide that. A report shown without
 * its limit is a report shown as something it is not, and the person reading
 * the screen would have no way of knowing.
 *
 * **The sentence is the renderer's, not ours.** It is the exact string in
 * `src/labcairn/reports/render/constants.py` (`FIRST_PASS_NOTICE`), which is
 * where the report's voice lives so that the four exports do not phrase it
 * four ways. Copying it here keeps one wording in the repository rather
 * than two that agree until somebody changes one of them — and
 * `firstPassNotice.test.ts` fails the moment the two differ, so the copy
 * cannot quietly become a paraphrase.
 *
 * The report's **own** face is shown as well, in the artefact preview: this
 * notice says what the limit is, and the preview is where a reader reads
 * the report's version of it.
 */
export const REPORT_FIRST_PASS_NOTICE =
  'This is a first-pass report produced by LabCairn. It is not journal-ready.'
