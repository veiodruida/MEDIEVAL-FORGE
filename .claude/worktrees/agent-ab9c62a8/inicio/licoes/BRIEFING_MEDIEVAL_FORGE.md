# BRIEFING — Medieval Forge (Ferramenta Web Local)

**Data:** 2026-04-15 | **Prioridade:** NOVA FERRAMENTA | **Fase inicial:** MVP

---

## 1. Contexto

O utilizador é Game Designer do projecto Reconquista (grand strategy Unity 6, Península Ibérica 868 AD). Durante ~25 iterações de um chat, gerou mapas medievais combinando dados modernos de municípios com pesquisa histórica manual. O processo foi trabalhoso e cheio de erros de iteração cega. Quer automatizar isto numa ferramenta reutilizável para qualquer país e qualquer período histórico.

A ferramenta existente (`map_generator.py` — incluído) gera bons mapas mas falta-lhe:
- Preview em tempo real (iterações eram cegas)
- Editor vectorial para corrigir fronteiras herdadas de municípios modernos
- Workflow de pesquisa histórica estruturado
- Validação automática (pontos pretos, territórios órfãos)
- Histórico undo/redo

---

## 2. Stack Técnico Obrigatório

### Backend
- **Python 3.11+** com FastAPI
- **Dependências Python**: `fastapi`, `uvicorn`, `pydantic>=2`, `numpy`, `scipy`, `pillow`, `shapely`, `rasterio`, `httpx`, `sqlalchemy`, `aiosqlite`, `anthropic`, `ollama`
- **Reutilizar** `map_generator.py` (incluído como biblioteca)
- **SQLite** para estado via SQLAlchemy async

### Frontend
- **React 18 + TypeScript + Vite**
- **Konva.js + react-konva** — canvas com camadas, hit detection, pontos vectoriais drag&drop
- **Zustand** — state management (com middleware `temporal` para undo/redo)
- **TanStack Query v5** — cache de requests ao backend
- **Tailwind CSS v4** — styling
- **Radix UI primitives** — dialogs, dropdowns, toolbars

### Empacotamento
- **Python package** instalável: `pip install medieval-forge`
- Entry point: `medieval-forge start` → corre FastAPI + serve frontend buildado → abre browser
- Frontend build incluído no package (via `package_data`)

---

## 3. Arquitectura de Pastas

```
medieval-forge/
├── pyproject.toml
├── README.md
├── LICENSE (MIT)
├── src/
│   └── medieval_forge/
│       ├── __init__.py
│       ├── cli.py                    # medieval-forge start/stop
│       ├── server.py                 # FastAPI app
│       ├── config.py                 # Paths, settings
│       ├── api/
│       │   ├── __init__.py
│       │   ├── projects.py           # /api/projects CRUD
│       │   ├── ingest.py             # /api/ingest/{source}
│       │   ├── research.py           # /api/research (LLM)
│       │   ├── generate.py           # /api/generate
│       │   ├── edit.py               # /api/edit/* (vectorial ops)
│       │   └── export.py             # /api/export
│       ├── services/
│       │   ├── wikidata.py           # SPARQL queries
│       │   ├── osm.py                # Overpass API
│       │   ├── natural_earth.py      # Rivers/coastlines
│       │   ├── llm.py                # Claude API + Ollama adapter
│       │   ├── voronoi.py            # Local regeneration
│       │   ├── validator.py          # Pre-export validation
│       │   └── generator.py          # Wraps map_generator.py
│       ├── models/
│       │   ├── project.py            # SQLAlchemy models
│       │   ├── territory.py
│       │   └── state.py              # Pydantic schemas
│       ├── storage/
│       │   └── database.py           # SQLite setup
│       └── static/                   # Frontend build output
│           └── index.html
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── store/
│   │   │   ├── project.ts            # Zustand store + temporal
│   │   │   ├── editor.ts             # Canvas state
│   │   │   └── ui.ts                 # Modals, selection
│   │   ├── api/
│   │   │   └── client.ts             # TanStack Query hooks
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── TopBar.tsx
│   │   │   │   ├── LeftSidebar.tsx   # Layers list
│   │   │   │   └── RightSidebar.tsx  # Properties panel
│   │   │   ├── canvas/
│   │   │   │   ├── MapCanvas.tsx     # Main Konva Stage
│   │   │   │   ├── TerrainLayer.tsx
│   │   │   │   ├── TerritoryLayer.tsx
│   │   │   │   ├── BordersLayer.tsx
│   │   │   │   ├── CapitalsLayer.tsx
│   │   │   │   └── LabelsLayer.tsx
│   │   │   ├── tools/
│   │   │   │   ├── MoveCapitalTool.tsx
│   │   │   │   ├── EditBorderTool.tsx
│   │   │   │   ├── MergeSplitTool.tsx
│   │   │   │   └── TerrainBrushTool.tsx
│   │   │   ├── dialogs/
│   │   │   │   ├── NewProjectDialog.tsx
│   │   │   │   ├── ResearchDialog.tsx
│   │   │   │   └── ExportDialog.tsx
│   │   │   └── ui/                   # Radix wrappers
│   │   ├── lib/
│   │   │   ├── geometry.ts           # Voronoi client-side preview
│   │   │   ├── constants.ts
│   │   │   └── utils.ts
│   │   └── types/
│   │       ├── project.ts
│   │       └── territory.ts
├── tests/
│   ├── conftest.py
│   ├── test_wikidata.py
│   ├── test_generator.py
│   └── test_export.py
└── vendor/
    └── map_generator.py              # Scripts existentes
    └── territory_data_example.py     # Exemplo Ibéria
```

