# JORNADA DE CRIAÇÃO DO MAPA — Documentação Técnica Completa

**Para:** Claude Code (implementação do Medieval Forge)
**Por:** Game Designer (Jhonni Vieceli) via Claude Chat
**Data:** Abril 2026
**Propósito:** Replicar e automatizar este processo numa ferramenta web

---

## Como Usar Este Documento

Este documento descreve **todas as decisões, falhas e soluções** desenvolvidas ao longo de ~25 iterações para criar um mapa medieval da Península Ibérica (868 AD) para o jogo Reconquista. Ao implementar o Medieval Forge, **respeita estas decisões** — cada uma resolve um problema concreto que demorámos horas a descobrir.

Estrutura:
1. **Visão geral** — o que tentámos fazer
2. **Linha temporal de versões** — V10c → V11 → V3
3. **Pipeline final** — passos exactos do `map_generator.py`
4. **Catálogo de problemas resolvidos** — cada bug com causa e solução
5. **Lições críticas** — não repetir nestes erros
6. **Anti-padrões** — abordagens que parecem boas mas falham

---

## 1. Visão Geral

### Objectivo
Gerar mapa estilo Crusader Kings 3 da Península Ibérica em 868 AD com:
- 4 reinos jogáveis (Astúrias, Pamplona, Marca Hispânica, Emirato de Córdoba)
- ~26 ducados, ~91 condados, ~250 baronias
- Costa real (rias da Galiza, Algarve, etc.)
- Fronteiras orgânicas medievais (não rectângulos modernos)
- Hit detection pixel-perfect para Unity
- Suporte para skin visual (pergaminho) por cima

### Restrições
- Sem dados Paradox (copyright)
- Sem datasets medievais reais (não existem com este detalhe)
- Apenas dados modernos: municípios PT (CAOP) + ES (Natural Earth)
- Pesquisa histórica feita manualmente

### Outputs Finais
12 ficheiros para Unity em `Assets/StreamingAssets/Maps/`:
```
lookup_barony.png      (1920×1080) ─ hit detection baronias
lookup_condado.png     (1920×1080) ─ hit detection condados
lookup_*_colors.json               ─ RGB → ID
terrain_lookup.png     (1920×1080) ─ tipo terreno por pixel
terrain_types.json                 ─ RGB → {movement, defense, attack}
territory_metadata.json            ─ hierarquia completa
visual_condado.png     (3840×2160) ─ placeholder visual
visual_barony.png      (3840×2160) ─ placeholder visual
mountains_mask.png     (3840×2160) ─ branco=impassável
rivers_overlay.png     (3840×2160) ─ PNG transparente
mountain_river_data.json           ─ coordenadas geo
```

---

## 2. Linha Temporal de Versões

### Fase A — Exploração (V1 a V9)
**O que tentámos:** Desenhar polígonos manualmente, blur sobre coordenadas dos centros, K-means clustering das paróquias.

**Por que falhou:**
- Polígonos manuais → inviável para 250 baronias
- Blur de centros → blobs sem alinhamento com geografia
- K-means → ignora costa, gerava territórios oceânicos

**Lição:** Precisamos da geometria real dos municípios modernos, não apenas centros.

### Fase B — V10 a V10c (Voronoi + Municípios)
**Abordagem que funcionou:**
1. Carregar polígonos completos dos municípios PT+ES
2. Para cada município, atribuí-lo à baronia mais próxima (KD-tree por centroide)
3. Renderizar união de municípios por baronia → polígono final

**Resultado:** Fronteiras seguem municípios reais → costa correcta automaticamente.

**Problema:** Borda PT/ES rasterizava municípios espanhóis dentro de Portugal (Voronoi cego à fronteira).

### Fase C — V11a/b/c (Border-Aware Voronoi)
**Inovação:** Polígono manual da fronteira PT/ES → KD-trees separadas para baronias PT e ES.

```python
PBP = [(-9.50,42.20), (-8.85,41.88), ...]  # PT border polygon
pt_baronies = [b for b in baronies if b.duchy in PT_DUCHIES]
es_baronies = [b for b in baronies if b.duchy not in PT_DUCHIES]
tree_pt = cKDTree(pt_baronies)
tree_es = cKDTree(es_baronies)

# For each PT municipality, query ONLY tree_pt
# For each ES municipality, query ONLY tree_es
```

