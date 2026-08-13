import { defineConfig, devices } from '@playwright/test'

/**
 * Browser tests, for the things jsdom cannot see.
 *
 * jsdom has no layout engine: getBoundingClientRect returns zeros and stacking
 * contexts do not exist. Two of the three frontend bugs found in Phase 7 were
 * invisible to it -- a cover clipped by an overflow container, and a z-index on
 * a statically positioned element.
 *
 * The API is stubbed with page.route rather than a real backend, so this suite
 * needs no Postgres and spends none of the provider's rate limit.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://localhost:4173',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // Preview rather than dev: tests the built output, and avoids HMR
  // reconnect noise mid-run.
  webServer: {
    command: 'npm run build && npm run preview -- --port 4173',
    url: 'http://localhost:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
