import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests', timeout: 30_000, fullyParallel: false, reporter: 'line',
  use: { baseURL: process.env.DOCS_PREVIEW_URL || 'http://127.0.0.1:4173', trace: 'retain-on-failure' },
  webServer: process.env.DOCS_PREVIEW_URL ? undefined : {
    command: 'npm run preview -- --host 127.0.0.1', url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI, timeout: 30_000
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }]
})
