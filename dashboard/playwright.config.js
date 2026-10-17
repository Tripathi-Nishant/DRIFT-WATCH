import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30000,
  use: { baseURL: process.env.BASE_URL || 'http://127.0.0.1:8765', trace: 'retain-on-failure' },
  webServer: process.env.BASE_URL ? undefined : { command: 'driftwatch serve --host 127.0.0.1 --port 8765', url: 'http://127.0.0.1:8765/healthz', reuseExistingServer: true },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
