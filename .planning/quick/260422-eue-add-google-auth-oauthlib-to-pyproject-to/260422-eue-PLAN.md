---
phase: quick-260422-eue
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
autonomous: true
requirements:
  - QUICK-260422-EUE
must_haves:
  truths:
    - "medieval-forge start launches without ModuleNotFoundError for google_auth_oauthlib"
    - "google-auth-oauthlib is declared as a runtime dependency in pyproject.toml"
    - "The package is installed in the active environment"
  artifacts:
    - path: "pyproject.toml"
      provides: "google-auth-oauthlib runtime dependency declaration"
      contains: "google-auth-oauthlib"
  key_links:
    - from: "pyproject.toml [project].dependencies"
      to: "runtime import of google_auth_oauthlib in backend code"
      via: "pip install -e ."
      pattern: "google-auth-oauthlib"
---

<objective>
Add `google-auth-oauthlib` to `pyproject.toml` runtime dependencies and install it so `medieval-forge start` no longer crashes with `ModuleNotFoundError: No module named 'google_auth_oauthlib'`.

Purpose: Unblock local startup. Backend code imports `google_auth_oauthlib` (likely for Google OAuth browser-auth flow being scoped for Phase 3 LLM/provider auth) but the dependency was never declared, so a fresh install fails at runtime.

Output: Updated `pyproject.toml` with the dependency pinned to a safe range, and a verified working import in the active environment.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@pyproject.toml

<interfaces>
Current `[project].dependencies` in pyproject.toml (abbreviated):
```
fastapi>=0.115,<0.140
uvicorn[standard]>=0.30,<0.50
sqlalchemy>=2.0,<2.1
aiosqlite>=0.20,<0.22
alembic>=1.13,<2.0
pydantic>=2.7,<3.0
httpx>=0.27,<0.30
click>=8.1,<9.0
psutil>=5.9,<7.0
scipy>=1.13,<2.0
shapely>=2.0,<3.0
numpy>=1.26,<3.0
Pillow>=10.0,<13.0
rasterio>=1.4,<2.0
```

Target library: `google-auth-oauthlib` (PyPI). Current stable line is 1.2.x (released throughout 2024–2025). It pulls in `google-auth` and `requests-oauthlib` transitively — no need to declare those separately.

Recommended pin: `google-auth-oauthlib>=1.2,<2.0` (matches the project's convention of `>=minor,<next-major` bounds).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add google-auth-oauthlib to pyproject.toml dependencies</name>
  <files>pyproject.toml</files>
  <action>
    Open `pyproject.toml` and add `"google-auth-oauthlib>=1.2,<2.0",` to the `[project].dependencies` array. Insert it after `httpx>=0.27,<0.30,` to keep HTTP/auth-adjacent deps grouped (alphabetical order is not enforced by other entries). Do not touch `[project.optional-dependencies]`, `[tool.setuptools]`, or any other section. Pin rationale: matches project convention of `>=current-minor,<next-major`; 1.2.x is the current stable line and is what Phase 3 browser-auth scope will consume.
  </action>
  <verify>
    <automated>python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); assert any('google-auth-oauthlib' in dep for dep in d['project']['dependencies']), 'dep missing'; print('OK')"</automated>
  </verify>
  <done>`pyproject.toml` contains `google-auth-oauthlib>=1.2,<2.0` in `[project].dependencies`; file still parses as valid TOML.</done>
</task>

<task type="auto">
  <name>Task 2: Install the updated dependency set and verify import + startup</name>
  <files></files>
  <action>
    Run `pip install -e .` (editable reinstall) from the repo root so the new dependency is resolved into the active environment. Then verify the import works and that `medieval-forge --help` no longer fails with ModuleNotFoundError. If `pip install -e .` is not appropriate for the user's environment (e.g. they use a venv manager), they can run `pip install "google-auth-oauthlib>=1.2,<2.0"` directly — but the pyproject change is the source of truth for fresh installs.
  </action>
  <verify>
    <automated>pip install -e . && python -c "import google_auth_oauthlib; print('import OK', google_auth_oauthlib.__name__)" && medieval-forge --help > /dev/null && echo "CLI OK"</automated>
  </verify>
  <done>`import google_auth_oauthlib` succeeds in the active env; `medieval-forge --help` exits 0 with no ModuleNotFoundError; `medieval-forge start` gets past the previous import crash (actual server boot may still be gated on other runtime concerns — out of scope for this quick task).</done>
</task>

</tasks>

<verification>
1. `pyproject.toml` parses as valid TOML and declares `google-auth-oauthlib>=1.2,<2.0`.
2. `python -c "import google_auth_oauthlib"` succeeds with no error.
3. `medieval-forge --help` returns exit code 0.
4. `medieval-forge start` no longer raises `ModuleNotFoundError: No module named 'google_auth_oauthlib'` (any subsequent startup errors are separate concerns).
</verification>

<success_criteria>
- Dependency declared with an appropriate version bound in `pyproject.toml`.
- Dependency installed and importable in the active environment.
- Original ModuleNotFoundError no longer reproducible.
</success_criteria>

<output>
After completion, create `.planning/quick/260422-eue-add-google-auth-oauthlib-to-pyproject-to/260422-eue-SUMMARY.md` describing:
- The exact line added to `pyproject.toml`
- The installed version of `google-auth-oauthlib`
- Output of the verification commands
- Any follow-up notes (e.g. if Phase 3 will need `google-auth` APIs beyond what this package exposes)
</output>
