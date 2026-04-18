# RECONQUISTA — MAPA HISTÓRICO V2
# 40 Territórios Ibéricos (Bookmark 868 AD)
# Lê o CLAUDE_CODE_BRIEFING_v27.md antes de começar.

---

## CONTEXTO

O mapa actual tem 10 territórios com polígonos aproximados
e sem fronteiras claras. Este briefing substitui-o completamente
com 40 territórios historicamente correctos, gerados a partir
de coordenadas geográficas reais.

Não há arte ainda — isso vem de uma IA especializada em imagem.
Por agora: polígonos sólidos com cor por reino, fronteiras visíveis,
ícones de texto simples para capitais e fortalezas.

---

## SISTEMA DE COORDENADAS

O mapa Unity tem 1200 × 900 unidades (world space).
Corresponde à Península Ibérica:

```
Longitude: -9.5° (costa oeste Portugal) → 3.5° (leste, Barcelona)
Latitude:  35.5° (Gibraltar) → 44.0° (norte Galiza/Astúrias)

Fórmula de conversão:
  x_unity = (longitude - (-9.5)) * 92.3
  y_unity = (latitude  - 35.5)  * 105.9

O eixo Y cresce para cima (norte = y maior) — correcto para Unity 2D.
```

### Método de Geração de Polígonos — Voronoi

Em vez de polígonos manuais, usar geração procedural
baseada nos centros dos territórios:

```csharp
// Algoritmo:
// 1. Para cada pixel do mapa, encontrar o território
//    cujo centro está mais próximo.
// 2. Esse pixel pertence a esse território.
// 3. Pixels na fronteira (vizinhos de territórios diferentes)
//    formam as linhas de fronteira.

// Implementação simplificada para Unity:
// Usar uma textura 1200x900 onde cada pixel tem a cor
// do reino do território mais próximo.
// Depois renderizar os polígonos via MeshRenderer.
```

---

## OS 40 TERRITÓRIOS — DADOS COMPLETOS

Formato de cada entrada:
```
id | nome_histórico | reino | centro_x | centro_y |
   fort_level | has_capital | has_market | has_temple |
   cultura | religião | população | dev
```

### REINO DAS ASTÚRIAS (cor: #4A7C59 verde escuro)

```
asturias_oviedo | Oviedo | asturias |
  337 | 832 | 4 | true | true | true |
  asturian | catholic | 2500 | 6
  NOTA: Capital real, sede do reino

asturias_gijon | Gijón | asturias |
  354 | 851 | 2 | false | true | false |
  asturian | catholic | 1200 | 3
  NOTA: Porto costeiro

asturias_cangas | Cangas de Onís | asturias |
  404 | 831 | 2 | false | false | true |
  asturian | catholic | 800 | 2
  NOTA: Antiga capital, valor histórico

cantabria | Cantábria | asturias |
  505 | 816 | 1 | false | false | false |
  cantabrian | catholic | 900 | 2

alava | Álava | asturias |
  630 | 778 | 2 | false | false | false |
  basque | catholic | 700 | 2
  NOTA: Território basca, culturalmente distinto

vasconia | Vascónia | asturias |
  709 | 812 | 1 | false | false | false |
  basque | catholic | 600 | 1
```

### GALIZA (cor: #5B8DB8 azul claro)

```
galiza_compostela | Santiago de Compostela | galiza |
  89 | 781 | 3 | false | true | true |
  galician_portuguese | catholic | 2000 | 5
  NOTA: Maior centro religioso ibérico, Caminho de Santiago

galiza_lugo | Lugo | galiza |
  179 | 795 | 2 | false | false | true |
  galician_portuguese | catholic | 1100 | 3

galiza_tui | Tui | galiza |
  78 | 694 | 2 | false | true | false |
  galician_portuguese | catholic | 900 | 3
  NOTA: Fronteira com Portugal, diocese importante
```

### CONDADO PORTUCALENSE (cor: #2B5090 azul)

```
portucale_braga | Braga | portugal |
  99 | 641 | 3 | true | true | true |
  galician_portuguese | catholic | 1800 | 5
  NOTA: Diocese primacial, capital do condado

portucale_guimaraes | Guimarães | portugal |
  112 | 629 | 2 | false | false | false |
  galician_portuguese | catholic | 900 | 3

portucale_porto | Porto | portugal |
  82 | 598 | 2 | false | true | false |
  galician_portuguese | catholic | 1200 | 4
  NOTA: Porto atlântico, rota comercial

portucale_lamego | Lamego | portugal |
  156 | 593 | 2 | false | false | true |
  galician_portuguese | catholic | 800 | 3

portucale_chaves | Chaves | portugal |
  187 | 661 | 2 | false | false | false |
  galician_portuguese | catholic | 600 | 2

portucale_braganca | Bragança | portugal |
  253 | 668 | 1 | false | false | false |
  galician_portuguese | catholic | 500 | 2
```