---

## 4. Divisão em Fases

### Fase 1 — MVP Backend + Geração (2-3 semanas)

**Objectivo:** Utilizador cria um projecto, faz ingestão, gera mapa estático. Sem edição ainda.

#### Endpoints a implementar

| Endpoint | Método | Propósito |
|---|---|---|
| `/api/projects` | GET, POST | Listar/criar projectos |
| `/api/projects/{id}` | GET, PATCH, DELETE | CRUD de projecto |
| `/api/projects/{id}/ingest/wikidata` | POST | Ingestão de municípios via SPARQL |
| `/api/projects/{id}/ingest/osm` | POST | Fallback via Overpass |
| `/api/projects/{id}/generate` | POST | Correr o pipeline (map_generator.py) |
| `/api/projects/{id}/export` | POST | Gerar ZIP Unity-ready |
| `/api/projects/{id}/preview/{layer}.png` | GET | Servir PNG preview |

#### Schema do Projecto (Pydantic + SQLAlchemy)

```python
class Project(BaseModel):
    id: str  # UUID
    name: str
    country: str  # "portugal", "england", etc
    period_start: int  # year
    period_end: int
    bounds: Bounds  # lon_min/max, lat_min/max
    config: GeneratorConfig  # smoothing_sigma, merge_threshold, etc
    created_at: datetime
    updated_at: datetime

class Bounds(BaseModel):
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float

class GeneratorConfig(BaseModel):
    map_w: int = 1920
    map_h: int = 1080
    upscale: int = 2
    island_min_px: int = 300
    fragment_min_px: int = 600
    blob_merge_px: int = 200
    median_passes: int = 8
    smooth_sigma: float = 4.5
    # Kingdom colors as hex list
    kingdom_colors: list[str] = []

class Territory(BaseModel):
    id: str
    project_id: str
    level: Literal["barony", "county", "duchy", "kingdom"]
    name: str
    parent_id: str | None  # hierarchy
    centroid_lon: float
    centroid_lat: float
    # Polygon as GeoJSON
    geometry: dict  # Polygon/MultiPolygon
    properties: dict  # culture, religion, development, terrain
```

#### Armazenamento em disco

```
~/.medieval-forge/
├── db.sqlite                         # Projects + territories metadata
└── projects/
    └── {project_id}/
        ├── raw/                      # Raw ingested data
        │   ├── municipalities.geojson
        │   ├── rivers.geojson
        │   └── elevation.tif         # Optional
        ├── state/
        │   ├── territories.json      # Current state (vectorial)
        │   ├── history/              # Undo/redo snapshots
        │   │   ├── 0001.json
        │   │   ├── 0002.json
        │   │   └── ...
        ├── preview/                  # Generated PNG previews
        │   ├── terrain.png
        │   ├── territories.png
        │   └── borders.png
        └── export/                   # Unity export staging
            └── [Unity files]
```

