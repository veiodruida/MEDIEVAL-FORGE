# RECONQUISTA — MAPA PIXEL LOOKUP V3
# Gerar mapa técnico a partir de dados GeoJSON reais
# Lê o CLAUDE_CODE_BRIEFING_v27.md antes de começar.

---

## OBJECTIVO

Gerar um ficheiro PNG 1400x1000 onde cada pixel tem a cor
sólida do território a que pertence. Este ficheiro é o
"lookup map" — ao clicar numa posição no Unity, o jogo
faz GetPixel(x,y) e obtém o territoryId.

Dados de entrada: GeoJSON reais de províncias ibéricas.
Dados de saída: PNG lookup + JSON de mapeamento para Unity.

---

## PASSO 1 — Script Python completo

Criar ficheiro: Tools/generate_lookup_map.py

```python
#!/usr/bin/env python3
"""
Reconquista — Pixel Lookup Map Generator
Descarrega GeoJSON reais e gera lookup map para Unity.
"""

import json
import math
import urllib.request
import os
from PIL import Image, ImageDraw

# ── Configuração ──────────────────────────────────────────

OUTPUT_PNG  = "../Assets/StreamingAssets/Maps/lookup_map.png"
OUTPUT_JSON = "../Assets/StreamingAssets/Maps/territory_colors.json"
MAP_WIDTH   = 1400
MAP_HEIGHT  = 1000

# Bounding box da Península Ibérica
LON_MIN, LON_MAX = -9.5,  4.5
LAT_MIN, LAT_MAX = 35.5, 44.5

# URLs dos dados GeoJSON reais
SPAIN_GEOJSON_URL = (
    "https://raw.githubusercontent.com/codeforgermany/"
    "click_that_hood/main/public/data/spain-provinces.geojson"
)
PORTUGAL_GEOJSON_URL = (
    "https://raw.githubusercontent.com/codeforgermany/"
    "click_that_hood/main/public/data/portugal-districts.geojson"
)

# ── Mapeamento: nome da província → territory_id do jogo ──

PROVINCE_TO_TERRITORY = {
    # ── PORTUGAL (distritos) ──────────────────────────────
    "Braga":            "portucale_braga",
    "Viana do Castelo": "portucale_braga",    # merge: Norte PT
    "Guimarães":        "portucale_guimaraes",
    "Porto":            "portucale_porto",
    "Aveiro":           "portucale_porto",    # merge: litoral
    "Vila Real":        "portucale_chaves",
    "Bragança":         "portucale_braganca",
    "Viseu":            "fronteira_viseu",
    "Guarda":           "fronteira_idanha",
    "Castelo Branco":   "fronteira_idanha",
    "Coimbra":          "fronteira_coimbra",
    "Leiria":           "fronteira_coimbra",  # merge: litoral
    "Lisboa":           "gharb_lisboa",
    "Santarém":         "gharb_santarem",
    "Setúbal":          "gharb_lisboa",       # merge: estuário Tejo
    "Évora":            "gharb_evora",
    "Portalegre":       "gharb_evora",        # merge: Alentejo norte
    "Beja":             "gharb_beja",
    "Faro":             "gharb_silves",
    "Viana do Alentejo":"gharb_mertola",      # merge interior sul
    # Nota: Mértola está em Beja mas precisa split
    # Usamos coordenadas para distinguir Beja/Mértola

    # ── ESPANHA (províncias) ──────────────────────────────

    # GALIZA
    "A Coruña":         "galiza_coruna",
    "Lugo":             "galiza_lugo",
    "Ourense":          "galiza_ourense",
    "Pontevedra":       "galiza_tui",

    # ASTÚRIAS
    "Asturias":         "asturias_oviedo",

    # CANTÁBRIA / NORTE
    "Cantabria":        "cantabria",

    # PAÍS BASCO
    "Álava":            "alava",
    "Vizcaya":          "vasconia",
    "Guipúzcoa":        "vasconia",

    # LEÃO
    "León":             "leon_capital",
    "Zamora":           "leon_zamora",
    "Salamanca":        "leon_salamanca",
    "Palencia":         "leon_palencia",
    "Valladolid":       "leon_valladolid",
    "Ávila":            "leon_salamanca",     # merge: sul Leão

    # CASTELA
    "Burgos":           "castela_burgos",
    "Soria":            "castela_soria",
    "La Rioja":         "castela_logrono",
    "Segovia":          "castela_osma",       # merge
    "Guadalajara":      "marca_guadalajara",

    # NAVARRA / ARAGÃO
    "Navarra":          "navarra_pamplona",
    "Huesca":           "aragon_jaca",        # norte = cristão
    "Zaragoza":         "marca_zaragoza",
    "Teruel":           "marca_zaragoza",     # merge

    # CATALUNHA
    "Barcelona":        "barcelona_capital",
    "Girona":           "barcelona_girona",
    "Lleida":           "marca_lleida",
    "Tarragona":        "marca_tortosa",

    # AL-ANDALUS NORTE / MARCA MÉDIA
    "Madrid":           "marca_madrid",
    "Toledo":           "marca_toledo",
    "Cuenca":           "marca_toledo",       # merge: interior
    "Ciudad Real":      "marca_toledo",       # merge

    # EXTREMADURA MUÇULMANA
    "Cáceres":          "extrem_caceres",
    "Badajoz":          "extrem_badajoz",

    # CÓRDOBA E SUL
    "Córdoba":          "cordoba_capital",
    "Jaén":             "cordoba_jaen",
    "Granada":          "cordoba_granada",
    "Málaga":           "levante_malaga",
    "Almería":          "levante_almeria",
    "Sevilla":          "cordoba_sevilla",
    "Huelva":           "cordoba_sevilla",    # merge: oeste Andaluzia
    "Cádiz":            "cordoba_algeciras",

    # LEVANTE
    "Valencia":         "levante_valencia",
    "Castellón":        "levante_valencia",   # merge
    "Alicante":         "levante_murcia",
    "Murcia":           "levante_murcia",

    # ILHAS
    "Islas Baleares":   "baleares",           # muçulmano em 868
    "Ibiza":            "baleares",
}

# ── Cores por território (RGB) ────────────────────────────
# Cada território tem uma cor ÚNICA — sem repetições

TERRITORY_COLORS = {
    # ASTÚRIAS (verdes escuros)
    "asturias_oviedo":      (60,  100,  70),
    "cantabria":            (70,  115,  80),
    "liebana":              (55,   90,  65),
    "alava":                (50,   85,  60),
    "vasconia":             (45,   80,  55),

    # GALIZA (azuis claros)
    "galiza_coruna":        (100, 150, 200),
    "galiza_lugo":          (90,  140, 190),
    "galiza_ourense":       (80,  130, 180),
    "galiza_tui":           (70,  120, 170),

    # PORTUGAL (azuis escuros)
    "portucale_braga":      (40,   70, 140),
    "portucale_guimaraes":  (50,   80, 150),
    "portucale_porto":      (35,   65, 130),
    "portucale_chaves":     (55,   85, 155),
    "portucale_braganca":   (60,   90, 160),
    "portucale_lamego":     (45,   75, 145),

    # FRONTEIRA MUÇULMANA (castanho claro)
    "fronteira_coimbra":    (160, 110,  60),
    "fronteira_viseu":      (170, 120,  65),
    "fronteira_idanha":     (180, 130,  70),

    # LEÃO (vermelhos escuros)
    "leon_capital":         (140,  25,  25),
    "leon_astorga":         (150,  35,  30),
    "leon_zamora":          (130,  20,  20),
    "leon_salamanca":       (155,  40,  35),
    "leon_palencia":        (145,  30,  28),
    "leon_valladolid":      (160,  45,  40),

    # CASTELA (dourados)
    "castela_burgos":       (195, 148,  55),
    "castela_soria":        (185, 138,  48),
    "castela_logrono":      (205, 158,  62),
    "castela_osma":         (175, 128,  42),

    # NAVARRA (roxos)
    "navarra_pamplona":     (100,  70, 150),
    "navarra_sangüesa":     (110,  80, 160),

    # ARAGÃO (âmbar)
    "aragon_jaca":          (180, 130,  15),
    "aragon_sobrarbe":      (170, 120,  10),

    # BARCELONA / CONDADOS CATALÃES (vermelho catalão)
    "barcelona_capital":    (200,  45,  45),
    "barcelona_girona":     (190,  38,  38),
    "barcelona_urgell":     (180,  32,  32),
    "barcelona_empuries":   (170,  26,  26),

    # MARCA SUPERIOR — muçulmana (laranjas escuros)
    "marca_zaragoza":       (160,  75,  25),
    "marca_huesca":         (150,  65,  20),
    "marca_lleida":         (170,  85,  30),
    "marca_tortosa":        (180,  95,  35),

    # MARCA MÉDIA — muçulmana (laranjas médios)
    "marca_toledo":         (200,  95,  10),
    "marca_talavera":       (190,  85,   8),
    "marca_madrid":         (185,  80,   6),
    "marca_guadalajara":    (195,  90,  12),
    "marca_medinaceli":     (205, 100,  15),

    # EXTREMADURA — muçulmana (castanhos alaranjados)
    "extrem_merida":        (165,  85,  30),
    "extrem_badajoz":       (155,  75,  25),
    "extrem_caceres":       (145,  65,  20),
    "extrem_trujillo":      (175,  95,  35),

    # GHARB AL-ANDALUS (castanhos claros — actual Portugal sul)
    "gharb_lisboa":         (190, 140,  80),
    "gharb_santarem":       (180, 130,  72),
    "gharb_evora":          (200, 150,  88),
    "gharb_beja":           (170, 120,  65),
    "gharb_silves":         (160, 110,  58),
    "gharb_mertola":        (150, 100,  52),

    # EMIRATO DE CÓRDOBA (castanhos muito escuros)
    "cordoba_capital":      ( 90,  15,   5),
    "cordoba_sevilla":      (100,  20,   8),
    "cordoba_jaen":         (110,  25,  10),
    "cordoba_granada":      (105,  22,   9),
    "cordoba_algeciras":    ( 95,  18,   7),

    # LEVANTE — muçulmano (avermelhados escuros)
    "levante_malaga":       (130,  35,  20),
    "levante_almeria":      (140,  42,  25),
    "levante_murcia":       (150,  48,  30),
    "levante_valencia":     (160,  55,  35),
    "levante_denia":        (170,  62,  40),

    # ILHAS
    "baleares":             (140,  60,  30),

    # OCEANO (não é território — cor de fundo)
    "_ocean":               ( 70, 130, 180),
}

# ── Funções de conversão ──────────────────────────────────

def lon_to_x(lon):
    return int((lon - LON_MIN) / (LON_MAX - LON_MIN) * MAP_WIDTH)

def lat_to_y(lat):
    # Inverter Y: latitude alta = y pequeno no ecrã
    return int((1 - (lat - LAT_MIN) / (LAT_MAX - LAT_MIN)) * MAP_HEIGHT)

def coords_to_pixels(coordinates):
    """Converter lista de [lon, lat] para lista de (x, y)."""
    result = []
    for coord in coordinates:
        if len(coord) >= 2:
            x = lon_to_x(coord[0])
            y = lat_to_y(coord[1])
            # Só incluir pontos dentro do mapa
            if 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT:
                result.append((x, y))
    return result

def get_province_name(feature):
    """Extrair nome da província do GeoJSON feature."""
    props = feature.get("properties", {})
    # Tentar vários campos de nome
    for key in ["name", "NAME", "provincia", "PROVINCIA",
                "distrito", "DISTRITO", "NAME_1", "nom"]:
        if key in props and props[key]:
            return props[key]
    return None

def draw_feature(draw, feature, color):
    """Desenhar um feature GeoJSON no PIL ImageDraw."""
    geom = feature.get("geometry", {})
    geom_type = geom.get("type", "")
    coords = geom.get("coordinates", [])

    if geom_type == "Polygon":
        draw_polygon(draw, coords[0], color)

    elif geom_type == "MultiPolygon":
        for polygon in coords:
            if polygon:
                draw_polygon(draw, polygon[0], color)

def draw_polygon(draw, ring, color):
    """Desenhar um polígono simples."""
    pixels = coords_to_pixels(ring)
    if len(pixels) >= 3:
        draw.polygon(pixels, fill=color)

# ── Main ──────────────────────────────────────────────────

def main():
    print("Reconquista — Pixel Lookup Map Generator")
    print("=" * 50)

    # Criar directórios de output
    os.makedirs(os.path.dirname(OUTPUT_PNG),  exist_ok=True)
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

    # Criar imagem base com cor do oceano
    ocean_color = TERRITORY_COLORS["_ocean"]
    img  = Image.new("RGB", (MAP_WIDTH, MAP_HEIGHT), ocean_color)
    draw = ImageDraw.Draw(img)

    print(f"Canvas: {MAP_WIDTH}x{MAP_HEIGHT}")
    print(f"Bbox: lon [{LON_MIN}, {LON_MAX}], lat [{LAT_MIN}, {LAT_MAX}]")

    # ── Descarregar e processar Portugal ──────────────────
    print("\nA descarregar Portugal GeoJSON...")
    try:
        with urllib.request.urlopen(PORTUGAL_GEOJSON_URL) as r:
            pt_data = json.loads(r.read().decode("utf-8"))
        print(f"  {len(pt_data['features'])} distritos carregados")

        for feature in pt_data["features"]:
            name = get_province_name(feature)
            if not name:
                continue
            territory_id = PROVINCE_TO_TERRITORY.get(name)
            if not territory_id:
                print(f"  AVISO: '{name}' não mapeado")
                continue
            color = TERRITORY_COLORS.get(territory_id)
            if not color:
                print(f"  AVISO: cor não definida para '{territory_id}'")
                continue
            draw_feature(draw, feature, color)
            print(f"  ✓ {name} → {territory_id}")

    except Exception as e:
        print(f"  ERRO Portugal: {e}")

    # ── Descarregar e processar Espanha ───────────────────
    print("\nA descarregar Espanha GeoJSON...")
    try:
        with urllib.request.urlopen(SPAIN_GEOJSON_URL) as r:
            es_data = json.loads(r.read().decode("utf-8"))
        print(f"  {len(es_data['features'])} províncias carregadas")

        for feature in es_data["features"]:
            name = get_province_name(feature)
            if not name:
                continue
            territory_id = PROVINCE_TO_TERRITORY.get(name)
            if not territory_id:
                print(f"  AVISO: '{name}' não mapeado")
                continue
            color = TERRITORY_COLORS.get(territory_id)
            if not color:
                print(f"  AVISO: cor não definida para '{territory_id}'")
                continue
            draw_feature(draw, feature, color)
            print(f"  ✓ {name} → {territory_id}")

    except Exception as e:
        print(f"  ERRO Espanha: {e}")

    # ── Desenhar bordas ───────────────────────────────────
    print("\nA desenhar bordas...")
    # Criar segunda passagem para bordas negras
    # (pixels onde cor do vizinho é diferente)
    border_img = img.copy()
    border_draw = ImageDraw.Draw(border_img)

    pixels = img.load()
    for x in range(1, MAP_WIDTH - 1):
        for y in range(1, MAP_HEIGHT - 1):
            c = pixels[x, y]
            if c == ocean_color:
                continue
            # Verificar vizinhos
            neighbors = [
                pixels[x-1, y], pixels[x+1, y],
                pixels[x, y-1], pixels[x, y+1]
            ]
            for n in neighbors:
                if n != c and n != ocean_color:
                    border_img.putpixel((x, y), (20, 15, 10))
                    break

    # ── Guardar lookup map (SEM bordas — só cores puras) ──
    print(f"\nA guardar lookup map: {OUTPUT_PNG}")
    img.save(OUTPUT_PNG, "PNG")
    print("  ✓ Lookup map guardado")

    # ── Guardar versão com bordas (para preview) ──────────
    preview_path = OUTPUT_PNG.replace(".png", "_preview.png")
    border_img.save(preview_path, "PNG")
    print(f"  ✓ Preview com bordas: {preview_path}")

    # ── Gerar JSON de mapeamento cor → território ─────────
    color_map = {}
    for territory_id, rgb in TERRITORY_COLORS.items():
        if territory_id.startswith("_"):
            continue
        hex_color = "#{:02x}{:02x}{:02x}".format(*rgb)
        color_map[hex_color] = territory_id

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(color_map, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Color map JSON: {OUTPUT_JSON}")

    # ── Estatísticas ──────────────────────────────────────
    print("\n" + "=" * 50)
    print("ESTATÍSTICAS:")
    color_counts = {}
    pixels = img.load()
    for x in range(MAP_WIDTH):
        for y in range(MAP_HEIGHT):
            c = pixels[x, y]
            color_counts[c] = color_counts.get(c, 0) + 1

    territories_found = 0
    for territory_id, rgb in TERRITORY_COLORS.items():
        if territory_id.startswith("_"):
            continue
        count = color_counts.get(rgb, 0)
        if count > 0:
            territories_found += 1
            print(f"  {territory_id}: {count:,} pixels")
        else:
            print(f"  {territory_id}: NÃO ENCONTRADO ⚠️")

    print(f"\nTotal territórios com pixels: {territories_found}")
    print("CONCLUÍDO!")

if __name__ == "__main__":
    main()
```

