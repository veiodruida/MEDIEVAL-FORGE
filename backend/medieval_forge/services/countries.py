"""Lookup table: country names (PT/EN) ↔ Wikidata QID ↔ ISO 3166-1 alpha-2.

Resolução de entrada:
- QID  (ex: "Q29")        → retorna direto
- ISO  (ex: "ES")         → converte para QID
- Nome (ex: "Espanha")    → converte para QID

Para OSM: usa iso2. Para Wikidata: usa qid.
"""
from __future__ import annotations

import re

# (qid, iso2, nomes_aceitos — case-insensitive)
_TABLE: list[tuple[str, str, list[str]]] = [
    ("Q45",   "PT", ["portugal"]),
    ("Q29",   "ES", ["espanha", "spain", "españa", "espana"]),
    ("Q142",  "FR", ["franca", "france", "França", "fr"]),
    ("Q183",  "DE", ["alemanha", "germany", "deutschland"]),
    ("Q38",   "IT", ["italia", "itália", "italy"]),
    ("Q145",  "GB", ["reino unido", "united kingdom", "uk", "england", "inglaterra", "grã-bretanha", "gra-bretanha"]),
    ("Q155",  "BR", ["brasil", "brazil"]),
    ("Q30",   "US", ["estados unidos", "usa", "united states", "eua", "america"]),
    ("Q31",   "BE", ["belgica", "bélgica", "belgium", "belgique"]),
    ("Q55",   "NL", ["holanda", "paises baixos", "países baixos", "netherlands", "holland"]),
    ("Q39",   "CH", ["suica", "suíça", "switzerland", "suisse"]),
    ("Q40",   "AT", ["austria", "áustria", "österreich"]),
    ("Q36",   "PL", ["polonia", "polónia", "poland", "polska"]),
    ("Q34",   "SE", ["suecia", "suécia", "sweden", "sverige"]),
    ("Q33",   "FI", ["finlandia", "finlândia", "finland", "suomi"]),
    ("Q35",   "DK", ["dinamarca", "denmark", "danmark"]),
    ("Q20",   "NO", ["noruega", "norway", "norge"]),
    ("Q25",   "WA", ["gales", "wales", "país de gales"]),  # note: Wales não tem ISO próprio
    ("Q191",  "EE", ["estonia", "estónia", "estonia"]),
    ("Q211",  "LV", ["letonia", "letónia", "latvia"]),
    ("Q37",   "LT", ["lituania", "lituânia", "lithuania"]),
    ("Q27",   "IE", ["irlanda", "ireland", "éire"]),
    ("Q214",  "SK", ["eslovaquia", "eslováquia", "slovakia"]),
    ("Q213",  "CZ", ["republica checa", "república checa", "czech republic", "czechia"]),
    ("Q28",   "HU", ["hungria", "hungary", "magyarország"]),
    ("Q218",  "RO", ["romenia", "roménia", "romania", "românia"]),
    ("Q219",  "BG", ["bulgaria", "bulgária"]),
    ("Q35",   "DK", ["dinamarca", "denmark"]),
    ("Q41",   "GR", ["grecia", "grécia", "greece", "hellas"]),
    ("Q224",  "HR", ["croacia", "croácia", "croatia"]),
    ("Q225",  "BA", ["bosnia", "bósnia", "bosnia and herzegovina"]),
    ("Q403",  "RS", ["serbia", "sérvia", "srbija"]),
    ("Q222",  "AL", ["albania", "albânia"]),
    ("Q221",  "MK", ["macedonia", "macedónia"]),
    ("Q232",  "ME", ["montenegro"]),
    ("Q229",  "SI", ["eslovenia", "eslovénia", "slovenia"]),
    ("Q431",  "UA", ["ucrania", "ucrânia", "ukraine"]),
    ("Q159",  "RU", ["russia", "rússia"]),
    ("Q217",  "BY", ["bielorussia", "bielorrússia", "belarus"]),
    ("Q399",  "AM", ["armenia", "armênia"]),
    ("Q948",  "TN", ["tunisia", "tunísia", "tunisie"]),
    ("Q262",  "DZ", ["argelia", "argélia", "algeria"]),
    ("Q1028", "MA", ["marrocos", "morocco", "maroc"]),
    ("Q79",   "EG", ["egipto", "egito", "egypt"]),
    ("Q184",  "MR", ["mauritania", "mauritânia"]),
    ("Q117",  "GH", ["ghana"]),
    ("Q1014", "ML", ["mali"]),
    ("Q912",  "SN", ["senegal"]),
    ("Q965",  "BF", ["burkina faso"]),
    ("Q1032", "NG", ["nigeria", "nigéria"]),
    ("Q115",  "ET", ["etiopia", "etiópia", "ethiopia"]),
    ("Q1000", "GA", ["gabao", "gabão", "gabon"]),
    ("Q953",  "ZM", ["zambia", "zâmbia"]),
    ("Q258",  "ZA", ["africa do sul", "áfrica do sul", "south africa"]),
    ("Q916",  "AO", ["angola"]),
    ("Q983",  "MZ", ["mocambique", "moçambique", "mozambique"]),
    ("Q1009", "CM", ["camaroes", "camarões", "cameroon", "cameroun"]),
    ("Q733",  "PY", ["paraguai", "paraguay"]),
    ("Q750",  "BO", ["bolivia", "bolívia"]),
    ("Q298",  "CL", ["chile"]),
    ("Q414",  "AR", ["argentina"]),
    ("Q717",  "VE", ["venezuela"]),
    ("Q739",  "CO", ["colombia", "colômbia"]),
    ("Q736",  "EC", ["equador", "ecuador"]),
    ("Q419",  "PE", ["peru"]),
    ("Q800",  "CR", ["costa rica"]),
    ("Q241",  "CU", ["cuba"]),
    ("Q96",   "MX", ["mexico", "méxico"]),
    ("Q668",  "IN", ["india", "índia"]),
    ("Q148",  "CN", ["china"]),
    ("Q17",   "JP", ["japao", "japão", "japan"]),
    ("Q884",  "KR", ["coreia do sul", "south korea"]),
    ("Q423",  "KP", ["coreia do norte", "north korea"]),
    ("Q928",  "PH", ["filipinas", "philippines"]),
    ("Q252",  "ID", ["indonesia", "indonésia"]),
    ("Q819",  "LA", ["laos"]),
    ("Q869",  "TH", ["tailandia", "tailândia", "thailand"]),
    ("Q836",  "MM", ["myanmar", "birmania", "birmânia"]),
    ("Q837",  "NP", ["nepal"]),
    ("Q843",  "PK", ["paquistao", "paquistão", "pakistan"]),
    ("Q889",  "AF", ["afeganistao", "afeganistão", "afghanistan"]),
    ("Q794",  "IR", ["ira", "irã", "iran"]),
    ("Q796",  "IQ", ["iraque", "iraq"]),
    ("Q801",  "IL", ["israel"]),
    ("Q858",  "SY", ["siria", "síria", "syria"]),
    ("Q817",  "KW", ["kuwait"]),
    ("Q878",  "AE", ["emirados", "emirados árabes", "uae", "united arab emirates"]),
    ("Q783",  "SA", ["arabia saudita", "arábia saudita", "saudi arabia"]),
    ("Q403",  "RS", ["serbia", "sérbia"]),
    ("Q974",  "CD", ["congo", "republica democratica do congo", "drc"]),
    ("Q971",  "CG", ["congo brazzaville", "republic of the congo"]),
]

