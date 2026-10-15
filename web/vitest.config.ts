import { defineConfig, mergeConfig } from 'vitest/config'

// The `.ts` extension is explicit because Vite's native config loader requires it.
import viteConfig from './vite.config.ts'

// Vitest runs in a jsdom environment because the only tests in this baseline render
// React components. Unit tests that do not need a DOM should use
// `// @vitest-environment node` at the top of the file instead of forcing jsdom globally.
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      globals: false,
      setupFiles: ['./src/test/setup.ts'],
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      restoreMocks: true,
      coverage: {
        provider: 'v8',
        reporter: ['text', 'lcov'],
        reportsDirectory: './coverage',
      },
    },
  }),
)
