import { spawnSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

/**
 * Plan 03-08 globalSetup.
 *
 * Shells out to `backend/tests/fixtures/uat_setup.py` which:
 *   1. runs the iberia_868 pipeline once (cached on disk),
 *   2. inserts a Project row in the SQLite DB the backend reads, and
 *   3. seeds that project's output dir with the 14 ARTIFACT_FILES.
 *
 * The Python helper writes the {project_id, ...} JSON line to stdout.
 * We persist it under `tests/uat/playwright/.uat-state/project.json` and
 * expose its absolute path via `process.env.UAT_PROJECT_INFO_PATH` so
 * the spec can read it without a global module.
 */
export default async function globalSetup(): Promise<void> {
  const repoRoot = path.resolve(__dirname, '../../../..')
  const backendDir = path.join(repoRoot, 'backend')
  const stateDir = path.join(__dirname, '.uat-state')
  const projectInfoPath = path.join(stateDir, 'project.json')

  mkdirSync(stateDir, { recursive: true })

  const py = process.env.PYTHON ?? 'python'
  const result = spawnSync(
    py,
    ['-c', 'from tests.fixtures.uat_setup import main; import sys; sys.exit(main(["uat_setup.py"]))'],
    {
      cwd: backendDir,
      encoding: 'utf-8',
      // Pipeline first run can take ~45 s.
      timeout: 5 * 60_000,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    },
  )

  if (result.status !== 0) {
    throw new Error(
      `uat_setup.py failed (exit ${result.status})\nstdout:\n${result.stdout}\nstderr:\n${result.stderr}`,
    )
  }

  // The script may emit pipeline progress lines on stdout before the JSON.
  // Take the LAST non-empty line, which is the JSON record.
  const lines = result.stdout
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0)
  const lastLine = lines[lines.length - 1]
  let info: { project_id: string; name: string }
  try {
    info = JSON.parse(lastLine)
  } catch (err) {
    throw new Error(
      `uat_setup.py did not emit valid JSON on the last stdout line:\n${lastLine}\n` +
        `full stdout:\n${result.stdout}`,
    )
  }
  if (typeof info.project_id !== 'string' || info.project_id.length === 0) {
    throw new Error(`uat_setup.py JSON is missing project_id: ${lastLine}`)
  }

  writeFileSync(projectInfoPath, JSON.stringify(info, null, 2), 'utf-8')
  process.env.UAT_PROJECT_INFO_PATH = projectInfoPath
}