**Resultado:** Fronteira PT/ES respeitada perfeitamente.

### Fase D — V3 final
Estabilização do pipeline V11c, adição de:
- Cleanup multi-pass (median filter)
- Smoothing Gaussiano
- Coast outline interior
- Lookup maps + JSON metadata

**Estado actual:** 251 baronias, 91 condados, sistema funcional no Unity.

---

## 3. Pipeline Final (passo a passo)

Este é exactamente o que o `map_generator.py` faz. **NÃO mudar a ordem** — cada passo depende do anterior.

### Passo 1 — Carregar Dados
```python
# Municípios PT (GeoJSON com 278 concelhos modernos)
ptd = json.load(open("pt_concelhos_wgs84.geojson"))

# Municípios ES (TopoJSON com 8116 municípios modernos)
esm = decode_topojson(json.load(open("es-atlas/municipalities.json")))

# Definição histórica (a parte manual!)
from territory_data_v3 import KINGDOMS, DUCHIES, CONDADOS
# CONDADOS = [(id, name, lon, lat, duchy_id, [(barony_name, lon, lat), ...]), ...]
```

### Passo 2 — Construir Máscara de Terra a 1x
```python
def build_land_mask(pt_data, es_municipalities, target_w, target_h):
    img = Image.new("L", (target_w, target_h), 0)
    draw = ImageDraw.Draw(img)
    # Pintar cada polígono de município como branco
    for feat in pt_data['features']:
        for ring in feat['geometry']['coordinates']:
            pts = [geo_to_pixel(lon, lat) for lon, lat in ring]
            draw.polygon(pts, fill=255)
    # Idem para ES
    
    land = np.array(img) > 0
    
    # CRÍTICO: remover ilhas pequenas (<300px) que são erros de coordenadas
    labeled, n = label(land)
    sizes = np.bincount(labeled.ravel())
    main_blob = np.argmax(sizes[1:]) + 1
    for lbl in range(1, n+1):
        if lbl != main_blob and sizes[lbl] < 300:
            land[labeled == lbl] = False
    return land
```

### Passo 3 — Construir Máscara da Fronteira PT/ES
```python
def build_border_mask(border_polygon):
    # Para cada pixel, verificar se está dentro do polígono PT
    # (ray-casting algorithm)
    mask = np.zeros((H, W), dtype=bool)
    for y in range(H):
        for x in range(0, W, 3):  # sample every 3 pixels for speed
            lon, lat = pixel_to_geo(x, y)
            if point_in_polygon(lon, lat, border_polygon):
                mask[y, x:x+3] = True
    return mask
```

### Passo 4 — Setup das Baronias (KD-trees Separadas)
```python
PT_DUCHIES = {"d_portucale", "d_gharb", "d_fronteira"}

bars = []  # all baronies as (name, px, py, condado_idx, duchy_id, kingdom_id)
bpt = []   # is_portugal flag

for ci, condado in enumerate(CONDADOS):
    duchy_id = condado[4]
    for barony_name, blon, blat in condado[5]:
        px, py = geo_to_pixel(blon, blat)
        bars.append((barony_name, px, py, ci, duchy_id, DUCHIES[duchy_id][0]))
        bpt.append(duchy_id in PT_DUCHIES)

pt_indices = [i for i in range(len(bars)) if bpt[i]]
es_indices = [i for i in range(len(bars)) if not bpt[i]]

tree_pt = cKDTree(np.array([(bars[i][1], bars[i][2]) for i in pt_indices]))
tree_es = cKDTree(np.array([(bars[i][1], bars[i][2]) for i in es_indices]))
```

### Passo 5 — Rasterizar Baronias
```python
result = np.full((H, W), -1, dtype=np.int16)

# Para cada município PT, encontrar a baronia PT mais próxima
for feat in pt_data['features']:
    centroid = compute_centroid(feat)
    px, py = geo_to_pixel(*centroid)
    _, local_idx = tree_pt.query([px, py])
    barony_idx = pt_indices[local_idx]
    # Pintar TODOS os pixels deste município com este barony_idx
    for ring in feat['geometry']['coordinates']:
        pts = [geo_to_pixel(lo, la) for lo, la in ring]
        ImageDraw.Draw(result_img).polygon(pts, fill=barony_idx)

# Idem para ES com tree_es
# Resultado: cada pixel de terra tem barony_idx atribuído
```

