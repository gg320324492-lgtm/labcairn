import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'

// `globals: false` in vitest.config.ts, so cleanup must be registered explicitly.
afterEach(() => {
  cleanup()
})