### ZONA DE FRONTEIRA — TERRITÓRIOS CONTESTADOS

```
fronteira_coimbra | Coimbra | cordoba |
  99 | 499 | 3 | false | true | false |
  mozarab | sunni | 2000 | 5
  NOTA: Muçulmana em 868, reconquistada em 878

fronteira_viseu | Viseu | cordoba |
  147 | 546 | 2 | false | false | false |
  mozarab | sunni | 800 | 3
  NOTA: Disputada, muda de mãos várias vezes
```

### REINO DE LEÃO (cor: #8B1A1A vermelho escuro)

```
leon_capital | León | leon |
  363 | 752 | 4 | true | true | true |
  leonese | catholic | 3000 | 6
  NOTA: Capital do reino, herdeiro das Astúrias

leon_astorga | Astorga | leon |
  317 | 737 | 3 | false | false | true |
  leonese | catholic | 1200 | 4
  NOTA: Diocese importante, Via da Prata

leon_zamora | Zamora | leon |
  347 | 635 | 3 | false | true | false |
  leonese | catholic | 1500 | 4

leon_salamanca | Salamanca | leon |
  354 | 579 | 2 | false | true | false |
  leonese | catholic | 1000 | 3

leon_palencia | Palência | leon |
  459 | 689 | 2 | false | false | false |
  leonese | catholic | 800 | 3
```

### CASTELA (cor: #C4943A dourado)

```
castela_burgos | Burgos | castela |
  535 | 724 | 3 | true | true | false |
  castilian | catholic | 1500 | 4
  NOTA: Capital da Castela nascente, Caminho de Santiago

castela_soria | Sória | castela |
  649 | 664 | 2 | false | false | false |
  castilian | catholic | 700 | 2
  NOTA: Fronteira sul de Castela

castela_logrono | Logroño (Rioja) | castela |
  618 | 724 | 2 | false | true | false |
  castilian | catholic | 900 | 3
  NOTA: Zona vinícola, Caminho de Santiago
```

### NAVARRA (cor: #6B4C9A roxo)

```
navarra_pamplona | Pamplona | navarra |
  724 | 775 | 3 | true | true | true |
  navarrese | catholic | 1800 | 5
  NOTA: Capital do reino de Pamplona

navarra_tudela | Tudela | cordoba |
  728 | 695 | 2 | false | true | false |
  arabic_andalusi | sunni | 1200 | 4
  NOTA: Cidade muçulmana no Ebro, disputada
```

### ARAGÃO / CONDADOS CATALÃES (cor: #B8860B)

```
aragon_jaca | Jaca (Aragão) | aragon |
  826 | 749 | 2 | true | false | true |
  aragonese | catholic | 800 | 3
  NOTA: Capital do condado de Aragão nascente

aragon_zaragoza | Saragoça | cordoba |
  795 | 651 | 5 | false | true | true |
  arabic_andalusi | sunni | 4000 | 7
  NOTA: Capital da Marca Superior, cidade major

aragon_barcelona | Barcelona | barcelona |
  967 | 712 | 4 | true | true | true |
  catalan | catholic | 2500 | 6
  NOTA: Condado de Barcelona, porta mediterrânica

aragon_lleida | Lleida | cordoba |
  893 | 673 | 3 | false | true | false |
  arabic_andalusi | sunni | 1500 | 4
```

### AL-ANDALUS — NORTE (cor: #C47A1A laranja)

```
andalus_toledo | Toledo | cordoba |
  506 | 462 | 5 | true | true | true |
  mozarab | sunni | 5000 | 8
  NOTA: Antiga capital visigoda, centro intelectual

andalus_madrid | Madrid (Magerit) | cordoba |
  535 | 521 | 2 | false | false | false |
  arabic_andalusi | sunni | 600 | 2
  NOTA: Fortaleza menor, construída para defender Toledo

andalus_guadalajara | Guadalajara | cordoba |
  585 | 543 | 2 | false | false | false |
  arabic_andalusi | sunni | 700 | 2

andalus_talavera | Talavera da Rainha | cordoba |
  431 | 472 | 2 | false | true | false |
  mozarab | sunni | 1200 | 3

andalus_caceres | Cáceres | cordoba |
  289 | 420 | 2 | false | false | false |
  arabic_andalusi | sunni | 800 | 2

andalus_merida | Mérida | cordoba |
  292 | 362 | 3 | false | true | true |
  mozarab | sunni | 2000 | 5
  NOTA: Antiga capital romana, rica em monumentos

andalus_badajoz | Badajoz | cordoba |
  233 | 358 | 3 | false | true | false |
  arabic_andalusi | sunni | 1800 | 4
  NOTA: Futura Taifa de Badajoz, fronteira com Portugal
```