### Passo 6 — Cleanup Multi-Pass (Median Filter)
**Por quê:** Pixels nas fronteiras de municípios criam ruído (1-2px de uma baronia dentro de outra).

```python
for pass_n in range(8):
    raw_int32 = raw.astype(np.int32)
    raw_int32[~land] = 9999  # marker para ignorar oceano
    
    # Kernel decrescente: 11, 11, 9, 9, 7, 7, 5, 5
    kernel = 11 if pass_n < 2 else 9 if pass_n < 4 else 7 if pass_n < 6 else 5
    cleaned = median_filter(raw_int32, size=kernel)
    cleaned[~land] = -1
    
    valid = (raw >= 0) & (cleaned >= 0) & (cleaned < num_baronies)
    raw[valid] = cleaned[valid]
    raw[~land] = -1
```

### Passo 7 — Remover Fragmentos Disconectados
```python
# Para cada baronia, encontrar todas as componentes conectadas
# Se houver múltiplas, manter só a maior (a "main") e fundir as outras com vizinhos
for bi in range(num_baronies):
    mask = raw == bi
    if not mask.any(): continue
    
    labeled, n_components = label(mask)
    if n_components <= 1: continue
    
    sizes = np.bincount(labeled.ravel())
    main = np.argmax(sizes[1:]) + 1
    
    for component_lbl in range(1, n_components+1):
        if component_lbl != main and sizes[component_lbl] < 600:
            fragment = labeled == component_lbl
            # Encontrar baronia vizinha mais comum
            dilated = binary_dilation(fragment, iterations=5)
            border = dilated & ~fragment & (raw >= 0) & (raw != bi)
            if border.any():
                neighbor_id = mode(raw[border])
                raw[fragment] = neighbor_id
```

### Passo 8 — Smoothing Gaussiano
**Por quê:** Fronteiras seguem perímetros de municípios → muito rectangulares. Gaussian smoothing torna-as orgânicas.

```python
# Para cada baronia, aplicar Gaussian na sua máscara, depois pegar onde a máscara é mais "intensa"
best = np.zeros((H, W), dtype=np.float32)
result = np.full((H, W), -1, dtype=np.int16)

for cid in np.unique(raw[raw >= 0]):
    mask = (raw == cid).astype(np.float32)
    mask[~land] = 0
    
    npx = mask.sum()
    sigma = 4.5 if npx > 400 else max(1.5, 4.5 * (npx/400))  # smaller sigma para baronias pequenas
    
    blurred = gaussian_filter(mask, sigma=sigma)
    blurred[~land] = 0
    
    better = blurred > best
    result[better] = cid
    best[better] = blurred[better]

result[~land] = -1
```

**CRÍTICO:** Sigma=4.5 é o sweet spot. Sigma=3.0 → fronteiras demasiado rectas. Sigma=6.0 → baronias pequenas absorvidas.

### Passo 9 — Merge Final de Baronias Mínimas
```python
# Se uma baronia ficou com <200 pixels após smoothing, fundi-la com vizinha
for bi in range(num_baronies):
    npx = (result == bi).sum()
    if npx == 0 or npx >= 200: continue
    
    mask = result == bi
    dilated = binary_dilation(mask, iterations=5)
    border = dilated & ~mask & (result >= 0) & (result != bi)
    if border.any():
        result[mask] = mode(result[border])
```

### Passo 10 — Construir Máscara de Terra a 2x (INDEPENDENTE)
**ESTA É A CHAVE PARA RESOLVER OS PONTOS PRETOS NO OCEANO.**

```python
# NÃO fazer upscale da máscara 1x!
# Construir do zero a 2x resolução, dos polígonos originais.
land_2x = build_land_mask(pt_data, es_municipalities, 3840, 2160)

# Esta máscara é usada APÓS o upscale visual para forçar oceano fora dela.
```

