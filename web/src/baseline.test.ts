import { describe, expect, it } from 'vitest'

import { BASELINE_FACTS } from './baseline'

describe('BASELINE_FACTS', () => {
  it('reports an under-construction status and never a working/ready one', () => {
    expect(BASELINE_FACTS.status).toBe('under-construction')
  })

  it('names the work order that produced the skeleton', () => {
    expect(BASELINE_FACTS.workOrder).toBe('LC-P1-01 / T10')
  })

  it('explicitly states the summary is a placeholder', () => {
    expect(BASELINE_FACTS.summary).toMatch(/placeholder/i)
  })

  it('lists capabilities a reader must not assume exist', () => {
    expect(BASELINE_FACTS.notImplemented.length).toBeGreaterThan(0)
    for (const item of BASELINE_FACTS.notImplemented) {
      expect(item.trim().length).toBeGreaterThan(0)
    }
  })
})
