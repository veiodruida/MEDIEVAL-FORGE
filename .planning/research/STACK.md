# STACK.md — Medieval Forge

**Researched:** 2026-04-16
**Overall Confidence:** MEDIUM-HIGH (most components verified against current sources; a few peer-dependency edge cases flagged)

---

## Validated Choices (from briefing)

### Frontend

| Library | Briefing Version | Current Stable | Status | Notes |
|---------|-----------------|----------------|--------|-------|
| React | 18 | 19.2.5 | CAUTION | React 18 is still fully supported and valid for a local tool. However, react-konva's latest release (19.2.3) uses versioning that tracks React 19, not 18. See Potential Issues. |
| Vite | 5 | 8.x (latest main), 6.x (LTS-ish) | OUTDATED | Vite 5 is functional but 6 was released Nov 2024 and 8 is current. For a greenfield project, start on Vite 6 at minimum. Migration from 5→6 is described as smooth. |
| TypeScript | not pinned | 5.8.x | OK | No issues. Vite uses esbuild/Oxc for transpile, tsc for type-checking. Any TS 5.x works. |
| react-konva + konva | 9.x | react-konva 19.2.3 / konva 9.x | CAUTION | react-konva latest version number (19.x) mirrors React 19 versioning convention. The underlying konva core is 9.x. With React 18 as peer, check for `--legacy-peer-deps` requirement. Actively maintained. |
| Zustand | not pinned | 5.0.12 | OK | Zustand v5 drops support for React < 18, making React 18 the minimum. No issue here. Uses native `useSyncExternalStore`. |
| zundo | 3.x (briefing) | 2.3.0 (actual npm) | VERSION MISMATCH | zundo 3.x does not exist on npm. Latest is 2.3.0. v2 is a complete rewrite with a different API. See Potential Issues. |
| TanStack Query | v5 | 5.99.0 | OK | v5 is stable, production-ready, actively maintained. Requires React 18+. Uses `useSyncExternalStore`. ~20% smaller than v4. |
| Tailwind CSS | v4 | 4.x (released Jan 22, 2025) | OK WITH GOTCHAS | v4 is stable since January 2025. Configuration is now CSS-first (no `tailwind.config.js`). PostCSS plugin moved to `@tailwindcss/postcss`. Use `@tailwindcss/vite` plugin instead of PostCSS for Vite projects. See Potential Issues. |
| Radix UI | not pinned | primitives 1.x / themes 3.x | OK WITH GOTCHAS | Works with Tailwind v4 but has known specificity + transparency issues post-upgrade. See Potential Issues. |

### Backend

| Library | Briefing Version | Current Stable | Status | Notes |
|---------|-----------------|----------------|--------|-------|
| Python | 3.11+ | 3.13 | OK | 3.11 is well-supported. All listed libraries (Shapely, rasterio, Pillow) support 3.11+. Rasterio 1.5+ requires 3.12, so if using latest rasterio, bump to 3.12+. |
| FastAPI | not pinned | 0.115.x | OK | Stable, actively maintained. Async-native. Pydantic v2 is the default. No migration issues for a greenfield project. |
| SQLAlchemy async + aiosqlite | not pinned | SQLAlchemy 2.0.x + aiosqlite 0.21.x | OK WITH SETUP NOTES | Fully supported pattern. Greenfield projects avoid legacy migration issues. Key: always use `sqlite+aiosqlite://` URL, set `expire_on_commit=False`, and manage sessions with `async with`. Alembic migrations need async env.py. |
| Pydantic | v2 (implied by FastAPI) | v2.x | OK | FastAPI 0.100+ uses Pydantic v2 by default. |
| Shapely | not pinned | 2.1.2 | OK | Requires Python >= 3.10, GEOS >= 3.9, NumPy >= 1.21. Breaking change from 1.x: `voronoi_diagram()` output changed (`MULTILINESTRING` when `only_edges=True`). For greenfield, use 2.x API from the start. |
| scipy (Voronoi) | not pinned | 1.17.x | OK | `scipy.spatial.Voronoi` is stable. Works alongside Shapely 2.x without conflict. |
| Pillow (PIL) | not pinned | 12.2.0 | OK | Python 3.10–3.14 supported. Python 3.9 dropped. 3.11 is fine. |
| rasterio | not pinned | 1.4.4 (stable) / 1.5+ (requires 3.12) | WATCH | rasterio 1.4.x supports Python 3.10+. rasterio 1.5+ requires Python 3.12 and NumPy >= 2. If using rasterio 1.5+, pin Python to 3.12+. For Python 3.11, stay on rasterio 1.4.x. |
| Anthropic Python SDK | not pinned | 0.94.1 | OK | Full async support via `AsyncAnthropic`. Supports streaming. No issues. |
| Ollama (local LLM) | not pinned | ollama Python client 0.x | OK | Standard REST adapter pattern. No special integration required beyond HTTP client. |