#### Wikidata SPARQL — exemplos de queries

```python
# Get all municipalities of a country with polygon centroids
WIKIDATA_MUNICIPALITIES_QUERY = """
SELECT ?muni ?muniLabel ?coord WHERE {
  ?muni wdt:P17 wd:{COUNTRY_QID} .
  ?muni wdt:P31/wdt:P279* wd:Q15284 .  # instance of administrative territorial entity
  ?muni wdt:P625 ?coord .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
LIMIT 5000
"""

# Country QIDs: PT=Q45, ES=Q29, GB=Q145, FR=Q142, IT=Q38, DE=Q183
```

#### CLI

```python
# cli.py
@click.group()
def cli():
    pass

@cli.command()
@click.option('--port', default=8000)
@click.option('--no-browser', is_flag=True)
def start(port, no_browser):
    """Start Medieval Forge local server."""
    setup_db()
    if not no_browser:
        webbrowser.open(f'http://localhost:{port}')
    uvicorn.run('medieval_forge.server:app', host='127.0.0.1', port=port)

@cli.command()
def stop():
    """Stop running server (kills by PID file)."""
    ...
```

#### Critérios de Aceitação — Fase 1

| # | Teste | Resultado Esperado |
|---|---|---|
| 1 | `pip install -e .` no directório | Instala sem erros |
| 2 | `medieval-forge start` | FastAPI corre em :8000, browser abre |
| 3 | POST /api/projects com Portugal/868 | Retorna ID do projecto |
| 4 | POST /api/projects/{id}/ingest/wikidata | Descarrega >200 municípios |
| 5 | POST /api/projects/{id}/generate | Gera preview PNG em <60s |
| 6 | GET /api/projects/{id}/preview/terrain.png | Devolve PNG válido |
| 7 | POST /api/projects/{id}/export | Devolve ZIP com 12 ficheiros |

---

### Fase 2 — Editor Vectorial (3-4 semanas) — ZONA MAIS COMPLEXA

**Objectivo:** Canvas interactivo onde o utilizador edita fronteiras, move capitais, mescla territórios, etc. Com undo/redo.

#### Prioridades (por ordem, escolhidas pelo utilizador)

1. **Mover capital/centróide** → recalcula Voronoi à volta (só dos vizinhos, não full regen)
2. **Editor vectorial de pontos** — mover/criar/apagar nós das fronteiras (tipo Bézier/SVG)
3. **Mesclar/dividir territórios** — operações booleanas Shapely
4. **Pintar terreno** — pincel por tipo (montanha/rio/floresta)
5. **Undo/Redo** — Ctrl+Z / Ctrl+Y em tudo
6. **Importar mapa de relevo** — utilizador sobrepõe imagem própria como guia

#### Arquitectura do Canvas (Konva.js)

