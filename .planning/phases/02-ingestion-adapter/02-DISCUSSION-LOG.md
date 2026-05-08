# Phase 02: Ingestion adapter - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 02-ingestion-adapter
**Areas discussed:** ProjectDataset + cfg wiring, Reconciliação de formato, Estratégia de paridade live, Escopo (terrain + v1 endpoint + Wikidata + CLI)

---

## ProjectDataset + cfg wiring

### Q1 — Como ProjectDataset se conecta ao RegionConfig?

| Option | Description | Selected |
|--------|-------------|----------|
| Substituir campos em cfg | RegionConfig perde municipality_*_geojson; ProjectDataset anexado como cfg.dataset; cfg permanece único input mutável (D-V3-05) | ✓ |
| Segundo arg em run_pipeline | run_pipeline(cfg, dataset); quebra D-V3-05 explicitamente | |
| Hang off cfg como atributo | cfg.dataset = field(...) sem remover paths legacy | |

**User's choice:** Substituir campos em cfg (Recommended).
**Notes:** Honors D-V3-05; Phase 01's `iberia_config()` factory builds a vendored ProjectDataset.

---

### Q2 — ProjectDataset carrega paths ou geometrias in-memory?

| Option | Description | Selected |
|--------|-------------|----------|
| Paths para arquivos | dataclass de Path; pipeline abre/parseia internamente; mantém comportamento inicio | ✓ |
| FeatureCollections in-memory | Carrega GeoJSON dicts já parseados; mais rápido, perde artifact em disco | |
| Híbrido lazy | Path-or-bytes-or-FeatureCollection; flexível mas complexo | |

**User's choice:** Paths para arquivos (Recommended).
**Notes:** Determinismo + debuggability ganham; revisitar se Phase 04 sliders provarem que I/O importa.

---

### Q3 — @dataclass ou pydantic?

| Option | Description | Selected |
|--------|-------------|----------|
| @dataclass | Espelha RegionConfig (Phase 01 D-01); drift zero | ✓ |
| pydantic BaseModel | Validação automática; antecipa Phase 06 | |
| TypedDict + runtime checks | Tipo leve; meio termo | |

**User's choice:** @dataclass (Recommended).
**Notes:** Phase 06 export-gate cuida de validação separada.

---

### Q4 — Campos REQUIRED no MVP?

| Option | Description | Selected |
|--------|-------------|----------|
| PT municipalities GeoJSON | Required — Phase 01 KD-tree PT | ✓ |
| ES municipalities (TopoJSON ou GeoJSON) | Required — Phase 01 KD-tree ES | ✓ |
| mountain_river_data.json | Required — inicio falha sem ele | ✓ |
| DEM raster (opcional) | Optional — slot reservado | ✓ (como optional) |

**User's choice:** Todos selecionados (DEM como optional).
**Notes:** Phase 02 contrato MVP; pipeline assert no topo de landmask.py.

---

## Reconciliação de formato

### Q5 — v1 OSM produz UMA municipalities.geojson; Phase 01 espera (PT + ES separados). Reconciliação?

| Option | Description | Selected |
|--------|-------------|----------|
| Adapters EMITEM 3 arquivos vendored-shape | Split por ISO via clip_iso_codes; pipeline não muda | ✓ |
| ProjectDataset aceita formato natural OSM | FeatureCollection + ISO-tag; pipeline ganha código de split | |
| Aceitar ambos via dispatcher | Path OU dict; loader detecta forma; viola Karpathy | |

**User's choice:** Adapters EMITEM 3 arquivos vendored-shape (Recommended).
**Notes:** Honors ROADMAP success #3 ("wrap, don't rewrite"); pipeline imutável.

---

### Q6 — ES live: TopoJSON ou GeoJSON?

| Option | Description | Selected |
|--------|-------------|----------|
| Adapter emite ES como GeoJSON | Drift no loader landmask.py, não no algoritmo | ✓ |
| Adapter converte GeoJSON → TopoJSON | Mantém formato vendored Phase 01; dep nova | |
| TopoJSON só vendored, GeoJSON só live | Loader detecta extensão; dois branches paralelos | |

**User's choice:** Adapter emite ES como GeoJSON (Recommended).
**Notes:** landmask.py loader gains GeoJSON branch; TopoJSON branch stays for vendored fixture.

---

### Q7 — Onde adapters escrevem?

| Option | Description | Selected |
|--------|-------------|----------|
| projects/<uuid>/inputs/ | Mesmo padrão v1 (paths.py existente) | ✓ |
| data/regions/<region>/cache/<bbox-hash>/ | Cache regional reutilizável; quebra modelo per-project | |
| tmp dir, in-memory passthrough | Sem cache, re-fetch a cada run | |

**User's choice:** projects/<uuid>/inputs/ (Recommended).
**Notes:** Reusa paths.ensure_project_dirs.

---

### Q8 — Vendored es-atlas TopoJSON: manter ou substituir?

| Option | Description | Selected |
|--------|-------------|----------|
| Mantém vendored como fallback | iberia_config() factory inalterado; live coexiste | ✓ |
| Live substitui vendored | Deleta es-atlas-pkg/; parity test usa snapshot live-recorded | |
| Vendored só para parity, live para projetos novos | Dois caminhos; fixture imutável | |

**User's choice:** Mantém vendored como fallback (Recommended).
**Notes:** D-09/D-10/D-11 do Phase 01 ficam imutáveis.

---

## Estratégia de paridade live

### Q9 — Como provar parity green com live ingestion sem CI flaky?

| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot live-recorded + replay | Snapshot em tests/fixtures/.../live-ingestion/; refresh manual via commit | ✓ |
| VCR cassettes (vcrpy/respx) | Cassettes YAML HTTP-level; dep nova | |
| Job opt-in @network atrás de --network | CI default skip; live como smoke separado | |
| Replay snapshot + cassette overlay | Híbrido; over-engineering | |