### EMIRATO DE CÓRDOBA — SUL (cor: #8B2500 vermelho escuro)

```
cordoba_capital | Córdoba | cordoba |
  436 | 253 | 5 | true | true | true |
  arabic_andalusi | sunni | 10000 | 9
  NOTA: A cidade mais avançada da Europa em 868.
  Capital do Emirato. Dev 9, Fort 5.

cordoba_sevilla | Sevilha | cordoba |
  324 | 199 | 4 | false | true | true |
  arabic_andalusi | sunni | 5000 | 7

cordoba_jaen | Jaén | cordoba |
  524 | 231 | 3 | false | false | true |
  arabic_andalusi | sunni | 1500 | 4

cordoba_granada | Granada | cordoba |
  545 | 178 | 3 | false | true | true |
  arabic_andalusi | sunni | 2000 | 5

cordoba_malaga | Málaga | cordoba |
  469 | 129 | 3 | false | true | false |
  arabic_andalusi | sunni | 2000 | 5
  NOTA: Porto mediterrânico, comércio com Norte África

cordoba_almeria | Almeria | cordoba |
  649 | 142 | 3 | false | true | false |
  arabic_andalusi | sunni | 1800 | 5
  NOTA: Porto de seda, ligação ao Mediterrâneo Oriental
```

---

## ADJACÊNCIAS COMPLETAS

Lista de pares adjacentes (baseada na geografia real):

```csharp
// Formato: { "territoryA", "territoryB" }
// Dois territórios são adjacentes se partilham fronteira terrestre.
// Costeiros podem ser adjacentes por mar se indicado.

private static readonly string[,] Adjacencies = {
  // ASTÚRIAS internas
  { "asturias_oviedo",    "asturias_gijon" },
  { "asturias_oviedo",    "asturias_cangas" },
  { "asturias_oviedo",    "galiza_lugo" },
  { "asturias_gijon",     "cantabria" },
  { "asturias_cangas",    "cantabria" },
  { "cantabria",          "alava" },
  { "cantabria",          "castela_burgos" },
  { "alava",              "vasconia" },
  { "alava",              "navarra_pamplona" },
  { "alava",              "castela_burgos" },
  { "vasconia",           "navarra_pamplona" },
  { "vasconia",           "aragon_jaca" },

  // ASTÚRIAS → GALIZA
  { "asturias_oviedo",    "galiza_lugo" },

  // GALIZA interna
  { "galiza_compostela",  "galiza_lugo" },
  { "galiza_compostela",  "galiza_tui" },
  { "galiza_lugo",        "galiza_tui" },
  { "galiza_lugo",        "portucale_braga" },
  { "galiza_lugo",        "portucale_braganca" },

  // GALIZA → PORTUGAL
  { "galiza_tui",         "portucale_braga" },
  { "galiza_compostela",  "portucale_porto" },

  // PORTUGAL interno
  { "portucale_braga",    "portucale_guimaraes" },
  { "portucale_braga",    "portucale_porto" },
  { "portucale_braga",    "portucale_chaves" },
  { "portucale_guimaraes","portucale_porto" },
  { "portucale_guimaraes","portucale_lamego" },
  { "portucale_porto",    "portucale_lamego" },
  { "portucale_porto",    "fronteira_coimbra" },
  { "portucale_lamego",   "portucale_chaves" },
  { "portucale_lamego",   "portucale_braganca" },
  { "portucale_lamego",   "fronteira_viseu" },
  { "portucale_lamego",   "fronteira_coimbra" },
  { "portucale_chaves",   "portucale_braganca" },
  { "portucale_braganca", "leon_astorga" },

  // PORTUGAL → FRONTEIRA
  { "portucale_lamego",   "fronteira_viseu" },
  { "fronteira_coimbra",  "fronteira_viseu" },
  { "fronteira_coimbra",  "andalus_caceres" },
  { "fronteira_viseu",    "leon_salamanca" },
  { "fronteira_viseu",    "andalus_merida" },

  // LEÃO interno
  { "leon_capital",       "leon_astorga" },
  { "leon_capital",       "leon_zamora" },
  { "leon_capital",       "leon_palencia" },
  { "leon_astorga",       "leon_zamora" },
  { "leon_astorga",       "portucale_braganca" },
  { "leon_zamora",        "leon_salamanca" },
  { "leon_zamora",        "leon_palencia" },
  { "leon_salamanca",     "andalus_caceres" },
  { "leon_palencia",      "castela_burgos" },
  { "leon_palencia",      "castela_soria" },

  // LEÃO → CASTELA
  { "leon_capital",       "castela_burgos" },
  { "leon_palencia",      "castela_burgos" },

  // CASTELA interna
  { "castela_burgos",     "castela_logrono" },
  { "castela_burgos",     "castela_soria" },
  { "castela_logrono",    "navarra_pamplona" },
  { "castela_logrono",    "aragon_zaragoza" },
  { "castela_soria",      "aragon_zaragoza" },
  { "castela_soria",      "andalus_guadalajara" },

  // NAVARRA / ARAGÃO
  { "navarra_pamplona",   "navarra_tudela" },
  { "navarra_pamplona",   "aragon_jaca" },
  { "navarra_tudela",     "aragon_zaragoza" },
  { "aragon_jaca",        "aragon_zaragoza" },
  { "aragon_jaca",        "aragon_barcelona" },
  { "aragon_zaragoza",    "aragon_lleida" },
  { "aragon_lleida",      "aragon_barcelona" },

  // AL-ANDALUS NORTE interno
  { "andalus_toledo",     "andalus_madrid" },
  { "andalus_toledo",     "andalus_guadalajara" },
  { "andalus_toledo",     "andalus_talavera" },
  { "andalus_toledo",     "andalus_caceres" },
  { "andalus_madrid",     "andalus_guadalajara" },
  { "andalus_madrid",     "andalus_talavera" },
  { "andalus_guadalajara","aragon_zaragoza" },
  { "andalus_talavera",   "andalus_caceres" },
  { "andalus_talavera",   "andalus_merida" },
  { "andalus_caceres",    "andalus_merida" },
  { "andalus_merida",     "andalus_badajoz" },
  { "andalus_merida",     "cordoba_capital" },

  // AL-ANDALUS NORTE → CÓRDOBA
  { "andalus_toledo",     "cordoba_capital" },
  { "andalus_toledo",     "cordoba_jaen" },
  { "andalus_badajoz",    "cordoba_sevilla" },

  // CÓRDOBA interno
  { "cordoba_capital",    "cordoba_sevilla" },
  { "cordoba_capital",    "cordoba_jaen" },
  { "cordoba_capital",    "cordoba_granada" },
  { "cordoba_sevilla",    "cordoba_malaga" },
  { "cordoba_jaen",       "cordoba_granada" },
  { "cordoba_jaen",       "cordoba_almeria" },
  { "cordoba_granada",    "cordoba_malaga" },
  { "cordoba_granada",    "cordoba_almeria" },
};
```