### Passo 11 — Renderizar Visual
```python
visual = np.zeros((H, W, 3), dtype=np.uint8)

# 1. Pintar cada baronia com cor do reino (com variação)
for bi in range(num_baronies):
    mask = result == bi
    base = KINGDOM_COLORS[bk[bi]]
    # Variação por ducado/condado/baronia para textura
    var = ((bd[bi]*23+7) % 25) - 12 + ((bc[bi]*17+5) % 20) - 10
    visual[mask] = clip(base + var, 30, 240)

# 2. Pintar oceano com gradiente
ocean = ~land
distance = distance_transform_edt(ocean)
gradient = clip(distance / 150, 0, 1)
visual[:,:,0][ocean] = (45 + (70-45)*gradient)[ocean]  # blue gradient

# 3. Desenhar fronteiras APENAS em pixels de terra
for dy, dx in [(0,1), (1,0)]:
    a = result[:,:-1] if dy==0 else result[:-1,:]
    b = result[:,1:] if dy==0 else result[1:,:]
    diff = (a != b) & (a >= 0) & (b >= 0)
    
    # Para cada transição, decidir grossura por hierarquia:
    # kingdom border = 5px, duchy = 3px, county = 2px, barony = 1px
    # ONLY paint if land[y,x] is True (NUNCA pintar no oceano!)
    ...
```

### Passo 12 — Upscale com NEAREST + Aplicação da Máscara 2x
**ABSOLUTAMENTE CRÍTICO:**

```python
# NÃO usar BICUBIC ou BILINEAR! Espalham pixels escuros para o oceano.
img_2x = visual_pil.resize((3840, 2160), Image.NEAREST)

# Forçar oceano em TODOS os pixels fora da máscara 2x
not_land_2x = ~land_2x
img_2x_arr[:,:,0][not_land_2x] = ocean_r_2x[not_land_2x]
img_2x_arr[:,:,1][not_land_2x] = ocean_g_2x[not_land_2x]
img_2x_arr[:,:,2][not_land_2x] = ocean_b_2x[not_land_2x]

# Adicionar contorno costeiro INTERIOR (2px dentro da terra)
coast_inner = land_2x & ~binary_erosion(land_2x, iterations=2)
img_2x_arr[coast_inner] = [15, 10, 5]  # quase preto
```

### Passo 13 — Lookup Maps
```python
# Cor única por baronia (RGB determinístico)
lookup_b = np.zeros((H, W, 3), dtype=np.uint8)
colors_b = {}
for bi in range(num_baronies):
    mask = result == bi
    if not mask.any(): continue
    r = (bi*37 + 50) % 256
    g = (bi*73 + 80) % 256
    b = (bi*113 + 30) % 256
    lookup_b[mask] = [r, g, b]
    colors_b[f"{r},{g},{b}"] = bi  # ESTE ÍNDICE É O ORIGINAL

Image.fromarray(lookup_b).save("lookup_barony.png")
json.dump(colors_b, open("lookup_barony_colors.json", "w"))
```

### Passo 14 — Metadata JSON
```python
metadata = {
    "region": "iberia_868ad",
    "map_size": [3840, 2160],
    "kingdoms": {...},
    "duchies": {...},
    "condados": [...],   # ARRAY COMPACTADO (sem condados vazios)
    "baronies": [...],
}
```

**⚠ BUG CRÍTICO DESCOBERTO:** O array `condados` no metadata é compactado (skipa entradas sem pixels), mas `lookup_condado_colors.json` mantém os índices originais. Isto causou o bug "Lisboa aparece como Santarém".

**Solução obrigatória:** Manter dois mapeamentos no Unity:
- `colorMap` (RGB → original_idx)
- `byOriginalIdx` (original_idx → metadata entry)

---

## 4. Catálogo de Problemas Resolvidos

### Bug #1 — Pontos Pretos no Oceano (15+ tentativas para resolver)

**Sintoma:** Pixels escuros aparecem no oceano, especialmente perto da costa.

**Causa raiz (descoberta após muitas tentativas):**
- BICUBIC/BILINEAR upscale interpola entre pixels
- Pixels da costa (escuros) são interpolados com pixels do oceano (azul)
- Resultado: manchas escuras no oceano

**Soluções TENTADAS que NÃO funcionaram:**
1. Aumentar erosão da máscara terra → cortou peninsulas reais
2. GaussianBlur antes do upscale → espalhou ainda mais
3. Suavizar contorno costeiro com Gaussian → criou anéis de cor
4. Detectar e pintar pixels escuros após upscale → falsos positivos

