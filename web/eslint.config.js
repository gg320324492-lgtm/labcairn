import js from '@eslint/js'
import prettier from 'eslint-config-prettier'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  {
    ignores: ['dist/', 'coverage/', 'node_modules/'],
  },

  // Tooling config files (ESM JavaScript at the web/ root).
  {
    files: ['**/*.{js,mjs,cjs}'],
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      globals: globals.node,
    },
  },

  // Application and test sources.
  {
    files: ['src/**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommendedTypeChecked, prettier],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    },
  },

  // The build tooling is TypeScript too, and is checked the same way the
  // application sources are: it runs at build time and decides what is
  // shipped, so a defect in it is a defect in the artefact.
  {
    files: ['scripts/**/*.ts'],
    extends: [js.configs.recommended, ...tseslint.configs.recommendedTypeChecked, prettier],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      globals: globals.node,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },

  // Vitest setup and test files get the test globals they actually use.
  {
    files: ['src/test/**/*.ts', 'src/**/*.test.{ts,tsx}'],
    languageOptions: {
      globals: globals.browser,
    },
  },
)
