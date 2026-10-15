import type { JSX } from 'react'

import { BASELINE_FACTS } from '../baseline'

/**
 * The only component in this baseline.
 *
 * It is intentionally a static, dependency-free notice. It performs no network calls,
 * holds no state and renders no research data. Later work orders replace it.
 */
export function PhaseOneBaselineNotice(): JSX.Element {
  return (
    <main className="baseline-notice">
      <h1 className="baseline-notice__title">LabCairn web baseline</h1>

      <p className="baseline-notice__badge" data-testid="baseline-status">
        Status: {BASELINE_FACTS.status}
      </p>

      <p className="baseline-notice__summary">{BASELINE_FACTS.summary}</p>

      <h2 className="baseline-notice__subtitle">Not implemented in this baseline</h2>
      <ul className="baseline-notice__list">
        {BASELINE_FACTS.notImplemented.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>

      <footer className="baseline-notice__footer">
        Produced by work order {BASELINE_FACTS.workOrder}. See the repository README and{' '}
        <code>docs/plans/LC-P1-01-task-breakdown.md</code> for status. The roadmap in the README
        describes plans, not shipped software.
      </footer>
    </main>
  )
}