---

## PASSO 2 — Instalar dependências e executar

```bash
# No terminal, na pasta do projecto Unity:
pip install Pillow --break-system-packages
cd Tools
python generate_lookup_map.py
```

Resultado esperado:
- `Assets/StreamingAssets/Maps/lookup_map.png` — lookup map puro
- `Assets/StreamingAssets/Maps/lookup_map_preview.png` — versão com bordas visíveis
- `Assets/StreamingAssets/Maps/territory_colors.json` — mapeamento cor→id

---

## PASSO 3 — PixelMapController.cs no Unity

Criar `Assets/Scripts/UI/Map/PixelMapController.cs`

```csharp
using UnityEngine;
using UnityEngine.UI;
using System.Collections;
using System.Collections.Generic;
using System.IO;

/// <summary>
/// Sistema de lookup map baseado em pixels.
/// Ao clicar no mapa, lê o pixel da textura de lookup
/// e devolve o territoryId correspondente.
/// </summary>
public class PixelMapController : MonoBehaviour
{
    public static PixelMapController Instance { get; private set; }

    [Header("Lookup Map")]
    [SerializeField] private Texture2D _lookupTexture;
    [SerializeField] private RectTransform _mapRect;
    [SerializeField] private RawImage _mapDisplay; // arte do mapa

    // Mapeamento: cor (hex) → territoryId
    private Dictionary<Color32, string> _colorToTerritory = new();
    private bool _isReady = false;

    // Território actualmente seleccionado
    private string _selectedTerritoryId = "";

    // Evento
    public static event System.Action<string> OnTerritoryClicked;

    void Awake()
    {
        Instance = this;
    }

    IEnumerator Start()
    {
        yield return LoadLookupTexture();
        yield return LoadColorMap();
        _isReady = true;
        Debug.Log($"[PixelMap] Pronto. " +
                  $"{_colorToTerritory.Count} territórios mapeados.");
    }

    // ── Carregar textura de lookup ────────────────────────

    IEnumerator LoadLookupTexture()
    {
        string path = Path.Combine(
            Application.streamingAssetsPath,
            "Maps", "lookup_map.png");

        if (!File.Exists(path))
        {
            Debug.LogError($"[PixelMap] Lookup map não encontrado: {path}");
            yield break;
        }

        byte[] data = File.ReadAllBytes(path);
        _lookupTexture = new Texture2D(2, 2,
            TextureFormat.RGB24, false);
        _lookupTexture.LoadImage(data);
        // CRÍTICO: sem compressão, sem filtro
        _lookupTexture.filterMode = FilterMode.Point;
        _lookupTexture.wrapMode   = TextureWrapMode.Clamp;

        Debug.Log($"[PixelMap] Lookup texture carregada: " +
                  $"{_lookupTexture.width}x{_lookupTexture.height}");
    }

    // ── Carregar mapeamento cor→território ───────────────

    IEnumerator LoadColorMap()
    {
        string path = Path.Combine(
            Application.streamingAssetsPath,
            "Maps", "territory_colors.json");

        if (!File.Exists(path))
        {
            Debug.LogError($"[PixelMap] Color map não encontrado: {path}");
            yield break;
        }

        string json = File.ReadAllText(path);
        var raw = JsonUtility.FromJson<ColorMapWrapper>(json);

        // Converter hex → Color32
        foreach (var entry in raw.entries)
        {
            if (ColorUtility.TryParseHtmlString(
                entry.hex, out Color c))
            {
                Color32 c32 = c;
                _colorToTerritory[c32] = entry.territoryId;
            }
        }

        Debug.Log($"[PixelMap] {_colorToTerritory.Count} cores mapeadas.");
        yield return null;
    }

    // ── Hit detection ─────────────────────────────────────

    /// <summary>
    /// Dado um ponto no ecrã, devolve o territoryId.
    /// Retorna "" se oceano ou fora do mapa.
    /// </summary>
    public string GetTerritoryAtScreenPoint(Vector2 screenPoint)
    {
        if (!_isReady || _lookupTexture == null) return "";

        // Converter ponto de ecrã para coordenadas UV do mapa
        if (!RectTransformUtility.ScreenPointToLocalPointInRectangle(
            _mapRect, screenPoint, null, out Vector2 localPoint))
            return "";

        // Normalizar para [0,1]
        Rect rect = _mapRect.rect;
        float u = (localPoint.x - rect.x) / rect.width;
        float v = (localPoint.y - rect.y) / rect.height;

        if (u < 0 || u > 1 || v < 0 || v > 1) return "";

        // Sample do pixel
        int px = Mathf.RoundToInt(u * (_lookupTexture.width  - 1));
        int py = Mathf.RoundToInt(v * (_lookupTexture.height - 1));

        Color32 pixel = _lookupTexture.GetPixel(px, py);

        // Lookup na tabela
        // Procurar cor mais próxima (tolerância de 5 por canal)
        return FindClosestTerritory(pixel);
    }

    string FindClosestTerritory(Color32 pixel)
    {
        // Verificar cor exacta primeiro
        if (_colorToTerritory.TryGetValue(pixel, out string id))
            return id;

        // Cor mais próxima com tolerância (para anti-aliasing)
        string closest  = "";
        int    minDist  = 30; // tolerância máxima

        foreach (var kvp in _colorToTerritory)
        {
            int dr = Mathf.Abs(pixel.r - kvp.Key.r);
            int dg = Mathf.Abs(pixel.g - kvp.Key.g);
            int db = Mathf.Abs(pixel.b - kvp.Key.b);
            int dist = dr + dg + db;

            if (dist < minDist)
            {
                minDist = dist;
                closest = kvp.Value;
            }
        }
        return closest;
    }

    // ── Input handling ────────────────────────────────────

    void Update()
    {
        if (!_isReady) return;

        // Touch (mobile)
        if (Input.touchCount > 0)
        {
            var touch = Input.GetTouch(0);
            if (touch.phase == TouchPhase.Began)
                HandleClick(touch.position);
        }
        // Mouse (editor / PC)
        else if (Input.GetMouseButtonDown(0))
        {
            HandleClick(Input.mousePosition);
        }
    }

    void HandleClick(Vector2 screenPos)
    {
        string territoryId = GetTerritoryAtScreenPoint(screenPos);

        if (string.IsNullOrEmpty(territoryId))
        {
            // Clique no oceano — desseleccionar
            DeselectAll();
            return;
        }

        _selectedTerritoryId = territoryId;
        OnTerritoryClicked?.Invoke(territoryId);

        // Abrir tooltip
        TerritoryTooltipController.Instance?
            .Show(territoryId, screenPos);

        #if UNITY_EDITOR || DEVELOPMENT_BUILD
        Debug.Log($"[PixelMap] Clique: {territoryId}");
        #endif
    }

    public void DeselectAll()
    {
        _selectedTerritoryId = "";
        TerritoryTooltipController.Instance?.Hide();
    }

    public string GetSelectedTerritory() => _selectedTerritoryId;

    // ── Overlay de highlight ──────────────────────────────

    /// <summary>
    /// Gerar textura de highlight para o território seleccionado.
    /// Pixels do território ficam brancos, resto transparente.
    /// </summary>
    public Texture2D GenerateHighlightTexture(string territoryId)
    {
        if (_lookupTexture == null) return null;

        var highlight = new Texture2D(
            _lookupTexture.width,
            _lookupTexture.height,
            TextureFormat.RGBA32, false);

        // Encontrar cor do território
        Color32 targetColor = default;
        bool found = false;
        foreach (var kvp in _colorToTerritory)
        {
            if (kvp.Value == territoryId)
            {
                targetColor = kvp.Key;
                found = true;
                break;
            }
        }

        if (!found) return null;

        var pixels = _lookupTexture.GetPixels32();
        var output = new Color32[pixels.Length];

        for (int i = 0; i < pixels.Length; i++)
        {
            int dr = Mathf.Abs(pixels[i].r - targetColor.r);
            int dg = Mathf.Abs(pixels[i].g - targetColor.g);
            int db = Mathf.Abs(pixels[i].b - targetColor.b);

            if (dr + dg + db < 20)
                output[i] = new Color32(255, 255, 255, 120);
            else
                output[i] = new Color32(0, 0, 0, 0);
        }

        highlight.SetPixels32(output);
        highlight.Apply();
        highlight.filterMode = FilterMode.Point;
        return highlight;
    }
}

// Helper para deserializar JSON
[System.Serializable]
public class ColorMapWrapper
{
    public ColorMapEntry[] entries;
}

[System.Serializable]
public class ColorMapEntry
{
    public string hex;
    public string territoryId;
}
```

