import { defineConfig, globalIgnores } from 'eslint/config'
import globals from 'globals'
import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'
import sonarjs from 'eslint-plugin-sonarjs'
import prettierConfig from 'eslint-config-prettier'

export default defineConfig([
  {
    name: 'app/files-to-lint',
    files: ['**/*.{js,mjs,jsx,ts,tsx,vue}'],
  },

  globalIgnores(['**/dist/**', '**/dist-ssr/**', '**/coverage/**']),

  {
    languageOptions: {
      globals: {
        ...globals.browser,
      },
    },
  },

  // JavaScript recommended rules
  js.configs.recommended,

  // TypeScript recommended rules
  ...tseslint.configs.recommended,

  // Vue essential rules
  ...pluginVue.configs['flat/essential'],

  // SonarJS recommended rules
  sonarjs.configs.recommended,

  // Prettier config (disables conflicting rules)
  prettierConfig,

  // Custom rules and overrides
  {
    rules: {
      // TypeScript specific
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
        },
      ],

      // SonarJS adjustments
      'sonarjs/cognitive-complexity': ['warn', 15],
      'sonarjs/no-duplicate-string': 'off', // Can be noisy in tests
      'sonarjs/todo-tag': 'off', // TODOs are legitimate markers for future work

      // Vue specific
      'vue/multi-word-component-names': 'off', // Allow single-word components
    },
  },

  // Test files: Relax rules for test code
  {
    files: ['**/*.test.ts'],
    rules: {
      'sonarjs/no-nested-functions': 'off', // Vitest naturally nests describe/it
      'sonarjs/assertions-in-tests': 'off', // Setup/teardown tests may not have assertions
      '@typescript-eslint/no-explicit-any': 'off', // Mocks often use 'any'
    },
  },
])
