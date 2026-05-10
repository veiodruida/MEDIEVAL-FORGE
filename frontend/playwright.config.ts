import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const REPO_ROOT = path.resolve(__dirname, '..')
const BACKEND_DIR = path.join(REPO_ROOT, 'backend')

/**
 * Playwright config for the Plan 03-08 read-only canvas UAT.
 *
 * `globalSetup` shells out to `backend/tests/fixtures/uat_setup.py` which
 *   1. runs the iberia_868 pipeline once (cached on disk),
 *   2. inserts a Project row in the same SQLite DB the backend reads, and
 *   3. seeds that project's `output/` dir with the 14 ARTIFACT_FILES.
 *
 * The setup script writes `{project_id, ...}` to a JSON sidecar that the
 * spec reads via `process.env.UAT_PROJECT_INFO_PATH`.
 *
 * The `webServer` array starts both the FastAPI backend on :8000 and the
 * Vite dev server on :5173. Vite proxies `/api` to the backend.
 */
export default defineConfig({
  testDir: './tests/uat/playwright',
  testMatch: /.*\.spec\.ts$/,
  timeout: 60_000,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  globalSetup: path.resolve(__dirname, 'tests/uat/playwright/globalSetup.ts'),
  webServer: [
    {
      command: 'python -m uvicorn medieval_forge.main:app --host 127.0.0.1 --port 8765',
      cwd: BACKEND_DIR,
      url: 'http://127.0.0.1:8765/api/projects',
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
      stderr: 'pipe',
      timeout: 60_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort',
      cwd: __dirname,
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
      stderr: 'pipe',
      timeout: 60_000,
    },
  ],
})