**SOLUÇÃO QUE FUNCIONOU:**
1. Construir máscara de terra a 2x **independentemente** dos polígonos originais
2. Upscale visual com **NEAREST** (não BICUBIC/BILINEAR)
3. Aplicar máscara 2x APÓS upscale: forçar oceano em todos pixels fora da máscara

```python
# WRONG (causa pontos pretos):
img_2x = img_1x.resize((3840, 2160), Image.BICUBIC)

# RIGHT (zero pontos pretos):
img_2x = img_1x.resize((3840, 2160), Image.NEAREST)
land_2x = build_land_mask_at_2x_independently(...)
img_2x[~land_2x] = ocean_color
```

### Bug #2 — Bug do Nájera (Lisboa = Santarém)

**Sintoma:** Clicar em Lisboa mostra "Santarém". Todos condados com índice >44 estão off-by-one.

**Causa raiz:**
- Gerador Python skipa condados sem pixels em ambos `lookup_colors.json` e `metadata.json`
- Mas `lookup` mantém índices originais (gap em 45)
- Enquanto `metadata` re-compacta (sem gap)
- `metadata.condados[60]` no Unity NÃO é o original 60, é o original 61

**SOLUÇÃO:** Construir mapeamento `byOriginalIdx`:
```python
# No metadata, incluir o índice original:
metadata["condados"].append({
    "id": condado.id,
    "name": condado.name,
    "original_idx": ci,  # ← CRÍTICO
    ...
})

# No Unity, usar dictionary lookup:
Dictionary<int, CondadoEntry> CondadoByOriginalIdx;
// Ao detectar cor, usar:
condado = CondadoByOriginalIdx[colorMap[rgb]];
```

### Bug #3 — Fronteiras "Modernas" Demasiado Rectas

**Sintoma:** Fronteiras seguem municípios modernos (rectangulares), não medievais (orgânicas).

**Tentativas falhadas:**
- Sigma=2.0, 3.0 → ainda muito recto
- Manual smoothing splines → muito complexo
- Polígonos manuais → inviável

**Solução parcial:** Sigma=4.5 nos baronia maiores, sigma reduzido em baronias pequenas:
```python
sigma = 4.5 if npx > 400 else max(1.5, 4.5 * (npx/400))
```

**Solução real (futura para Medieval Forge):** **Editor vectorial manual** — utilizador ajusta pontos onde precisa.

### Bug #4 — Inversão Y (Numpy vs Unity)

**Sintoma:** Pixel center no metadata aponta para localização errada no Unity.

**Causa:** Numpy usa Y-down (origem topo-esquerda), Unity Y-up (origem baixo-esquerda). PNG carregado com `Texture2D.LoadImage` flipa Y automaticamente.

**Solução no Unity:**
```csharp
public Color32 GetPixelAt(int numpyX, int numpyY) {
    int unityY = texture.height - 1 - numpyY;
    return texture.GetPixel(numpyX, unityY);
}
```

### Bug #5 — Costa Recta no L do Cádiz

**Sintoma:** Costa entre Cádiz e Algarve aparece como linha diagonal recta (tipo Voronoi).

**Causa:** Não havia baronias suficientes nessa zona costeira → KD-tree colocava pontos longe.

**Solução:** Adicionar 13 pontos costeiros entre Sanlúcar e Ayamonte na fronteira PT/ES, garantindo que cada zona tem baronia próxima.

### Bug #6 — Tejo Não Chega a Lisboa

**Sintoma:** Rio Tejo termina em Santarém (~-8.8, 39.1) sem chegar a Lisboa.

**Causa:** Natural Earth 50m trunca o rio (dados grosseiros).

**Solução:** Adicionar pontos manuais até estuário de Lisboa (-9.14, 38.72).

```python
# tejo_coords originalmente terminava em (-8.8, 39.1)
# Adicionado:
extra_tejo_points = [
    (-8.95, 38.78), (-9.05, 38.74), (-9.14, 38.72)
]
```

### Bug #7 — Conflent (0 pixels)

**Sintoma:** Condado de Conflent existe no metadata mas tem 0 pixels no mapa.