_QID_RE = re.compile(r"^Q\d+$")
_ISO_RE = re.compile(r"^[A-Z]{2}$")

# Índice rápido
_qid_to_iso: dict[str, str] = {}
_iso_to_qid: dict[str, str] = {}
_name_to_qid: dict[str, str] = {}

for _qid, _iso, _names in _TABLE:
    _qid_to_iso.setdefault(_qid, _iso)
    _iso_to_qid.setdefault(_iso, _qid)
    for _n in _names:
        _name_to_qid[_n.lower()] = _qid


def resolve_to_qid(value: str) -> str:
    """Converte nome, código ISO ou QID para QID Wikidata.

    Exemplos:
        "Portugal"  → "Q45"
        "PT"        → "Q45"
        "Q45"       → "Q45"
        "espanha"   → "Q29"

    Lança ValueError se não reconhecido.
    """
    v = value.strip()
    if _QID_RE.match(v):
        return v
    if _ISO_RE.match(v.upper()):
        qid = _iso_to_qid.get(v.upper())
        if qid:
            return qid
    qid = _name_to_qid.get(v.lower())
    if qid:
        return qid
    raise ValueError(
        f"País não reconhecido: {value!r}. "
        "Use o nome em português (ex: 'Portugal', 'Espanha'), "
        "código ISO (ex: 'PT', 'ES') ou QID Wikidata (ex: 'Q45')."
    )