### Packaging

| Concern | Briefing Approach | Current Practice | Status | Notes |
|---------|-------------------|-----------------|--------|-------|
| pip-installable package | `package_data` in `setup.py` | `pyproject.toml` with `[tool.setuptools.package-data]` | UPGRADE PATH | `setup.py` still works but `pyproject.toml` is the 2025 standard. `include-package-data = true` is the default for `pyproject.toml`-based projects. |
| Serving bundled React build | FastAPI `StaticFiles` mount | FastAPI `app.mount("/", StaticFiles(...))` for SPA | OK | Established pattern: `vite build` outputs to `frontend/dist/`, Python package includes that `dist/` dir via `package-data`, FastAPI serves it. `index.html` must be returned for all non-API routes (SPA fallback). |
| CLI entry point | `medieval-forge start` | `[project.scripts]` in `pyproject.toml` | OK | `[project.scripts] medieval-forge = "medieval_forge.cli:main"` is the modern approach. The CLI launches uvicorn and opens a browser tab. |

---

## Potential Issues

### 1. react-konva version number vs React 18 (HIGH PRIORITY)

react-konva has adopted a versioning scheme that mirrors the React version it targets. The latest release is **19.2.3**, which targets React 19. If your project pins React 18, you may receive peer dependency warnings or need `--legacy-peer-deps` during install.

**Impact:** Build warnings, possible CI failures, potential subtle runtime issues if konva 19.x uses React 19 internals.

**Mitigation:** Either (a) use `react-konva@18.2.x` which is the last React-18-targeted release, or (b) upgrade to React 19 (which is stable as of December 2024). For a greenfield local tool, upgrading to React 19 is the cleaner choice.

### 2. zundo: Version 3.x does not exist

The briefing specifies `zundo 3.x`, but the current npm latest is **2.3.0** (last published ~1 year ago, ~2025). There is no 3.x release. This is a version number error in the briefing.

**The v2 API is significantly different from v1:**
- Middleware renamed: `undoMiddleware` → `temporal`
- Config: `include`/`exclude` → `partialize`; `historyDepthLimit` → `limit`; `coolOffDurationMs` → use `handleSet` with debounce
- `undo()`/`redo()` now accept optional `steps` parameter
- `pause`/`resume`/`isTracking` now available

**Impact:** Any code written assuming zundo 1.x API will break. v2 is the correct and current API to target.

**Mitigation:** Target `zundo@2.3.0` explicitly. Use the v2 `temporal` API throughout.

### 3. Tailwind CSS v4: CSS-first configuration is a paradigm shift

Tailwind v4 (released January 22, 2025) is stable but represents a breaking change from v3:

- **No `tailwind.config.js`** — all configuration is in your CSS file via `@theme`.
- **PostCSS plugin split** — `tailwindcss` no longer works as a PostCSS plugin directly. You must install `@tailwindcss/postcss`. For Vite, use `@tailwindcss/vite` (recommended, better performance).
- **`postcss-import` and `autoprefixer` no longer needed** — v4 handles both.
- **Content auto-detection** — no need to configure `content: []` paths.
- **Confirmed Radix UI gotcha**: After v3→v4 upgrade, some Radix UI components (especially Select, Dropdown from shadcn/ui-style setups) render transparent due to CSS layer ordering conflicts. Radix Themes has addressed specificity in recent releases, but manual testing is required.