---

## CORES POR REINO

```csharp
public static readonly Dictionary<string, Color> KingdomColors =
    new() {
    { "asturias",  new Color(0.29f, 0.49f, 0.35f) }, // Verde escuro
    { "galiza",    new Color(0.36f, 0.55f, 0.72f) }, // Azul claro
    { "portugal",  new Color(0.17f, 0.31f, 0.56f) }, // Azul real
    { "leon",      new Color(0.55f, 0.10f, 0.10f) }, // Vermelho escuro
    { "castela",   new Color(0.77f, 0.58f, 0.23f) }, // Dourado
    { "navarra",   new Color(0.42f, 0.30f, 0.60f) }, // Roxo
    { "aragon",    new Color(0.72f, 0.53f, 0.07f) }, // Âmbar
    { "barcelona", new Color(0.85f, 0.20f, 0.20f) }, // Vermelho Catalão
    { "cordoba",   new Color(0.55f, 0.15f, 0.00f) }, // Vermelho islâmico
    { "neutral",   new Color(0.55f, 0.50f, 0.40f) }, // Cinzento terra
    // Jogador: sempre azul brilhante por cima da cor base
};

// Ocupado durante guerra: cor do ocupante com 60% opacidade
// Território do jogador: cor do reino + borda branca
// Capital: símbolo ♛ em branco sobre o território
```

---

## IMPLEMENTAÇÃO — PASSO A PASSO

### PASSO 1 — Novo TerritoryData com coordenadas geográficas

Adicionar a TerritoryData.cs:

```csharp
[Header("Coordenadas do Mapa")]
public Vector2 centerPosition;   // centro em world space Unity
public Vector2[] polygonVertices; // gerado via Voronoi
public string kingdomId;          // "portugal", "leon", etc.
public bool   isKingdomCapital;
public bool   hasMarket;
public bool   hasTemple;
public int    fortificationLevel; // 0-5
```

### PASSO 2 — MapDataGenerator.cs (Editor Tool)

Criar Assets/Editor/MapDataGenerator.cs

Menu: Reconquista > Map > Generate Territory Data

Este script:
1. Lê os dados dos 40 territórios hardcoded (do briefing)
2. Cria ou actualiza os TerritoryData ScriptableObjects
3. Calcula polígonos Voronoi baseados nos centros
4. Guarda as adjacências

