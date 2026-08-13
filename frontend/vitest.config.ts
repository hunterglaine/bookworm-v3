import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

/**
 * Separate from vite.config.ts on purpose.
 *
 * The app config carries a dev-server proxy and the Tailwind plugin, neither of
 * which a unit run needs. Keeping them apart also stops the Playwright specs,
 * which live outside src/, from being swept into the Vitest run.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
})