**Mitigation:**
- Use `@tailwindcss/vite` plugin (not PostCSS).
- Import Radix Themes CSS **before** Tailwind's `@import "tailwindcss"` in your entry CSS, or use `@layer` to manage order.
- Use `tailwindcss-radix` package for Radix state attribute utilities if needed.

### 4. Vite 5 is two majors behind

At time of writing, Vite is at version 8.x. Vite 5 is not end-of-life but is not the current stable. Vite 6 was released November 2024 and is well-settled.

**Notable Vite 6 changes affecting this project:**
- `commonjsOptions.strictRequires` now defaults to `true` — may affect CJS dependencies.
- CSS output filenames changed in library mode (not applicable to SPA).
- Sass legacy API deprecated (not used here).

**Recommendation:** Start on Vite 6. Vite 7 and 8 exist but are newer major versions — Vite 6 is the safest non-5 choice for early 2026 development.

### 5. SQLAlchemy async with Alembic: migrations need special setup

Alembic does not auto-detect async engines. The `env.py` must be explicitly written to use `async_engine_from_config` and `run_async_migrations()`.

**Gotcha:** Forgetting to set `expire_on_commit=False` on the async session factory causes `MissingGreenlet` errors when accessing lazy-loaded relationships after commit.

**Mitigation:** Use this pattern from project start:
```python
async_engine = create_async_engine("sqlite+aiosqlite:///./forge.db", echo=False)
AsyncSession = async_sessionmaker(async_engine, expire_on_commit=False)
```

### 6. Rasterio 1.5+ requires Python 3.12 and NumPy 2

If `map_generator.py` (the existing pipeline) imports rasterio, the Python version constraint of the whole package is gated by rasterio's requirements.

- rasterio 1.4.x: Python 3.10+, NumPy 1.x or 2.x
- rasterio 1.5+: Python 3.12+, NumPy >= 2

**Mitigation:** Either pin rasterio to `>=1.4,<1.5` if staying on Python 3.11, or bump the project's minimum Python to 3.12 and get rasterio 1.5+. Given the PROJECT.md states Python 3.11+, pin rasterio to 1.4.x until Python constraint is revisited.

### 7. React 18 vs React 19 decision point

The briefing specifies React 18, but React 19 was released December 2024 and is the current stable (19.2.5). TanStack Query v5 requires React 18+, Zustand v5 requires React 18+, both work with React 19. react-konva 19.x targets React 19.

For a greenfield local tool with no legacy code, **React 19 is defensible**, especially since react-konva's latest release is 19.x-versioned.

---

## Recommendations

### Adjust These Versions

| Component | Briefing Says | Recommend Instead | Reason |
|-----------|--------------|-------------------|--------|
| Vite | 5 | 6.x | Two majors behind; smooth upgrade; 6.x is well-settled |
| React | 18 | 19 (or keep 18, see note) | react-konva 19.x targets React 19; React 19 is stable |
| react-konva | 9.x (implied) | 18.2.x (if React 18) or 19.2.x (if React 19) | Version scheme mirrors React version |
| zundo | 3.x | 2.3.0 | v3 does not exist; v2 is the current and correct release |
| rasterio | latest | >=1.4,<1.5 if Python 3.11; >=1.5 if Python 3.12 | 1.5+ requires Python 3.12 |
| Tailwind CSS | v4 | v4 with `@tailwindcss/vite` | Correct choice; just use Vite plugin, not PostCSS |

### Packaging Approach

Use `pyproject.toml` (not `setup.py`) with:
```toml
[tool.setuptools.package-data]
medieval_forge = ["frontend/dist/**/*"]

[project.scripts]
medieval-forge = "medieval_forge.cli:main"
```

The CLI entrypoint should:
1. Resolve the bundled `frontend/dist/` path using `importlib.resources` (Python 3.9+ API)
2. Launch `uvicorn` programmatically on a free port
3. Open the browser with `webbrowser.open()`

FastAPI serves the SPA with:
```python
app.mount("/", StaticFiles(directory=dist_path, html=True), name="frontend")
```

The `html=True` flag enables SPA fallback (serves `index.html` for unmatched routes).