```csharp
[MenuItem("Reconquista/Map/Generate Territory Data")]
static void GenerateMap()
{
    // 1. Definir os 40 territórios (dados do briefing)
    var territories = GetTerritoryDefinitions();

    // 2. Calcular polígonos Voronoi
    var polygons = CalculateVoronoiPolygons(
        territories,
        mapWidth: 1200f,
        mapHeight: 900f);

    // 3. Criar/actualizar ScriptableObjects
    foreach (var t in territories)
    {
        string path = $"Assets/ScriptableObjects/Territories/{t.id}.asset";
        var data = AssetDatabase.LoadAssetAtPath<TerritoryData>(path)
                ?? ScriptableObject.CreateInstance<TerritoryData>();

        data.territoryId      = t.id;
        data.territoryName    = t.name;
        data.kingdomId        = t.kingdom;
        data.centerPosition   = t.center;
        data.polygonVertices  = polygons[t.id];
        data.fortificationLevel = t.fortLevel;
        data.isKingdomCapital = t.isCapital;
        data.hasMarket        = t.hasMarket;
        data.hasTemple        = t.hasTemple;
        data.culture          = t.culture;
        data.religion         = t.religion;
        data.population       = t.population;
        data.development      = t.dev;

        if (!AssetDatabase.Contains(data))
            AssetDatabase.CreateAsset(data, path);
        else
            EditorUtility.SetDirty(data);
    }

    // 4. Gerar MapAdjacencyData.asset
    GenerateAdjacencyData(territories);

    AssetDatabase.SaveAssets();
    Debug.Log("[MapGen] 40 territórios gerados com sucesso.");
}

// Algoritmo Voronoi simplificado para Unity
static Dictionary<string, Vector2[]> CalculateVoronoiPolygons(
    TerritoryDefinition[] territories,
    float width, float height)
{
    // Resolução da grid para calcular Voronoi
    int gridW = 600, gridH = 450; // metade da resolução final
    float scaleX = width  / gridW;
    float scaleY = height / gridH;

    // Para cada célula da grid, encontrar o território mais próximo
    var cellOwner = new string[gridW, gridH];
    for (int px = 0; px < gridW; px++)
    for (int py = 0; py < gridH; py++)
    {
        float wx = px * scaleX;
        float wy = py * scaleY;
        float minDist = float.MaxValue;
        string owner = "";

        foreach (var t in territories)
        {
            float dx = wx - t.center.x;
            float dy = wy - t.center.y;
            float d  = dx*dx + dy*dy; // distância quadrada
            if (d < minDist)
            {
                minDist = d;
                owner   = t.id;
            }
        }
        cellOwner[px, py] = owner;
    }

    // Extrair polígonos: para cada território, encontrar os
    // pixels da fronteira e convertê-los em vértices
    var result = new Dictionary<string, List<Vector2>>();
    foreach (var t in territories)
        result[t.id] = new List<Vector2>();

    for (int px = 1; px < gridW-1; px++)
    for (int py = 1; py < gridH-1; py++)
    {
        string owner = cellOwner[px, py];
        // É fronteira se algum vizinho tem dono diferente
        bool isBorder =
            cellOwner[px-1, py] != owner ||
            cellOwner[px+1, py] != owner ||
            cellOwner[px, py-1] != owner ||
            cellOwner[px, py+1] != owner;

        if (isBorder)
            result[owner].Add(new Vector2(
                px * scaleX, py * scaleY));
    }

    // Ordenar vértices por ângulo em relação ao centro
    // (para criar polígono convexo aproximado)
    var final = new Dictionary<string, Vector2[]>();
    foreach (var t in territories)
    {
        var pts  = result[t.id];
        var ctr  = t.center;
        var ordered = pts
            .OrderBy(p => Mathf.Atan2(p.y - ctr.y, p.x - ctr.x))
            .ToArray();

        // Simplificar: manter só 1 ponto a cada N graus
        // para não ter demasiados vértices
        var simplified = SimplifyPolygon(ordered, 8f);
        final[t.id] = simplified;
    }

    return final;
}

static Vector2[] SimplifyPolygon(Vector2[] pts, float minAngleDeg)
{
    if (pts.Length < 3) return pts;
    // Douglas-Peucker simplificado
    var result = new List<Vector2> { pts[0] };
    for (int i = 1; i < pts.Length - 1; i++)
    {
        if (Vector2.Distance(pts[i], result[result.Count-1]) > 10f)
            result.Add(pts[i]);
    }
    result.Add(pts[pts.Length - 1]);
    return result.ToArray();
}
```

### PASSO 3 — TerritoryVisual.cs (redesign completo)

Cada território é renderizado como:
1. **Mesh** do polígono Voronoi (cor do reino, com alpha variável)
2. **Linha de fronteira** entre reinos (LineRenderer, 3px, cor escura)
3. **Linha de fronteira** dentro do reino (LineRenderer, 1px, mesma cor mais escura)
4. **Ícone ♛** se isKingdomCapital (TextMeshPro)
5. **Ícone torre** escalado ao fort level (TextMeshPro ou Sprite)
6. **Nome** do território (TextMeshPro pequeno)
7. **Fog of war** overlay (cor cinzenta escura com alpha 0.6)