def qid_to_iso(qid: str) -> str:
    """Converte QID Wikidata para código ISO alpha-2 (para uso no OSM).

    Lança ValueError se o QID não estiver na tabela.
    """
    iso = _qid_to_iso.get(qid)
    if iso is None:
        raise ValueError(
            f"Código ISO não encontrado para QID {qid!r}. "
            "Este país pode não estar na tabela de países suportados. "
            "Use o campo de país com um nome reconhecido."
        )
    return iso


def clip_iso_codes_for_qid(country_qid: str) -> list[str] | None:
    """Retorna lista de ISO alpha-2 para country clipping dado um QID Wikidata.

    Consulta PRESETS pelo country_qid e retorna clip_iso_codes se definido.
    Para QIDs não presentes nos presets, tenta converter o próprio QID para ISO
    e retorna lista com um único código — cobrindo países simples sem preset.

    Retorna None apenas se o QID não for reconhecido de forma alguma, caso em
    que o clipping será ignorado com aviso.
    """
    # 1. Verificar presets com clip_iso_codes explícito
    for preset in PRESETS:
        if preset.get("country_qid") == country_qid and "clip_iso_codes" in preset:
            return preset["clip_iso_codes"]

    # 2. Fallback: converter QID → ISO (países simples sem preset)
    iso = _qid_to_iso.get(country_qid)
    if iso:
        return [iso]

    return None


def list_countries() -> list[dict]:
    """Retorna lista de países disponíveis para a UI."""
    seen: set[str] = set()
    result = []
    for qid, iso, names in _TABLE:
        if qid in seen:
            continue
        seen.add(qid)
        result.append({"qid": qid, "iso": iso, "nome": names[0].title() if names else qid})
    return sorted(result, key=lambda x: x["nome"])