---

## PASSO 4 — Atribuição dos territórios por bookmark

Para cada bookmark (868, 1035, 1085, etc.), definir
quem controla cada território em GameSetupData.cs.

### Bookmark 868 — Vímara Peres

```
PLAYER (portucale):
  portucale_braga, portucale_guimaraes, portucale_porto,
  portucale_chaves, portucale_braganca, portucale_lamego

REINO DAS ASTÚRIAS (npc):
  asturias_oviedo, cantabria, liebana, alava, vasconia,
  galiza_coruna, galiza_lugo, galiza_ourense, galiza_tui

REINO DE LEÃO (npc):
  leon_capital, leon_astorga, leon_zamora, leon_salamanca,
  leon_palencia, leon_valladolid

CASTELA (npc, vassalo de Leão):
  castela_burgos, castela_soria, castela_logrono, castela_osma

NAVARRA (npc):
  navarra_pamplona, navarra_sangüesa

ARAGÃO (npc):
  aragon_jaca, aragon_sobrarbe

BARCELONA (npc):
  barcelona_capital, barcelona_girona, barcelona_urgell,
  barcelona_empuries

EMIRATO DE CÓRDOBA (npc muçulmano):
  fronteira_coimbra, fronteira_viseu, fronteira_idanha,
  marca_zaragoza, marca_huesca, marca_lleida, marca_tortosa,
  marca_toledo, marca_talavera, marca_madrid, marca_guadalajara,
  marca_medinaceli, extrem_merida, extrem_badajoz,
  extrem_caceres, extrem_trujillo, gharb_lisboa, gharb_santarem,
  gharb_evora, gharb_beja, gharb_silves, gharb_mertola,
  cordoba_capital, cordoba_sevilla, cordoba_jaen, cordoba_granada,
  cordoba_algeciras, levante_malaga, levante_almeria,
  levante_murcia, levante_valencia, levante_denia, baleares
  
  NOTA: Tudela (navarra_tudela) = muçulmano em 868
```