```csharp
public class TerritoryVisual : MonoBehaviour
{
    [Header("Componentes")]
    [SerializeField] MeshFilter   _meshFilter;
    [SerializeField] MeshRenderer _meshRenderer;
    [SerializeField] LineRenderer _borderLine;
    [SerializeField] TextMeshPro  _nameLabel;
    [SerializeField] TextMeshPro  _capitalIcon;
    [SerializeField] TextMeshPro  _fortIcon;

    private TerritoryState _state;
    private TerritoryData  _data;
    private bool _isFogOfWar = false;

    public void Init(TerritoryState state)
    {
        _state = state;
        _data  = state.data;
        BuildMesh();
        UpdateVisuals();
    }

    void BuildMesh()
    {
        var verts   = _data.polygonVertices;
        var mesh    = new Mesh();
        var vertices= new Vector3[verts.Length];
        for (int i = 0; i < verts.Length; i++)
            vertices[i] = new Vector3(verts[i].x, verts[i].y, 0);

        // Triangulação fan (funciona para polígonos convexos)
        var tris = new int[(verts.Length - 2) * 3];
        for (int i = 0; i < verts.Length - 2; i++)
        {
            tris[i*3]   = 0;
            tris[i*3+1] = i + 1;
            tris[i*3+2] = i + 2;
        }

        mesh.vertices  = vertices;
        mesh.triangles = tris;
        mesh.RecalculateNormals();
        _meshFilter.mesh = mesh;

        // Border
        _borderLine.positionCount = verts.Length + 1;
        for (int i = 0; i < verts.Length; i++)
            _borderLine.SetPosition(i,
                new Vector3(verts[i].x, verts[i].y, -0.1f));
        _borderLine.SetPosition(verts.Length,
            new Vector3(verts[0].x, verts[0].y, -0.1f));
    }

    public void UpdateVisuals()
    {
        if (_state == null || _data == null) return;

        // Cor base do reino
        Color baseColor = MapController.GetKingdomColor(_state.currentRulerId);

        // Modificadores
        if (_state.isOccupied)
        {
            // Ocupado: cor do ocupante com 70% opacidade
            baseColor = MapController.GetKingdomColor(_state.occupierId);
            baseColor.a = 0.7f;
        }

        bool isPlayerTerritory = _state.currentRulerId ==
            CharacterManager.Instance?.PlayerCharacterId;

        if (isPlayerTerritory)
            baseColor = Color.Lerp(baseColor,
                new Color(0.4f, 0.6f, 1f), 0.3f);

        _meshRenderer.material.color = _isFogOfWar
            ? new Color(0.25f, 0.22f, 0.18f, 0.8f)
            : baseColor;

        // Bordas: grossas entre reinos, finas dentro
        _borderLine.startWidth = IsKingdomBorder() ? 0.015f : 0.005f;
        _borderLine.startColor =
        _borderLine.endColor   = _isFogOfWar
            ? new Color(0.15f, 0.12f, 0.08f)
            : new Color(0, 0, 0, 0.5f);

        // Labels (ocultas em fog of war)
        _nameLabel.gameObject.SetActive(!_isFogOfWar);
        _capitalIcon.gameObject.SetActive(
            !_isFogOfWar && _data.isKingdomCapital);
        _fortIcon.gameObject.SetActive(
            !_isFogOfWar && _data.fortificationLevel > 0);

        if (!_isFogOfWar)
        {
            _nameLabel.text = _data.territoryName;
            _capitalIcon.text = "♛";
            _fortIcon.text = _data.fortificationLevel switch {
                1 => "▲",      // paliçada
                2 => "◆",      // torre
                3 => "🏰",     // castelo (usa SegoeSymbol)
                4 => "⬡",      // fortaleza
                5 => "★",      // castelo major
                _ => ""
            };
        }
    }

    public void SetFogOfWar(bool fog)
    {
        _isFogOfWar = fog;
        UpdateVisuals();
    }

    public void SetSelected(bool selected)
    {
        _borderLine.startWidth = selected ? 0.025f : (IsKingdomBorder() ? 0.015f : 0.005f);
        _borderLine.startColor =
        _borderLine.endColor   = selected
            ? Color.white
            : new Color(0, 0, 0, 0.5f);
    }

    bool IsKingdomBorder()
    {
        // Verifica se algum vizinho pertence a reino diferente
        var adj = TerritoryManager.Instance?
            .GetAdjacentTerritories(_data.territoryId);
        if (adj == null) return false;
        return adj.Any(tid => {
            var t = TerritoryManager.Instance?.GetTerritory(tid);
            return t?.data?.kingdomId != _data.kingdomId;
        });
    }
}
```

