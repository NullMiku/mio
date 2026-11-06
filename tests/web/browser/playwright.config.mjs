import { defineConfig } from '@playwright/test';

const port = Number(process.env.MIO_WEB_PORT || 8787);
export default defineConfig({
  testDir: '.',
  timeout: 120_000,
  expect: { timeout: 30_000 },
  workers: 1,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: '../../../build/web-report/browser.json' }]],
  use: { baseURL: `http://127.0.0.1:${port}/`, headless: true, acceptDownloads: true },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  webServer: {
    // Plain static file server: the playground must work without any server-side code.
    command: `python3 serve.py ${port} ${process.env.MIO_WEB_DIR || '../../../build/web'}`,
    url: `http://127.0.0.1:${port}/index.html`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