---

## PASSO 5 — Importar arte do Gemini

A arte visual usa o melhor mapa do Gemini como textura:

```csharp
// Em PixelMapController, o _mapDisplay (RawImage) usa
// o mapa artístico do Gemini como textura visual.
// O _lookupTexture fica invisível — só para hit detection.

// Em MapSetup.cs:
void SetupMap()
{
    // Arte visual (Gemini map)
    _mapDisplay.texture = Resources.Load<Texture2D>(
        "Maps/iberia_868_art");

    // Lookup invisível (gerado pelo Python)
    // Carregado automaticamente pelo PixelMapController
}
```

---

## TESTES DE VALIDAÇÃO

```
☐ T1: Executar Python script → sem erros → 2 ficheiros criados
☐ T2: Abrir lookup_map_preview.png →
       Peninsula Ibérica visível com fronteiras claras
☐ T3: Verificar que CADA território tem pixels (log do script)
☐ T4: Play no Unity → sem erros de carregamento
☐ T5: Clicar em Braga → log "[PixelMap] Clique: portucale_braga"
☐ T6: Clicar em León → log "[PixelMap] Clique: leon_capital"
☐ T7: Clicar em Córdoba → log "[PixelMap] Clique: cordoba_capital"
☐ T8: Clicar no oceano → log vazio, tooltip fecha
☐ T9: Clicar em Lisboa → log "[PixelMap] Clique: gharb_lisboa"
☐ T10: Highlight de território funciona (pixel branco)
```