**Causa:** Coordenadas estão na fronteira francesa, fora dos dados de municípios.

**Solução:** Aceitar perda — Conflent ficou fora do jogo, ou seria necessário adicionar dados franceses.

**Lição para Medieval Forge:** Mostrar warning ao utilizador quando um território fica vazio.

---

## 5. Lições Críticas (NÃO IGNORAR)

### Sobre Geração
1. **NUNCA usar BICUBIC para upscale** — só NEAREST
2. **SEMPRE construir máscaras 2x independentemente** — não fazer upscale de máscaras
3. **NUNCA suavizar contorno costeiro com blur** — usa erosão+inversão
4. **Sigma 4.5 é o sweet spot** — não mexer sem testar
5. **Median filter precisa de múltiplas passes** com kernel decrescente
6. **Marker -1 para oceano, 9999 para "ignorar"** durante median filter

### Sobre Borders PT/ES
7. **KD-trees SEPARADAS** para baronias PT e ES
8. **Polígono de fronteira** define a separação (ray-casting)
9. **Sample fronteira a cada 3 pixels** (não cada pixel — lento demais)

### Sobre Hierarquia
10. **Manter `original_idx`** em todos os outputs JSON
11. **Lookup → metadata** precisa SEMPRE de mapeamento explícito
12. **Compactar metadata** mas preservar índices originais

### Sobre Costa
13. **Adicionar pontos costeiros suficientes** — KD-tree precisa de pontos próximos
14. **Validar visualmente** antes de aceitar — costa recta = pontos em falta

### Sobre Rios e Montanhas
15. **Natural Earth 50m é grosseiro** — usar como base, refinar manualmente
16. **Coordenadas da Wikipedia** funcionam para rios principais
17. **Polígonos manuais** para sistemas montanhosos (não há dados livres bons)

### Sobre Performance
18. **Cleanup é caro** — 8 passes × median filter pode ser >10s
19. **scipy.spatial.cKDTree** é 100x mais rápido que loops Python
20. **Numpy operations** sempre que possível, não loops

### Sobre Unity Integration
21. **PPU=200** para texturas 3840×2160 (não 100)
22. **FilterMode.Point** obrigatório nos lookups (sem interpolação)
23. **No compression** nos PNG de lookup
24. **Newtonsoft JSON** para parsing (Unity JsonUtility não suporta dictionaries)

---

## 6. Anti-Padrões (Aprendidos da Forma Difícil)

### ❌ Anti-Padrão #1 — "Vou desenhar polígonos manualmente"
**Problema:** 250 baronias × 50 pontos = 12,500 pontos manuais. Impossível manter.
**Correcto:** Geração automática + edição vectorial nos pontos críticos.

### ❌ Anti-Padrão #2 — "GaussianBlur resolve tudo"
**Problema:** Blur espalha pixels escuros, suaviza demais, esconde detalhes.
**Correcto:** Median filter para limpeza, Gaussian APENAS na máscara binária para suavizar fronteiras.

### ❌ Anti-Padrão #3 — "Vou fazer upscale e depois pintar oceano"
**Problema:** BICUBIC já contaminou os pixels do oceano com valores escuros.
**Correcto:** NEAREST upscale + máscara 2x independente.

### ❌ Anti-Padrão #4 — "K-means para definir territórios"
**Problema:** K-means ignora costa, pode gerar territórios oceânicos.
**Correcto:** Voronoi a partir de centros pré-definidos, com máscara de terra.

### ❌ Anti-Padrão #5 — "Vou usar dados Paradox como referência"
**Problema:** Copyright. E os mapas Paradox têm erros conhecidos.
**Correcto:** Apenas dados públicos (Natural Earth, OSM, CAOP, Wikidata).

### ❌ Anti-Padrão #6 — "Iteração cega: gerar → ver"
**Problema:** Fizemos 25+ iterações cegas, cada uma demorou minutos.
**Correcto (para Medieval Forge):** Preview live em canvas vectorial.

### ❌ Anti-Padrão #7 — "Detectar pontos pretos com regex de pixel"
**Problema:** Falsos positivos (sombras legítimas), falsos negativos (pixels apenas ligeiramente escuros).
**Correcto:** Não criar o problema — usar máscara correcta no upscale.