### SQLite Is Appropriate for This Use Case

The project is a local single-user tool. SQLite is not a limitation here — it is the right choice. The async setup with aiosqlite is warranted because FastAPI uses an async event loop and LLM calls may be concurrent with DB operations. No need to consider PostgreSQL.

---

## Confidence Levels

| Area | Confidence | Basis |
|------|------------|-------|
| React / Vite / TypeScript | MEDIUM | Vite is at v8 in production; briefing specifies v5. React 19 peer dep issues with konva are real. Multiple sources confirm. |
| TanStack Query v5 | HIGH | npm confirms 5.99.0 active. Official docs confirm React 18+ requirement. No issues. |
| Zustand v5 + zundo v2 | HIGH (zustand) / HIGH (zundo version) | npm confirms zustand 5.0.12 and zundo 2.3.0. Briefing's "zundo 3.x" is a factual error. |
| Tailwind CSS v4 + Radix UI | MEDIUM | Stable since Jan 2025, confirmed. Radix transparency bug is confirmed in GitHub issue #17137. Full integration needs empirical testing. |
| react-konva / Konva.js | MEDIUM | npm confirms 19.2.3. React 18 peer dep compatibility needs `--legacy-peer-deps` or React 19 upgrade. Actively maintained. |
| FastAPI + SQLAlchemy async + aiosqlite | HIGH | Established 2025 pattern. Multiple authoritative sources. Only gotcha is Alembic async env.py, documented. |
| Python geometry stack (Shapely/scipy) | HIGH | Shapely 2.1.2 stable, scipy 1.17.x stable. Rasterio 1.4.x/1.5.x version split is documented on PyPI. |
| pip package with bundled frontend | MEDIUM | Established pattern (Hatch + pyproject.toml), multiple blog references. Project-specific CLI setup needs empirical testing. |
| Anthropic Python SDK | HIGH | PyPI confirms 0.94.1. Official docs confirm async support. |

---

## Sources

- [Vite 8 Release Blog](https://vite.dev/blog/announcing-vite8)
- [Vite 6 Migration Guide](https://v6.vite.dev/guide/migration)
- [react-konva npm](https://www.npmjs.com/package/react-konva)
- [zundo npm](https://www.npmjs.com/package/zundo)
- [zundo GitHub Releases](https://github.com/charkour/zundo/releases)
- [TanStack Query v5 Announcement](https://tanstack.com/blog/announcing-tanstack-query-v5)
- [TanStack Query npm (@tanstack/react-query)](https://www.npmjs.com/package/@tanstack/react-query)
- [Tailwind CSS v4.0 Blog](https://tailwindcss.com/blog/tailwindcss-v4)
- [Tailwind v4 PostCSS plugin issue](https://github.com/tailwindlabs/tailwindcss/discussions/15764)
- [Tailwind v4 + Radix UI transparency bug](https://github.com/tailwindlabs/tailwindcss/discussions/17137)
- [Radix UI Themes Styling Docs](https://www.radix-ui.com/themes/docs/overview/styling)
- [Zustand v5 Announcement](https://pmnd.rs/blog/announcing-zustand-v5/)
- [Zustand npm](https://www.npmjs.com/package/zustand)
- [FastAPI + Async SQLAlchemy 2.0 Guide](https://medium.com/@tclaitken/setting-up-a-fastapi-app-with-async-sqlalchemy-2-0-pydantic-v2-e6c540be4308)
- [Shapely 2.x Release Notes](https://shapely.readthedocs.io/en/stable/release/2.x.html)
- [rasterio PyPI](https://pypi.org/project/rasterio/)
- [Pillow Release Notes](https://pillow.readthedocs.io/en/stable/releasenotes/index.html)
- [Embedding React in FastAPI Python Package](https://medium.com/@asafshakarzy/embedding-a-react-frontend-inside-a-fastapi-python-package-in-a-monorepo-c00f99e90471)
- [setuptools package-data docs](https://setuptools.pypa.io/en/latest/userguide/datafiles.html)
- [Anthropic Python SDK PyPI](https://pypi.org/project/anthropic/)