```typescript
// MapCanvas.tsx — estrutura de camadas
<Stage width={window.innerWidth} height={window.innerHeight}>
  {/* Layer 0: Reference overlays (user-uploaded terrain, SRTM) */}
  <Layer name="reference" opacity={referenceOpacity}>
    <Image image={userTerrainMap} />
  </Layer>
  
  {/* Layer 1: Ocean + land mask */}
  <Layer name="base">
    <Path data={coastlinePath} fill="#a8c0d4" />
  </Layer>
  
  {/* Layer 2: Territories (filled polygons) */}
  <Layer name="territories">
    {territories.map(t => (
      <Line
        key={t.id}
        points={t.geometry.flat()}
        closed
        fill={t.kingdomColor}
        stroke="transparent"
        onClick={() => selectTerritory(t.id)}
      />
    ))}
  </Layer>
  
  {/* Layer 3: Borders (thick lines by hierarchy) */}
  <Layer name="borders">
    {borders.map(b => <Line key={b.id} points={b.points} stroke="#000" strokeWidth={b.width} />)}
  </Layer>
  
  {/* Layer 4: Capitals (draggable) */}
  <Layer name="capitals">
    {territories.map(t => (
      <Circle
        key={t.id}
        x={t.centroid_px.x}
        y={t.centroid_px.y}
        radius={selectedId === t.id ? 6 : 4}
        fill="#C4943A"
        draggable
        onDragEnd={(e) => moveCapital(t.id, e.target.x(), e.target.y())}
      />
    ))}
  </Layer>
  
  {/* Layer 5: Border vertex handles (only shown when in edit mode) */}
  {editMode === 'vertices' && (
    <Layer name="handles">
      {selectedBorderVertices.map((v, i) => (
        <Circle
          key={i}
          x={v.x} y={v.y} radius={3}
          fill="#378ADD"
          draggable
          onDragMove={(e) => updateVertex(i, e.target.x(), e.target.y())}
        />
      ))}
    </Layer>
  )}
  
  {/* Layer 6: Tool overlay (brush preview, selection box) */}
  <Layer name="tools">
    {/* ... */}
  </Layer>
</Stage>
```

#### Estado com Undo/Redo

```typescript
// store/project.ts
import { create } from 'zustand';
import { temporal } from 'zundo';

interface ProjectState {
  territories: Territory[];
  borders: Border[];
  moveCapital: (id: string, lon: number, lat: number) => void;
  mergeTerritories: (ids: string[]) => void;
  splitTerritory: (id: string, cutLine: Point[]) => void;
  // ...
}

export const useProjectStore = create(
  temporal<ProjectState>(
    (set, get) => ({
      territories: [],
      borders: [],
      moveCapital: (id, lon, lat) => {
        // Optimistic local update
        set(state => ({
          territories: state.territories.map(t =>
            t.id === id ? { ...t, centroid_lon: lon, centroid_lat: lat } : t
          )
        }));
        // Request server to recalc Voronoi for affected neighbors
        api.edit.recalcVoronoi({ territoryId: id, lon, lat });
      },
      // ...
    }),
    {
      limit: 50,  // Keep last 50 snapshots
      equality: (a, b) => JSON.stringify(a.territories) === JSON.stringify(b.territories),
    }
  )
);
```

#### Endpoints de edição — Backend

```python
# api/edit.py
@router.post("/projects/{id}/edit/move-capital")
async def move_capital(
    id: str,
    territory_id: str,
    new_lon: float,
    new_lat: float,
) -> EditResult:
    """Recompute local Voronoi for affected neighbors.
    
    Strategy:
    1. Identify territories with shared borders (neighbors).
    2. Regenerate ONLY those baronies' polygons using updated centroid set.
    3. Return new polygons for frontend to apply.
    """
    neighbors = await get_neighbors(id, territory_id)
    affected_ids = [territory_id] + [n.id for n in neighbors]
    
    # Use scipy Voronoi just on affected points
    from scipy.spatial import Voronoi
    points = np.array([[t.centroid_lon, t.centroid_lat] for t in await get_territories_by_ids(affected_ids)])
    vor = Voronoi(points)
    
    # Clip to bounds, convert to polygons
    new_polygons = clip_voronoi_to_land(vor, land_mask)
    
    return {"affected": new_polygons}

@router.post("/projects/{id}/edit/merge")
async def merge_territories(id: str, territory_ids: list[str]) -> EditResult:
    """Union of polygons using Shapely."""
    from shapely.ops import unary_union
    polys = [shape(t.geometry) for t in await get_territories_by_ids(territory_ids)]
    merged = unary_union(polys)
    # Create new territory, delete old ones (in transaction)
    ...

@router.post("/projects/{id}/edit/split")
async def split_territory(id: str, territory_id: str, cut_line: list[Point]) -> EditResult:
    """Split polygon by a user-drawn line."""
    from shapely.ops import split
    poly = shape(territory.geometry)
    line = LineString([(p.lon, p.lat) for p in cut_line])
    parts = split(poly, line)
    # Return N new polygons
    ...

@router.post("/projects/{id}/edit/paint-terrain")
async def paint_terrain(
    id: str,
    terrain_type: Literal["mountain", "river", "forest", "plains"],
    stroke_points: list[Point],
    brush_size: int,
) -> EditResult:
    """Paint on terrain_lookup.png."""
    # Load terrain PNG, apply brush strokes, save
    ...
```