# ---------------------------------------------------------------------------
# Presets de regiões/países com bounding box pré-definida
# bbox: (lon_min, lat_min, lon_max, lat_max) em WGS84
# country_qid: QID Wikidata para ingestão (país principal ou região)
# label: nome de exibição em português
# ---------------------------------------------------------------------------
PRESETS: list[dict] = [
    {
        "label": "Portugal Continental",
        "country": "Portugal",
        "country_qid": "Q45",
        "bbox": {"lon_min": -9.5, "lat_min": 36.9, "lon_max": -6.2, "lat_max": 42.2},
        "period_example": (868, 1640),
        # clip_iso_codes: ISO alpha-2 list used for country-polygon clipping after bbox OSM fetch.
        # Single-country regions use their own ISO only.
        "clip_iso_codes": ["PT"],
    },
    {
        "label": "Península Ibérica (Portugal + Espanha)",
        "country": "Espanha+Portugal",
        "country_qid": "Q29,Q45",
        "bbox": {"lon_min": -13.2, "lat_min": 35.4, "lon_max": 8.2, "lat_max": 44.6},
        "period_example": (711, 1492),
        # Iberia spans two sovereign countries — clip to union of ES + PT polygons so that
        # French départements (Dordogne, Landes, etc.) are excluded from the ingest result.
        "clip_iso_codes": ["ES", "PT"],
    },
    {
        "label": "França",
        "country": "França",
        "country_qid": "Q142",
        "bbox": {"lon_min": -5.1, "lat_min": 41.3, "lon_max": 9.6, "lat_max": 51.1},
        "period_example": (843, 1453),
    },
    {
        "label": "Ilhas Britânicas (Inglaterra, Escócia, Irlanda)",
        "country": "Q145",
        "country_qid": "Q145,Q27",
        "bbox": {"lon_min": -10.5, "lat_min": 49.8, "lon_max": 2.0, "lat_max": 61.0},
        "period_example": (1066, 1485),
        "clip_iso_codes": ["GB", "IE"],
    },
    {
        "label": "Itália",
        "country": "Itália",
        "country_qid": "Q38",
        "bbox": {"lon_min": 6.6, "lat_min": 36.6, "lon_max": 18.5, "lat_max": 47.1},
        "period_example": (476, 1454),
    },
    {
        "label": "Alemanha (Sacro Império)",
        "country": "Alemanha",
        "country_qid": "Q183",
        "bbox": {"lon_min": 5.9, "lat_min": 47.3, "lon_max": 15.0, "lat_max": 55.1},
        "period_example": (962, 1356),
    },
    {
        "label": "Escandinávia (Dinamarca, Noruega, Suécia)",
        "country": "Q34",
        "country_qid": "Q35,Q20,Q34",
        "bbox": {"lon_min": 4.5, "lat_min": 54.5, "lon_max": 31.0, "lat_max": 71.2},
        "period_example": (793, 1397),
        "clip_iso_codes": ["DK", "NO", "SE"],
    },
    {
        "label": "Balcãs (Sérvia, Croácia, Bósnia, etc.)",
        "country": "Q403",
        "country_qid": "Q403,Q224,Q225",
        "bbox": {"lon_min": 13.4, "lat_min": 38.0, "lon_max": 28.0, "lat_max": 47.0},
        "period_example": (1000, 1500),
        "clip_iso_codes": ["RS", "HR", "BA"],
    },
    {
        "label": "Europa Central (Polónia, Hungria, Rep. Checa)",
        "country": "Q36",
        "country_qid": "Q36,Q28,Q213",
        "bbox": {"lon_min": 12.0, "lat_min": 45.8, "lon_max": 24.2, "lat_max": 54.9},
        "period_example": (960, 1410),
        "clip_iso_codes": ["PL", "HU", "CZ"],
    },
    {
        "label": "Médio Oriente (Anatólia, Levante, Mesopotâmia)",
        "country": "Q43",
        "country_qid": "Q43",
        "bbox": {"lon_min": 25.6, "lat_min": 29.0, "lon_max": 48.6, "lat_max": 42.4},
        "period_example": (1071, 1453),
    },
    {
        "label": "Norte de África (Marrocos, Argélia, Tunísia)",
        "country": "Q1028",
        "country_qid": "Q1028,Q262,Q948",
        "bbox": {"lon_min": -6.0, "lat_min": 30.0, "lon_max": 13.0, "lat_max": 37.5},
        "period_example": (647, 1492),
        "clip_iso_codes": ["MA", "DZ", "TN"],
    },
    {
        "label": "Brasil",
        "country": "Brasil",
        "country_qid": "Q155",
        "bbox": {"lon_min": -74.0, "lat_min": -33.8, "lon_max": -34.8, "lat_max": 5.3},
        "period_example": (1500, 1822),
    },
]