### ❌ Anti-Padrão #8 — "JSON com chave RGB como string"
**Problema:** `{"123,45,67": 0}` é frágil. Whitespace, ordem dos componentes.
**Correcto:** Funcionou na prática mas considera tuplos `[r,g,b]` ou hex `"#7B2D43"`.

### ❌ Anti-Padrão #9 — "Vou tentar múltiplos rendering tweaks de uma vez"
**Problema:** Quando funciona, não sabemos qual tweak funcionou.
**Correcto:** Mudar UMA coisa, testar, validar, commit, próxima.

### ❌ Anti-Padrão #10 — "Vou começar do zero quando algo correr mal"
**Problema:** Perdemos horas de trabalho.
**Correcto:** Snapshots do estado em cada passo importante. Para Medieval Forge: undo/redo obrigatório.

---

## 7. Workflow Replicável (Para Medieval Forge)

Este é o workflow que o utilizador deve seguir na ferramenta:

### Passo 1 — Setup Inicial (5 min)
1. Escolher país (Portugal, Inglaterra, etc)
2. Escolher período histórico (868 AD, 1066, 1492)
3. Definir bounds geográficos (lon/lat min/max)

### Passo 2 — Ingestão de Dados (1-2 min auto)
- Wikidata SPARQL → municípios + capitais
- Natural Earth → rios, costa
- (Opcional) Upload de mapa de relevo SRTM

### Passo 3 — Pesquisa Histórica (5 min com LLM)
- Prompt automatizado: "Dá-me a divisão política de {país} em {ano}"
- LLM devolve estrutura: kingdoms → duchies → counties → baronies
- Utilizador valida no UI: editar nomes, mover capitais

### Passo 4 — Geração Inicial (30s)
- Pipeline correr automático
- Preview em canvas

### Passo 5 — Validação Visual
Sistema marca automaticamente:
- ⚠ Territórios sem pixels
- ⚠ Pontos escuros no oceano (não devia haver)
- ⚠ Costa recta (precisa de mais pontos)
- ⚠ Baronias <200px (vão ser fundidas)

### Passo 6 — Edição Manual (a parte importante)
**Por ordem de prioridade (escolhida pelo utilizador):**
1. Mover capital → recálculo Voronoi local
2. Editar pontos vectoriais de fronteiras
3. Mesclar/dividir territórios
4. Pintar terreno (montanha/rio/floresta)
5. Undo/redo histórico

### Passo 7 — Export Unity
- Validação final (bloqueia se erros)
- ZIP com 12 ficheiros prontos
- Drop em `Assets/StreamingAssets/Maps/`

---

## 8. Ferramentas e Bibliotecas Validadas

### Backend Python (testado e funciona)
```python
numpy             # Arrays, máscaras
scipy.spatial.cKDTree  # KD-tree para Voronoi
scipy.ndimage     # gaussian_filter, median_filter, binary_dilation, label, distance_transform_edt
PIL (Pillow)      # PNG I/O, polygon rasterization
shapely           # Operações booleanas em polígonos
```

### Dados Geográficos (validados como funcionais)
```
Wikidata SPARQL    # Municípios via P31/P279 + P625 (coordinates)
                   # Country QIDs: PT=Q45, ES=Q29, GB=Q145, FR=Q142, IT=Q38, DE=Q183
Natural Earth      # Rios via sane-topojson npm package
                   # Coastlines (50m e 110m)
OpenStreetMap      # Overpass API (fallback se Wikidata incompleto)
CAOP Portugal      # Carta Administrativa Oficial (fonte oficial PT)
INE Spain          # Instituto Nacional de Estadística (fonte oficial ES)
SRTM elevation     # 1arcsec via OpenTopography (precisa registo)
```

### Frontend (recomendação — não testado neste chat)
```
React 18 + TypeScript + Vite
Konva.js + react-konva  # Canvas com layers
Zustand + zundo         # State + undo/redo
TanStack Query          # API calls
Tailwind CSS v4
Radix UI primitives
```

---

## 9. Métricas Reais do Pipeline