#### Validação em Tempo Real

```python
# services/validator.py
def validate_project(project_id: str) -> ValidationReport:
    """Returns list of issues before export allowed."""
    issues = []
    
    # Check 1: Orphan baronies (no parent county)
    for barony in baronies:
        if not barony.parent_id:
            issues.append(Issue(
                severity="error",
                code="ORPHAN_BARONY",
                message=f"Baronia '{barony.name}' sem condado pai",
                territory_id=barony.id,
            ))
    
    # Check 2: Dark pixels in ocean (rendering bug)
    terrain = load_terrain_png()
    land_mask = load_land_mask()
    dark_in_ocean = (brightness(terrain) < 50) & ~land_mask
    if np.sum(dark_in_ocean) > 0:
        issues.append(Issue(
            severity="warning",
            code="DARK_PIXELS_OCEAN",
            message=f"{np.sum(dark_in_ocean)} pixels escuros no oceano",
        ))
    
    # Check 3: Territories without capitals
    # Check 4: Territories < 200px (too small)
    # Check 5: Missing terrain type in some area
    # Check 6: Hierarchy integrity (counts add up)
    
    return ValidationReport(issues=issues)
```

#### Critérios de Aceitação — Fase 2

| # | Teste | Resultado Esperado |
|---|---|---|
| 1 | Abrir projecto Fase 1, mostrar canvas | Territórios visíveis, pan/zoom funcionais |
| 2 | Clicar em capital, arrastar | Centróide move, vizinhos recalculam em <500ms |
| 3 | Ctrl+Z após mover capital | Volta ao estado anterior |
| 4 | Seleccionar 2 territórios adjacentes, Merge | União correcta, novo território criado |
| 5 | Pintar com pincel montanha | Terrain layer actualiza em tempo real |
| 6 | Upload de SRTM como overlay | Mostra com slider de opacidade |
| 7 | Editar fronteira com vértices | Mover vértice actualiza polígono |

---

### Fase 3 — Pesquisa Histórica + Terreno Completo (2 semanas)

#### Integração LLM

```python
# services/llm.py
class LLMProvider(Protocol):
    async def research(self, prompt: str) -> dict: ...

class ClaudeProvider:
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
    
    async def research(self, prompt: str) -> dict:
        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        return parse_structured_response(response.content[0].text)

class OllamaProvider:
    async def research(self, prompt: str) -> dict:
        # Uses ollama python lib, local model
        import ollama
        response = await asyncio.to_thread(
            ollama.chat,
            model='llama3.1:70b',
            messages=[{"role": "user", "content": prompt}],
        )
        return parse_structured_response(response['message']['content'])
```

#### Prompt Template

```python
HISTORICAL_RESEARCH_PROMPT = """
És um historiador especializado em {country} durante o período {year_start}-{year_end}.

OBJECTIVO: Devolver a divisão política deste país neste período como JSON estruturado.

HIERARQUIA OBRIGATÓRIA:
1. Reinos (kingdoms) — máxima autoridade política
2. Ducados (duchies) — divisões principais dentro de reinos
3. Condados (counties) — subdivisões administrativas
4. Baronias (baronies) — unidade mais pequena (vilas, castelos)

FORMATO DE RESPOSTA (JSON puro, sem markdown):
{{
  "kingdoms": [
    {{
      "id": "asturias",
      "name": "Reino das Astúrias",
      "capital": "Oviedo",
      "notes": "Fundado por Pelágio em 718..."
    }}
  ],
  "duchies": [
    {{
      "id": "d_galiza",
      "name": "Ducado da Galiza",
      "kingdom_id": "asturias",
      "capital": "Santiago",
      "approximate_bounds": "NW of Iberian peninsula"
    }}
  ],
  "counties": [
    {{
      "id": "santiago",
      "name": "Santiago de Compostela",
      "duchy_id": "d_galiza",
      "approximate_center": [-8.54, 42.88],
      "baronies": ["santiago", "padron", "noia"]
    }}
  ]
}}

REGRAS:
- Usa factos históricos verificados (não inventes territórios)
- Coordenadas aproximadas (lon, lat) para centros administrativos
- Para cada condado, lista 2-5 baronias com nome
- Se o país estava dividido entre múltiplos reinos, inclui todos
- Considera poderes suprarregionais (cruzadas, califados) se relevantes

Responde APENAS com o JSON, sem explicações.
"""
```

