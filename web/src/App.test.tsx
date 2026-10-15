import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { App } from './App'
import { BASELINE_FACTS } from './baseline'

describe('App', () => {
  it('renders the baseline notice heading', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'LabCairn web baseline' })).toBeInTheDocument()
  })

  it('shows the under-construction status rather than a working app', () => {
    render(<App />)

    expect(screen.getByTestId('baseline-status')).toHaveTextContent(
      `Status: ${BASELINE_FACTS.status}`,
    )
  })

  it('displays every not-yet-implemented capability', () => {
    render(<App />)

    for (const item of BASELINE_FACTS.notImplemented) {
      expect(screen.getByText(item)).toBeInTheDocument()
    }
  })
})