**User's choice:** Snapshot live-recorded + replay (Recommended).
**Notes:** Refresh ritual mirrors Phase 01 baseline-refresh.

---

### Q10 — Onde fica o snapshot?

| Option | Description | Selected |
|--------|-------------|----------|
| tests/fixtures/iberia_868/live-ingestion/ | Co-localizado com golden/ | ✓ |
| data/regions/iberia_868/snapshots/ | Próximo aos inputs vendored; mistura input/test | |
| Test arquivo embedado | Inviável (Iberia OSM ~10-30MB) | |

**User's choice:** tests/fixtures/iberia_868/live-ingestion/ (Recommended).
**Notes:** Refresh via scripts/refresh_live_snapshot.py manual.

---

### Q11 — Test parametrize ou separado?

| Option | Description | Selected |
|--------|-------------|----------|
| Test separado: test_iberia_868_live.py | Fixture-path imutável; dois testes, dois caminhos, mesma saída | ✓ |
| Parametrize fixture vs live | @pytest.mark.parametrize; roda 2x | |
| Test live em integration, não parity | Não bloqueia parity gate | |

**User's choice:** Test separado: test_iberia_868_live.py (Recommended).
**Notes:** Ambos @pytest.mark.parity, ambos non-skippable, mesmo golden/.

---

### Q12 — Snapshot HTTP-level ou GeoJSON-level?

| Option | Description | Selected |
|--------|-------------|----------|
| GeoJSON-level (pós-adapter) | Adapter unit-tested separadamente; isola pipeline de OSM drift | ✓ |
| HTTP-level (raw OSM response) | Mock httpx; testa adapter+pipeline juntos | |
| Ambos níveis | Mais cobertura, mais snapshots | |

**User's choice:** GeoJSON-level (pós-adapter) (Recommended).
**Notes:** Adapter logic exercitada por unit test com tiny synthetic Overpass response.

---

## Escopo (terrain + v1 endpoint + Wikidata + CLI)

### Q13 — Terrain ingestion (DEM/HydroSHEDS/ridges) wire-up?

| Option | Description | Selected |
|--------|-------------|----------|
| Stub passthrough | Adapter retorna mountain_river_data.json vendored as-is; slot reservado | ✓ |
| Wire-up completo | DEM/HydroSHEDS/ridges → mountain_river_data.json automático; +50% código | |
| Wire-up parcial: só mountains | Mountains de DEM; rivers vendored | |

**User's choice:** Stub passthrough (Recommended).
**Notes:** Wire-up completo deferido para Phase 06 ou v3.1.

---

### Q14 — Endpoint v1 /api/projects/{id}/ingest disposition?

| Option | Description | Selected |
|--------|-------------|----------|
| Refactor /api/v3/projects/{id}/ingest novo | v1 endpoint coexiste até Phase 03 | ✓ |
| Substituir in-place | Quebra v1 stepper antes de Phase 03 estar pronta | |
| Só funções de adapter, sem endpoint | CLI direto; reduz escopo | |
| Adapter + endpoint v3 + manter v1 vivo | Coexistem; máxima compat | |

**User's choice:** Refactor /api/v3/projects/{id}/ingest novo (Recommended).
**Notes:** v1 stepper continua funcionando até Phase 03 deletar com endpoint legacy.

---

### Q15 — Wikidata wrapper Phase 02?

| Option | Description | Selected |
|--------|-------------|----------|
| Drop wrapper Wikidata | OSM-only é v3 contract; ingest_wikidata.py legacy stays | ✓ |
| Wikidata como fallback v3 | Codepath testado para entregar mapas todo-azul | |
| Trivial passthrough | Adapter de uma linha; valor mínimo | |

**User's choice:** Drop wrapper Wikidata (Recommended).
**Notes:** ingest_wikidata.py morre na Phase 03 com stepper.

---

### Q16 — CLI dedicado (medieval-forge ingest)?

| Option | Description | Selected |
|--------|-------------|----------|
| Só biblioteca Python | Adapters como Python imports; sem CLI novo | ✓ |
| Adicionar python -m ingest CLI | Espelha pipeline CLI; permite smoke fora pytest | |
| Subcomando medieval-forge ingest | Primeiro-classe para Game Designer | |

**User's choice:** Só biblioteca Python (Recommended).
**Notes:** CLI ergonomics ficam para Phase 03 (UI button).

---

## Claude's Discretion

- pipeline/adapters/ subpackage layout (osm.py + terrain.py + base.py vs flat) — decidido em planejamento
- Snapshot file naming + fingerprint convention (sha256 sidecar)
- Como landmask.py detecta ES GeoJSON vs TopoJSON (extension sniffing vs peek vs cfg.dataset.es_format)
- Adapter unit test fixture size + format
- SSE event payload schema do /api/v3 endpoint
- iberia_config() build inline vs vendored_dataset() helper
- pt_geojson aceita .geojson only ou também .json

## Deferred Ideas

- DEM/HydroSHEDS/ridges → mountain_river_data.json automático (Phase 06 ou v3.1)
- Region YAML loader (Phase 05)
- Per-region cache em data/regions/<region>/cache/<bbox-hash>/ (Phase 04)
- VCR cassettes (vcrpy/respx) para HTTP-level recording
- medieval-forge ingest CLI subcommand (Phase 03)
- Wikidata wrapper como v3 fallback (drop explícito)
- Substituir vendored es-atlas-pkg por live-only
- TopoJSON conversion de live OSM ES output
- Pydantic validation de ProjectDataset (Phase 06)
- Frontend wiring de /api/v3/projects/{id}/ingest (Phase 03)