#### Pincel de Terreno

```typescript
// components/tools/TerrainBrushTool.tsx
const brushTypes = {
  mountain: { color: '#8B7355', hotkey: 'M' },
  river: { color: '#4A90D9', hotkey: 'R' },
  forest: { color: '#2E5E1A', hotkey: 'F' },
  plains: { color: '#6B8E23', hotkey: 'P' },
  arid: { color: '#D4B896', hotkey: 'A' },
};

// User strokes on canvas → send to backend to update terrain_lookup.png
// Preview as overlay while painting (optimistic)
```

---

### Fase 4 — Export + Polimento (1 semana)

#### Export Unity-Ready

```python
# api/export.py
@router.post("/projects/{id}/export")
async def export_unity(id: str) -> FileResponse:
    """Generate ZIP with all Unity-ready files."""
    # Run validation first — block if errors
    report = validate_project(id)
    if report.has_errors:
        raise HTTPException(400, {"errors": report.issues})
    
    # Regenerate final PNGs with current state
    await regenerate_all(id)
    
    # Package into ZIP
    zip_path = make_zip(id, [
        "lookup_barony.png",
        "lookup_condado.png",
        "lookup_barony_colors.json",
        "lookup_condado_colors.json",
        "terrain_lookup.png",
        "terrain_types.json",
        "territory_metadata.json",
        "mountains_mask.png",
        "rivers_overlay.png",
        "visual_barony.png",
        "visual_condado.png",
        "mountain_river_data.json",
    ])
    
    return FileResponse(zip_path, filename=f"{project.name}_unity.zip")
```

#### Dialog de Export

```typescript
// Shows validation report, allows override of warnings (not errors)
// Shows estimated file sizes
// "Download" button → triggers download
// Instructions to drop into Assets/StreamingAssets/Maps/
```

---

## 5. Decisões de Design Importantes

### Porque React+Konva e não puro Canvas
- Hit detection built-in (essencial para cliques em pontos vectoriais)
- Layer system nativo (resolve z-ordering)
- Performance — usa offscreen canvas internamente
- Bindings React declarativos — menos bugs de sincronização

### Porque SQLite e não JSON plain
- Queries rápidas em projectos com 500+ territórios
- Transações atómicas (merge/split não pode deixar estado inconsistente)
- Async support via `aiosqlite`
- Backup fácil (copiar um ficheiro)

### Porque Zustand e não Redux
- API mais simples para state management
- `zundo` middleware dá undo/redo gratuito
- Sem boilerplate de actions/reducers
- TypeScript inference melhor

### Porque FastAPI e não Flask
- Async nativo (importante para LLM calls + ingestion)
- Type hints com Pydantic (validação automática)
- OpenAPI docs automáticas
- WebSocket support para live preview (futuro)

### Porque não puro frontend (sem backend)
- Voronoi em 500+ pontos é lento em JS (~2s) vs Python+scipy (~0.1s)
- Wikidata requer servidor intermediário (CORS)
- LLM API keys não podem estar no browser
- Processamento de PNGs grandes estoura memória no browser

---

## 6. Cuidados Especiais (Lições do Chat Original)

### Geração de Mapas
1. **Máscara de terra a 2x resolução independente** — aplicar DEPOIS do upscale resolve pontos pretos
2. **Upscale NEAREST** — BICUBIC/BILINEAR espalham pixels escuros para o oceano
3. **Fronteiras só em pixels de terra** — verificar `if land[y,x]` antes de pintar
4. **Smoothing σ=4.5** — σ=3.0 deixa fronteiras demasiado rectas
5. **Merge threshold 200px** — abaixo disto, territórios pequenos desaparecem