### PASSO 4 — MapAdjacencyData.cs

```csharp
// Assets/Scripts/Data/MapAdjacencyData.cs
[CreateAssetMenu(menuName = "Reconquista/Map/AdjacencyData")]
public class MapAdjacencyData : ScriptableObject
{
    [System.Serializable]
    public class AdjacencyPair
    {
        public string territoryA;
        public string territoryB;
    }

    public List<AdjacencyPair> pairs = new();

    // Runtime: construído em Start()
    private Dictionary<string, List<string>> _adjacencyMap;

    public void Build()
    {
        _adjacencyMap = new();
        foreach (var p in pairs)
        {
            if (!_adjacencyMap.ContainsKey(p.territoryA))
                _adjacencyMap[p.territoryA] = new();
            if (!_adjacencyMap.ContainsKey(p.territoryB))
                _adjacencyMap[p.territoryB] = new();
            _adjacencyMap[p.territoryA].Add(p.territoryB);
            _adjacencyMap[p.territoryB].Add(p.territoryA);
        }
    }

    public List<string> GetAdjacent(string territoryId)
    {
        if (_adjacencyMap == null) Build();
        return _adjacencyMap.TryGetValue(territoryId, out var list)
            ? list : new();
    }

    public bool AreAdjacent(string a, string b)
    {
        return GetAdjacent(a).Contains(b);
    }
}
```

O MapDataGenerator deve criar este asset com todas
as adjacências da lista acima.

### PASSO 5 — Passagem de Tropas (Military Access)

Nova mecânica crítica. Sem acordo de passagem,
não podes mover tropas por território neutro.

```csharp
// Em ArmyManager.MoveSelectedArmyTo():
public bool MoveSelectedArmyTo(string targetTerritoryId)
{
    var army = GetSelectedArmy();
    if (army == null) return false;

    // Verificar adjacência
    if (!TerritoryManager.Instance?.AreAdjacent(
        army.currentTerritoryId, targetTerritoryId) == true)
        return false;

    var target = TerritoryManager.Instance?
        .GetTerritory(targetTerritoryId);
    string playerId = CharacterManager.Instance?.PlayerCharacterId;

    // Verificar acesso:
    // 1. É território do jogador → sempre pode
    // 2. É território em guerra → sempre pode (inimigo)
    // 3. É território neutro/aliado → precisa de acordo

    bool isOwn     = target?.currentRulerId == playerId;
    bool isEnemy   = WarManager.Instance?.IsAtWar(
        playerId, target?.currentRulerId) == true;
    bool hasAccess = DiplomacyManager.Instance?
        .HasMilitaryAccess(playerId, target?.currentRulerId) == true;

    if (!isOwn && !isEnemy && !hasAccess)
    {
        // Sem acesso — mostrar mensagem explicativa
        NotificationManager.Instance?.AddNotification(
            new NotificationData {
                type     = NotificationType.Diplomacy,
                priority = NotificationPriority.Medium,
                titleKey = "war.no_access.title",
                messageKey = "war.no_access.desc",
                args     = new[] {
                    target?.data?.territoryName ?? "",
                    CharacterManager.Instance?
                        .GetCharacter(target?.currentRulerId)?
                        .name ?? ""
                },
                // Botão de acção rápida: pedir passagem
                actionKey    = "war.request_access",
                actionCallback = () => DiplomacyManager.Instance?
                    .RequestMilitaryAccess(
                        playerId, target?.currentRulerId),
            });
        return false;
    }

    // Proceder com o movimento
    army.movingToTerritoryId   = targetTerritoryId;
    army.isMoving              = true;
    // ...resto do código...
    return true;
}
```

Adicionar ao DiplomacyManager.cs:

```csharp
// Acordos de passagem activos
private HashSet<(string, string)> _militaryAccessPairs = new();

public bool HasMilitaryAccess(string requesterId, string ownerId)
{
    if (string.IsNullOrEmpty(ownerId)) return true;
    return _militaryAccessPairs.Contains((requesterId, ownerId))
        || _militaryAccessPairs.Contains((ownerId, requesterId));
}

public void GrantMilitaryAccess(string a, string b, int months)
{
    _militaryAccessPairs.Add((a, b));
    // Expirar após X meses via NarrativeContext.ScheduleFollowUp
}

public void RequestMilitaryAccess(string requesterId, string ownerId)
{
    // Abre o ecrã de diplomacia com proposta pré-preenchida
    DiplomacyPanelController.Instance?.OpenWithProposal(
        requesterId, ownerId, "military_access");
}
```

### PASSO 6 — TerritoryTooltip melhorado

Ao fazer hover/tap num território, mostrar:

