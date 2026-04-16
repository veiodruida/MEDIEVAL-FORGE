"""GEN-01..04: wrapper around medieval_forge.lib.map_generator.

D-04: map_generator is treated as a vendored black box. We do NOT modify it.
D-05: synchronous pipeline runs in asyncio.to_thread.
Pitfall 6 mitigation: territory data is injected via sys.modules patching
                       before generate_maps invokes load_territory_data.

Reload mitigation: load_territory_data calls importlib.reload(mod) after
import_module. For a synthetic module (no file on disk), _find_spec returns
None and reload raises ModuleNotFoundError. We patch importlib.reload in the
map_generator module's own namespace for the duration of the pipeline call so
that reload on our synthetic module is a no-op. Real modules are unaffected.
"""
from __future__ import annotations

import asyncio
import importlib
import io
import logging
import shutil
import sys
import types
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Any

from ..lib import map_generator
from .paths import ensure_project_dirs

logger = logging.getLogger(__name__)

# Files map_generator produces (per RESEARCH Critical Integration section).
_GENERATOR_OUTPUTS: tuple[str, ...] = (
    "visual_condado.png",
    "visual_barony.png",
    "lookup_condado.png",
    "lookup_barony.png",
    "lookup_condado_colors.json",
    "lookup_barony_colors.json",
    "territory_metadata.json",
    "mountains_mask.png",
    "rivers_overlay.png",
)

# Aliases the UI uses for headline previews (GEN-02). Each alias is a copy
# of one of the generator outputs, written post-generation under a stable name.
_PREVIEW_ALIASES: dict[str, str] = {
    "terrain.png": "mountains_mask.png",
    "territories.png": "visual_condado.png",
    "borders.png": "lookup_condado.png",
}

# Ficheiros adicionais gerados por outros renderizadores (ex: render_modern)
_AUXILIARY_OUTPUTS: tuple[str, ...] = (
    "modern_map.png",
    "modern_map_colors.json",
)

GENERATED_FILE_WHITELIST: frozenset[str] = frozenset(
    list(_GENERATOR_OUTPUTS) + list(_PREVIEW_ALIASES.keys()) + list(_AUXILIARY_OUTPUTS)
)


def _inject_territory_module(name: str, data: dict[str, Any]) -> types.ModuleType:
    """Create a synthetic module with KINGDOMS/DUCHIES/CONDADOS and register in sys.modules."""
    mod = types.ModuleType(name)
    mod.KINGDOMS = data.get("kingdoms", {})
    mod.DUCHIES = data.get("duchies", {})
    mod.CONDADOS = data.get("condados", [])
    sys.modules[name] = mod
    return mod


def _cleanup_territory_module(name: str) -> None:
    sys.modules.pop(name, None)


@contextmanager
def _patch_reload_for_synthetic(synthetic_module_name: str):
    """Patch importlib.reload in map_generator's namespace to be a no-op for
    our synthetic module only.

    load_territory_data does:
        mod = importlib.import_module(name)
        importlib.reload(mod)

    For a synthetic module (no backing .py file), Python's reload calls
    _bootstrap._find_spec which returns None, raising ModuleNotFoundError.
    We intercept reload *only* for our synthetic module; real modules are
    reloaded normally.
    """
    _real_reload = importlib.reload

    def _safe_reload(module: types.ModuleType) -> types.ModuleType:
        if getattr(module, "__name__", None) == synthetic_module_name:
            return module  # no-op for our synthetic module
        return _real_reload(module)

    # Patch in map_generator's importlib reference (the module uses
    # `import importlib` at the top, so we patch via its module dict).
    import importlib as _importlib_mod
    _importlib_mod.reload = _safe_reload  # type: ignore[method-assign]
    try:
        yield
    finally:
        _importlib_mod.reload = _real_reload  # type: ignore[method-assign]


def _cleanup_territory_module(name: str) -> None:
    sys.modules.pop(name, None)


def _build_region_config(generated_dir: Path, config: dict[str, Any]) -> Any:
    """Construct a RegionConfig from caller-supplied overrides, defaulting output_dir.

    Se existir municipalities.geojson ingerido no projeto, aponta automaticamente
    municipality_pt_geojson para esse arquivo — necessário para construir a land mask.
    """
    valid_fields = set(map_generator.RegionConfig.__dataclass_fields__.keys())
    kwargs: dict[str, Any] = {"output_dir": str(generated_dir)}
    for k, v in config.items():
        if k in valid_fields and k != "output_dir":
            kwargs[k] = v

    # Apontar municipality_pt_geojson para o GeoJSON ingerido se não foi
    # fornecido explicitamente e o arquivo existir
    if "municipality_pt_geojson" not in kwargs:
        raw_geojson = generated_dir.parent / "raw" / "municipalities.geojson"
        if raw_geojson.exists():
            kwargs["municipality_pt_geojson"] = str(raw_geojson)

    return map_generator.RegionConfig(**kwargs)


