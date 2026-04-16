# RECONQUISTA — MAPA V2 FASE 2: POLIGONOS GEOJSON REAIS
# Le o CLAUDE_CODE_BRIEFING_v27.md e o SESSION_NOTES_2026_04_12_H.md antes.

---

## OBJECTIVO

Substituir os poligonos Voronoi actuais por poligonos geograficos REAIS
extraidos de GeoJSON publico. O resultado final deve parecer um mapa
real da Peninsula Iberica com provincias visiveis.

---

## ESTADO ACTUAL

O MapDataGenerator.cs gera 44 territorios com:
- Centros em coordenadas reais (lat/lon convertidas)
- Poligonos Voronoi clippados por Sutherland-Hodgman contra outline da Peninsula
- PROBLEMA: Voronoi nao respeita fronteiras naturais (rios, montanhas)
- PROBLEMA: S-H tem artefactos nas zonas concavas (Pireneus)
- O mapa parece-se com a Peninsula mas nao e fiel

---

## FONTES DE DADOS (GRATUITAS, OPEN SOURCE)

### Provincias de Espanha
- GitHub: https://github.com/simp37/GeoJson_SPAIN/blob/master/Spain/spain-provinces.geojson
- Gist simplificado: https://gist.github.com/josemamira/3af52a4698d42b3f676fbc23f807a605
- es-atlas (TopoJSON): https://github.com/martgnz/es-atlas

### Distritos de Portugal
- SimpleMaps: https://simplemaps.com/gis/country/pt (GeoJSON gratuito)
- IGISMAP: https://www.igismap.com/download-portugal-administrative-boundary-gis-data-regions-districts-and-more/

### Coastline
- Natural Earth: https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-coastline/
- GitHub: https://github.com/martynafford/natural-earth-geojson

---

## MAPEAMENTO: PROVINCIAS MODERNAS → TERRITORIOS MEDIEVAIS

### Portugal (18 distritos → 8 territorios)
```
portucale_braga     = Braga
portucale_guimaraes = Braga (zona sul) — pode fundir com braga
portucale_porto     = Porto
portucale_lamego    = Viseu (zona norte/este)
portucale_chaves    = Vila Real
portucale_braganca  = Braganca
fronteira_coimbra   = Coimbra
fronteira_viseu     = Viseu (zona sul) + Guarda
```

### Galiza (4 provincias → 3 territorios)
```
galiza_compostela   = A Coruna + Pontevedra (metade norte)
galiza_lugo         = Lugo
galiza_tui          = Pontevedra (metade sul)
```

### Asturias / Cantabria / Pais Basco (provincias → 6 territorios)
```
asturias_oviedo     = Asturias (metade oeste)
asturias_gijon      = Asturias (metade leste/costa)
asturias_cangas     = Asturias (extremo leste)
cantabria           = Cantabria
alava               = Alava
vasconia            = Guipuzcoa + Vizcaya
```

### Leon (5 provincias → 5 territorios)
```
leon_capital        = Leon
leon_astorga        = Leon (zona oeste) — pode fundir
leon_palencia       = Palencia
leon_zamora         = Zamora
leon_salamanca      = Salamanca
```

### Castela (3 provincias → 3 territorios)
```
castela_burgos      = Burgos
castela_soria       = Soria
castela_logrono     = La Rioja
```

### Navarra (1 provincia → 2 territorios)
```
navarra_pamplona    = Navarra (norte)
navarra_tudela      = Navarra (sul) — zona do Ebro
```

### Aragao / Catalunha (4 provincias → 4 territorios)
```
aragon_jaca         = Huesca
aragon_zaragoza     = Zaragoza
aragon_barcelona    = Barcelona + Girona
aragon_lleida       = Lleida
```

### Al-Andalus Norte (provincias → 7 territorios)
```
andalus_toledo      = Toledo
andalus_madrid      = Madrid
andalus_guadalajara = Guadalajara
andalus_talavera    = Toledo (zona oeste) — dividir poligono
andalus_caceres     = Caceres
andalus_merida      = Badajoz (zona este/Merida)
andalus_badajoz     = Badajoz (zona oeste)
```

### Cordoba / Sul (provincias → 6 territorios)
```
cordoba_capital     = Cordoba
cordoba_sevilla     = Sevilla + Huelva
cordoba_jaen        = Jaen
cordoba_granada     = Granada
cordoba_malaga      = Malaga
cordoba_almeria     = Almeria + Murcia
```

---

## FORMULA DE CONVERSAO

```
x_unity = (longitude - (-9.5)) * 92.3
y_unity = (latitude  - 35.5)  * 105.9
```

---

## ALGORITMO DE IMPLEMENTACAO

```
1. Carregar GeoJSON de Espanha e Portugal
2. Para cada territorio do jogo:
   a. Identificar a(s) provincia(s) moderna(s) correspondente(s)
   b. Extrair os poligonos (podem ser MultiPolygon — usar o maior)
   c. Se territorio = fusao de provincias: fazer union dos poligonos
   d. Se territorio = subdivisao de provincia: cortar com linha divisoria
   e. Simplificar para ~30-50 vertices (Douglas-Peucker)
   f. Converter lat/lon → Unity
3. Guardar como polygonPoints no TerritoryMapData
4. Manter adjacencias (MapAdjacencyData) — revalidar contra novos poligonos
5. Testar: todos os territorios devem ser clicaveis e visiveis
```

---

## ABORDAGEM PRATICA

O mais eficiente e criar um script Python ou C# Editor que:
1. Le o GeoJSON
2. Faz o mapeamento e simplificacao
3. Escreve os dados directamente nos TerritoryMapData assets

OU, mais simples:
1. Hardcodar os poligonos simplificados directamente no MapDataGenerator.cs
   (como ja faz com os centros dos territorios)
2. Substituir a chamada ao Voronoi por lookup directo

---

## REFERENCIA CK2

CK2 divide a Iberia em ~60 provincias:
- Coruña, Santiago, Porto, Coimbra, Bragança, Guarda, Lisboa...
- León, Zamora, Salamanca, Astorga, Valladolid, Burgos, Soria...
- Toledo, Calatayud, Zaragoza, Barcelona, Urgell...
- Córdoba, Sevilla, Granada, Almería, Murcia...

Os nossos 44 sao ligeiramente menos granulares (bom para mobile).
Para aumentar: basta adicionar mais entradas ao MapDataGenerator.

---

## NOTAS IMPORTANTES

- NAO apagar o MapDataGenerator actual — so substituir a funcao de geracao de poligonos
- Manter o sistema de adjacencias (MapAdjacencyData) intacto
- Manter o clipping S-H como fallback se o GeoJSON falhar para algum territorio
- O oceano (background azul) ainda nao existe — adicionar como sprite ou quad
- As coordenadas dos centros ja estao correctas — so mudar os polygonPoints