```
┌──────────────────────────────────────┐
│ COIMBRA                              │
│ García de Leão  (Reino de Leão)      │
│                                      │
│ 🏰 Castelo (nível 3)                 │
│ 💰 Mercado  ✝ Mosteiro              │
│                                      │
│ Dev: 5  Pop: 1800  Renda: 12/mês    │
│ Cultura: Leonesa  Fé: Católica       │
│                                      │
│ [Declarar Guerra]  [Pedir Passagem] │
└──────────────────────────────────────┘
```

"Declarar Guerra" só visível se:
  - Território inimigo
  - Não há guerra activa com este reino
  - Jogador tem adjacência ou acesso militar

"Pedir Passagem" só visível se:
  - Território neutro/aliado
  - Não há acordo activo

---

## PASSO 7 — TerritoryManager.cs actualizado

Adicionar métodos:

```csharp
public bool AreAdjacent(string a, string b) =>
    _adjacencyData?.AreAdjacent(a, b) ?? false;

public List<string> GetAdjacentTerritories(string tid) =>
    _adjacencyData?.GetAdjacent(tid) ?? new();

public List<TerritoryState> GetTerritoriesOwnedBy(string charId) =>
    _territories.Values
        .Where(t => t.currentRulerId == charId)
        .ToList();

public string GetKingdomCapital(string kingdomId) =>
    _territories.Values
        .FirstOrDefault(t => t.data?.kingdomId == kingdomId
                          && t.data?.isKingdomCapital == true)
        ?.territoryId ?? "";

public List<TerritoryState> GetKingdomTerritories(string kingdomId) =>
    _territories.Values
        .Where(t => t.data?.kingdomId == kingdomId)
        .ToList();
```

---

## PASSO 8 — Strings i18n a adicionar

```
pt.json:
"war.no_access.title":     "Sem Acesso Militar",
"war.no_access.desc":      "Não tens permissão para mover
                            tropas por {0}. O senhor {1} não
                            te deu acesso.",
"war.request_access":      "Pedir Passagem",
"territory.capital":       "Capital",
"territory.fort.0":        "Sem muralhas",
"territory.fort.1":        "Paliçada",
"territory.fort.2":        "Torre",
"territory.fort.3":        "Castelo",
"territory.fort.4":        "Fortaleza",
"territory.fort.5":        "Castelo Major",
"territory.has_market":    "Mercado",
"territory.has_temple_christian": "Mosteiro",
"territory.has_temple_muslim":    "Mesquita",
"kingdom.asturias":        "Reino das Astúrias",
"kingdom.galiza":          "Reino da Galiza",
"kingdom.portugal":        "Condado Portucalense",
"kingdom.leon":            "Reino de Leão",
"kingdom.castela":         "Condado de Castela",
"kingdom.navarra":         "Reino de Pamplona",
"kingdom.aragon":          "Condado de Aragão",
"kingdom.barcelona":       "Condado de Barcelona",
"kingdom.cordoba":         "Emirato de Córdoba",
```

---

## TESTES DE VALIDAÇÃO — MAPA (12 testes)

```
☐ T1: Menu Reconquista > Map > Generate Territory Data
      → 40 TerritoryData assets criados em
        Assets/ScriptableObjects/Territories/

☐ T2: Play → mapa mostra 40 territórios com cores por reino
      → Portugal azul, Leão vermelho, Córdoba castanho

☐ T3: Fronteiras entre reinos são visivelmente mais grossas
      que fronteiras dentro do mesmo reino

☐ T4: Capital de cada reino tem ícone ♛

☐ T5: Territórios com fortaleza alta têm ícone de torre maior

☐ T6: Tap em Braga → tooltip com dados correctos:
      Nome, dono, fortaleza ★★★, holdings, dev, pop

☐ T7: Tooltip de Braga tem botão "Declarar Guerra"
      (é território de García de Leão se preset Vímara)

☐ T8: Exército em Braga → tentar mover para León →
      BLOQUEADO com mensagem "Sem Acesso Militar"
      + botão "Pedir Passagem"

☐ T9: Exército em Braga → mover para Guimarães →
      PERMITIDO (território do jogador)

☐ T10: Declarar guerra a Leão → mover exército para León →
       PERMITIDO (território inimigo em guerra)

☐ T11: Fog of war: territórios de Córdoba (não adjacentes)
       aparecem cinzentos sem nome nem ícones

☐ T12: Territórios adjacentes ao jogador mostram nome,
       cor, fortaleza e dono correctamente
```

---

## NOTA SOBRE ARTE FUTURA

Os polígonos actuais são gerados proceduralmente.
Quando a IA de imagem criar o mapa artístico:

1. O mapa artístico é uma textura de fundo (pergaminho)
2. Os polígonos Voronoi continuam a existir como
   camada invisível para interacção (colliders)
3. A textura artística é renderizada por baixo
4. Os polígonos ficam com alpha baixo (outline apenas)

Isto significa que a arte pode ser trocada sem
alterar nenhum código de gameplay.