### Validação
- Detectar dois índices diferentes no mesmo ficheiro (bug do Nájera neste chat)
- Lookup index → metadata array deve usar `*ByOriginalIdx` dict, não acesso directo
- `pixel_center` do metadata é Y-down (numpy), Unity é Y-up — converter!
- `visual_*.png` é 3840×2160 → PPU=200 na Unity (não 100)

### LLM
- Validar resposta contra schema Pydantic antes de usar
- Retry automático se JSON inválido (3 tentativas)
- Ollama é 10x mais lento que Claude API — mostrar progress bar
- Cache de respostas por projecto (não re-pesquisar o mesmo país)

### Ingestão
- Wikidata: respeitar rate limits (max 1 req/s)
- OSM Overpass: usar instância Polonesa para UE (menos lag)
- SRTM/elevation: opcional, utilizador faz upload ou usa polígonos manuais
- GeoJSON pode ter rings em ordem errada → validar winding com Shapely

---

## 7. Ficheiros de Referência (incluídos)

| Ficheiro | Propósito |
|---|---|
| `map_generator.py` | Pipeline de geração completo — REUTILIZAR como biblioteca |
| `territory_data_v3.py` | Exemplo de formato (Ibéria 868 AD, 91 condados) |
| `mountain_river_data.json` | Exemplo de dados geográficos |
| `BRIEFING_MAP_TERRAIN.md` | Briefing anterior (integração Unity) |

---

## 8. Critérios de Aceitação Globais (v1.0 completa)

| # | Teste | Resultado Esperado |
|---|---|---|
| 1 | `pip install medieval-forge && medieval-forge start` | Abre browser em localhost:8000 |
| 2 | Criar projecto "Inglaterra 1066" | Registro criado em SQLite |
| 3 | Ingerir municípios | >500 paróquias descarregadas |
| 4 | Pesquisa LLM (Claude API) | Retorna reinos + ducados + condados válidos |
| 5 | Gerar mapa inicial | PNG preview visível em canvas |
| 6 | Arrastar capital de "Londres" | Voronoi recalcula em <1s |
| 7 | Pintar os Pennines com pincel montanha | Terrain layer actualiza |
| 8 | Ctrl+Z 10x, Ctrl+Y 5x | Histórico funciona perfeitamente |
| 9 | Export para Unity | ZIP com 12 ficheiros, validação passa |
| 10 | Drop dos ficheiros no Unity Reconquista | Sistema actual reconhece e carrega |

---

## 9. O Que NÃO Fazer

- NÃO reescrever `map_generator.py` — usar como biblioteca importada
- NÃO usar Tauri/Electron — webapp + localhost basta
- NÃO persistir LLM API keys no backend (só em memória da sessão)
- NÃO fazer frontend SSR (Next.js overkill) — Vite SPA é suficiente
- NÃO integrar com Unity directamente (ferramenta é offline, utilizador copia ficheiros)
- NÃO tentar rendering em GPU (Konva é DOM-based e rápido o suficiente até 1000 territórios)

---

## 10. Entregáveis Finais

### Fase 1 (fim)
- Repositório git inicial
- `pip install -e .` funcional
- Endpoints backend testados (pytest)
- Frontend mínimo que mostra preview

### Fase 2 (fim)
- Canvas completo com todos os tools de edição
- Undo/redo universal
- Validação em tempo real

### Fase 3 (fim)
- Workflow completo: país → LLM → mapa gerado → editado
- Pincel terreno funcional

### Fase 4 (fim)
- Export para Unity passa validação
- Documentação: README + USAGE.md + TUTORIAL.md
- v1.0 taggeada em git
- Vídeo tutorial (opcional)

---

## Notas Finais

O Game Designer valida cada fase no Unity com o projecto Reconquista antes de avançar. Commits sempre por **Jhonni Vieceli** (ver skill `reconquista-coder` para padrões de commit).

Este briefing substitui a conversa anterior — assume que começas do zero. Todos os ficheiros de referência estão anexados.

Estimativa total: **8-10 semanas** de desenvolvimento concentrado.
