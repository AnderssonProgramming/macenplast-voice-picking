import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, devices } from '@playwright/test'

const dirname = path.dirname(fileURLToPath(import.meta.url))
const apiDir = path.resolve(dirname, '../api')
const pythonWin = path.join(apiDir, '.venv', 'Scripts', 'python.exe')
const pythonUnix = path.join(apiDir, '.venv', 'bin', 'python')
// CI installs macenplast into the runner's system Python (no venv) and
// sets E2E_API_PYTHON=python; local dev uses whichever venv exists.
export const apiPython = process.env.E2E_API_PYTHON || (existsSync(pythonWin) ? pythonWin : pythonUnix)

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: false,
  retries: 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `"${apiPython}" -m uvicorn macenplast.main:app --host 127.0.0.1 --port 8000`,
      cwd: apiDir,
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: 'npm run dev -- --port 5173 --strictPort --host 127.0.0.1',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
})
