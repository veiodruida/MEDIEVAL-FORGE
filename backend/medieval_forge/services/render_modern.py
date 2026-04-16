"""Renderização direta do mapa moderno a partir dos polígonos ingeridos.

Pinta cada município/província com uma cor única para validar visualmente
que os dados geográficos estão corretos, ANTES da complexidade Voronoi medieval.

Projeção equiretangular simples (top-down, norte para cima) com correção
proporcional de longitude baseada no cosseno da latitude central.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .paths import ensure_project_dirs

logger = logging.getLogger(__name__)


def _color_for(key: str) -> tuple[int, int, int]:
    """Cor pastel determinística a partir de um identificador."""
    h = hashlib.md5(key.encode("utf-8")).hexdigest()
    # Canais 120-220 → tons suaves, evita quase-preto e quase-branco
    r = 120 + int(h[0:2], 16) % 100
    g = 120 + int(h[2:4], 16) % 100
    b = 120 + int(h[4:6], 16) % 100
    return r, g, b


def _geo_to_pixel(
    lon: float, lat: float,
    lon_min: float, lat_min: float, lon_max: float, lat_max: float,
    width: int, height: int,
    lon_scale: float,
) -> tuple[int, int]:
    """Projeção equiretangular com correção de longitude.

    A longitude é escalada pelo cosseno da latitude central para manter
    proporções corretas (caso contrário o mapa fica esticado na horizontal
    em latitudes altas).
    """
    # Normalizar posição dentro do bbox
    rel_x = (lon - lon_min) / (lon_max - lon_min)
    rel_y = (lat_max - lat) / (lat_max - lat_min)  # Y invertido: norte = topo
    x = int(rel_x * width)
    y = int(rel_y * height)
    return x, y


def render_modern_map(
    project_id: str,
    bbox: tuple[float, float, float, float],  # lon_min, lat_min, lon_max, lat_max
    width: int = 1920,
    height: int = 1080,
) -> dict[str, Path]:
    """Renderiza o mapa moderno e escreve 2 ficheiros em generated/.

    Args:
        project_id: UUID do projeto.
        bbox: (lon_min, lat_min, lon_max, lat_max) em WGS84.
        width: largura do mapa em pixels.
        height: altura.

    Returns:
        dict {'map': path_png, 'colors': path_json}.

    Raises:
        ValueError: se não houver polígonos para renderizar.
    """
    lon_min, lat_min, lon_max, lat_max = bbox
    center_lat = (lat_min + lat_max) / 2
    lon_scale = math.cos(math.radians(center_lat))

    # Ajustar height para manter proporção correta com a correção de longitude
    # (o map_generator original usa upscale=2; aqui mantemos 1x para simplicidade)
    aspect_ratio = ((lon_max - lon_min) * lon_scale) / (lat_max - lat_min)
    height_adj = int(width / aspect_ratio) if aspect_ratio > 0 else height
    height_adj = min(max(height_adj, 400), 2000)

    dirs = ensure_project_dirs(project_id)
    raw_path = dirs["raw"] / "municipalities.geojson"
    if not raw_path.exists():
        raise ValueError(
            "Nenhum ficheiro municipalities.geojson encontrado.\n"
            "Execute 'Ingerir via OSM' primeiro."
        )

    with raw_path.open(encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    polygon_types = {"Polygon", "MultiPolygon"}
    polygon_features = [
        ft for ft in features
        if ft.get("geometry", {}).get("type") in polygon_types
    ]

    if not polygon_features:
        raise ValueError(
            f"Ingestão contém {len(features)} features mas nenhum polígono.\n"
            "Este tipo de render precisa de polígonos reais (OSM).\n"
            "Execute 'Ingerir via OSM' (botão 1b)."
        )

    # Imagem com fundo oceano
    img = Image.new("RGB", (width, height_adj), (60, 110, 160))  # azul-oceano
    draw = ImageDraw.Draw(img)

    color_map: dict[str, list[int]] = {}
    rendered = 0
    skipped = 0

    for feat in polygon_features:
        props = feat.get("properties", {})
        name = props.get("name", "") or f"osm_{props.get('osm_id', '?')}"
        color = _color_for(name)

        geom = feat["geometry"]
        coords = geom["coordinates"]

        # Extrair rings: Polygon tem [outer, holes...]; MultiPolygon tem [[outer, holes], ...]
        rings: list[list[list[float]]] = []
        if geom["type"] == "Polygon":
            rings = [coords[0]]  # só ring externo, ignoramos holes para simplicidade
        elif geom["type"] == "MultiPolygon":
            rings = [p[0] for p in coords]

        drew_any = False
        for ring in rings:
            pts = [
                _geo_to_pixel(float(lo), float(la), lon_min, lat_min, lon_max, lat_max,
                              width, height_adj, lon_scale)
                for lo, la in ring
                if lon_min - 1 <= float(lo) <= lon_max + 1
                and lat_min - 1 <= float(la) <= lat_max + 1
            ]
            if len(pts) >= 3:
                # Linha de fronteira preta fina + preenchimento colorido
                draw.polygon(pts, fill=color, outline=(40, 30, 20))
                drew_any = True

        if drew_any:
            rendered += 1
            color_map[name] = list(color)
        else:
            skipped += 1

    logger.info(
        "render_modern: renderizadas %d províncias, %d ignoradas (fora do bbox)",
        rendered, skipped,
    )

    # Adicionar escala/legenda no canto
    try:
        legend_font = ImageFont.load_default()
        legend_text = (
            f"{rendered} provincias renderizadas  |  "
            f"bbox: [{lon_min:.1f}, {lat_min:.1f}] - [{lon_max:.1f}, {lat_max:.1f}]"
        )
        # Fundo semi-transparente da legenda
        draw.rectangle([(5, 5), (5 + 8 * len(legend_text), 22)], fill=(0, 0, 0, 180))
        draw.text((10, 8), legend_text, font=legend_font, fill=(255, 255, 255))
    except Exception:
        pass  # legenda é cosmética, não bloquear se fontes falharem

    out_dir = dirs["generated"]
    out_dir.mkdir(parents=True, exist_ok=True)
    map_path = out_dir / "modern_map.png"
    colors_path = out_dir / "modern_map_colors.json"

    img.save(map_path)
    colors_path.write_text(
        json.dumps({
            "provinces": color_map,
            "rendered_count": rendered,
            "skipped_count": skipped,
            "bbox": {"lon_min": lon_min, "lat_min": lat_min, "lon_max": lon_max, "lat_max": lat_max},
            "dimensions": {"width": width, "height": height_adj},
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {"map": map_path, "colors": colors_path}