def _materialise_aliases(generated_dir: Path) -> None:
    """Copy underlying generator outputs to their alias names (terrain.png etc).

    Se o arquivo fonte não existir (ex: mountains_mask.png quando não há dados de
    montanha), cria uma imagem preta como placeholder para que o alias exista.
    """
    for alias, source_name in _PREVIEW_ALIASES.items():
        source = generated_dir / source_name
        target = generated_dir / alias
        if source.exists():
            shutil.copyfile(source, target)
        elif alias == "terrain.png":
            # Gerar placeholder preto (sem terreno) para que o preview não quebre
            from PIL import Image as _PIL_Image
            import numpy as _np
            placeholder = _PIL_Image.fromarray(_np.zeros((1080, 1920), dtype=_np.uint8))
            placeholder.save(str(target))


def _validate_municipalities(raw_geojson_path: Path) -> None:
    """Verifica se o GeoJSON contém polígonos suficientes para gerar o mapa.

    Lança ValueError com mensagem amigável se os dados forem inadequados.
    """
    import json as _json
    if not raw_geojson_path.exists():
        raise ValueError(
            "Nenhum dado geográfico encontrado.\n"
            "Execute 'Ingerir via OSM' antes de gerar o mapa."
        )
    with raw_geojson_path.open(encoding="utf-8") as f:
        data = _json.load(f)
    features = data.get("features", [])
    if not features:
        raise ValueError(
            "O arquivo de municípios está vazio.\n"
            "Execute 'Ingerir via OSM' novamente."
        )
    polygon_types = {"Polygon", "MultiPolygon"}
    n_polygons = sum(
        1 for feat in features
        if feat.get("geometry", {}).get("type") in polygon_types
    )
    n_points = len(features) - n_polygons
    if n_polygons == 0:
        raise ValueError(
            f"Os dados ingeridos contêm apenas {n_points} pontos (centroides do Wikidata) "
            "e nenhum polígono de fronteira.\n"
            "O gerador precisa de polígonos para construir a máscara de terra — "
            "o resultado seria um ecrã azul (oceano).\n\n"
            "Solução: execute 'Ingerir via OSM' (botão 1b) para obter dados com polígonos reais."
        )
    logger.info(
        "municipalities validation OK: %d polygons, %d points", n_polygons, n_points
    )


def _run_pipeline_sync(
    project_id: str,
    generated_dir: Path,
    config: dict[str, Any],
) -> dict[str, str]:
    territory_data = config.get("territory_data")
    if not isinstance(territory_data, dict):
        raise ValueError(
            "config['territory_data'] must be a dict with keys {kingdoms, duchies, condados}"
        )
    # Validar dados geográficos ANTES de iniciar o pipeline
    raw_geojson = generated_dir.parent / "raw" / "municipalities.geojson"
    _validate_municipalities(raw_geojson)

    module_name = f"_mf_territory_{project_id.replace('-', '_')}"
    _inject_territory_module(module_name, territory_data)
    try:
        region_cfg = _build_region_config(generated_dir, config)
        # Redirect map_generator's progress prints to a UTF-8 StringIO buffer.
        # map_generator uses Unicode characters (→, —) in its print statements
        # that fail on Windows cp1252 console encoding when running as a
        # background thread. The captured output is logged at DEBUG level.
        _buf = io.StringIO()
        with _patch_reload_for_synthetic(module_name), redirect_stdout(_buf):
            map_generator.generate_maps(
                region_cfg,
                territory_module=module_name,
                draw_names=False,
            )
        logger.debug("map_generator output for %s:\n%s", project_id, _buf.getvalue())
        _materialise_aliases(generated_dir)
    finally:
        _cleanup_territory_module(module_name)

    manifest: dict[str, str] = {}
    for fname in GENERATED_FILE_WHITELIST:
        p = generated_dir / fname
        if p.exists():
            manifest[fname] = f"generated/{fname}"
    return manifest


async def run_generation(project_id: str, config: dict[str, Any]) -> dict[str, str]:
    """Async entry point. Schedules the synchronous pipeline in a thread.

    Returns a manifest of {filename: relative_path}. Caller is responsible for
    updating project.status (the api layer does this).
    """
    dirs = ensure_project_dirs(project_id)
    generated_dir = dirs["generated"]
    logger.info("starting generation for %s into %s", project_id, generated_dir)
    manifest = await asyncio.to_thread(
        _run_pipeline_sync, project_id, generated_dir, config
    )
    logger.info("generation done for %s: %d files", project_id, len(manifest))
    return manifest
