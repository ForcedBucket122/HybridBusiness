import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests', fullyParallel: false, workers: 1,
  use: { baseURL: 'http://127.0.0.1:8000', headless: true, channel: 'msedge', viewport: { width: 1440, height: 1000 } },
  reporter: [['list'], ['json', { outputFile: 'test-results/results.json' }]],
})