Para Ibéria 868 AD (referência):
- Municípios PT carregados: **278 concelhos**
- Municípios ES carregados: **8,116 municipios**
- Baronias finais: **251** (originalmente definidas: 257, 6 fundidas)
- Condados finais: **91** (originalmente 92, 1 vazio: Conflent)
- Tempo de geração total: **~45 segundos** num CPU moderno
- Tempo só para median filter passes: ~12s
- Tempo só para Gaussian smoothing: ~8s
- Tempo só para rasterização: ~3s
- Tamanho dos outputs: **~6 MB** (12 ficheiros)

---

## 10. Próximos Passos Sugeridos para Medieval Forge

Em ordem de implementação:

### Fase 1 (MVP)
1. Backend FastAPI com endpoints de projecto
2. Wrapper para `map_generator.py` existente
3. Frontend mínimo: form + botão "gerar" + preview PNG
4. **Validar:** consegue replicar o mapa Ibéria deste chat

### Fase 2 (Editor)
5. Canvas Konva com camadas
6. Ferramenta de mover capital + recálculo Voronoi local
7. Undo/redo
8. **Validar:** consegue mover capital de Lisboa, ver fronteiras actualizarem

### Fase 3 (Pesquisa Histórica)
9. Integração Anthropic API (utilizador traz chave)
10. Prompt template para extrair hierarquia
11. Validação manual no UI
12. **Validar:** consegue criar projecto Inglaterra 1066 do zero

### Fase 4 (Polish)
13. Pincel terreno
14. Validação automática
15. Export ZIP
16. **Validar:** drop dos ficheiros no Unity Reconquista funciona

---

## Apêndice A — Coordenadas Validadas

### Bounds Ibéria
```python
LON_MIN, LON_MAX = -13.2, 8.2
LAT_MIN, LAT_MAX = 35.4, 44.6
LON_SCALE = math.cos(math.radians(40.0))
```

### Polígono Fronteira PT/ES (validado)
38 pontos definindo limite oeste de Espanha (= limite leste Portugal):
```python
PBP = [
    (-9.50,42.20), (-8.85,41.88), (-8.16,41.82), (-7.92,41.88),
    (-7.40,41.87), (-7.17,41.97), (-6.93,41.94), (-6.81,41.95),
    (-6.55,41.68), (-6.38,41.65), (-6.19,41.57), (-6.54,41.37),
    (-6.80,41.13), (-6.93,41.03), (-6.86,40.89), (-6.86,40.27),
    (-6.90,40.11), (-6.96,39.91), (-7.04,39.67), (-7.02,39.47),
    (-7.26,39.21), (-7.42,39.18), (-7.30,39.05), (-7.16,38.96),
    (-7.07,38.81), (-7.06,38.65), (-7.17,38.44), (-7.25,38.24),
    (-7.35,38.14), (-7.42,38.00), (-7.48,37.82), (-7.44,37.65),
    (-7.50,37.50), (-7.46,37.38), (-7.43,37.26), (-7.41,37.18),
    (-7.38,37.08), (-7.40,36.90), (-9.50,36.90), (-9.50,42.20),
]
```

### Cores dos Reinos (Ibéria 868)
```python
KINGDOM_COLORS = {
    0: (190, 158, 82),    # Astúrias — dourado
    1: (148, 88, 168),    # Pamplona — roxo
    2: (198, 108, 128),   # Marca Hispânica — rosa
    3: (68, 158, 62),     # Emirato — verde
}
```

---

## Apêndice B — Scripts e Ferramentas Anexas

Anexar a este briefing:
- `map_generator.py` — pipeline completo (620 linhas)
- `territory_data_v3.py` — base de dados Ibéria 868 (308 linhas)
- `mountain_river_data.json` — dados geográficos validados
- `BRIEFING_MEDIEVAL_FORGE.md` — briefing principal de implementação

---

## Conclusão

Este documento captura ~30 horas de iteração e debug condensadas em ~600 linhas. Cada bug listado custou tempo real para descobrir. Cada anti-padrão foi tentado e falhou. Cada lição crítica é dura ganhada.

**Para o Medieval Forge:** segue o pipeline da secção 3 sem o reinventar. Implementa as validações da secção 4 desde o início. Evita os anti-padrões da secção 6 conscientemente. O resultado será uma ferramenta robusta que poupa ao próximo utilizador todas as horas que perdemos aqui.

Boa sorte.
