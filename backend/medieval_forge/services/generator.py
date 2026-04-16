"""GEN-01..04: wrapper around medieval_forge.lib.map_generator.

D-04: map_generator is treated as a vendored black box. We do NOT modify it.
D-05: synchronous pipeline runs in asyncio.to_thread.
Pitfall 6 mitigation: territory data is injected via sys.modules patching
                       before generate_maps invokes load_territory_data.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import sys
import types
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

GENERATED_FILE_WHITELIST: frozenset[str] = frozenset(
    list(_GENERATOR_OUTPUTS) + list(_PREVIEW_ALIASES.keys())
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


def _build_region_config(generated_dir: Path, config: dict[str, Any]) -> Any:
    """Construct a RegionConfig from caller-supplied overrides, defaulting output_dir."""
    valid_fields = set(map_generator.RegionConfig.__dataclass_fields__.keys())
    kwargs: dict[str, Any] = {"output_dir": str(generated_dir)}
    for k, v in config.items():
        if k in valid_fields and k != "output_dir":
            kwargs[k] = v
    return map_generator.RegionConfig(**kwargs)


def _materialise_aliases(generated_dir: Path) -> None:
    """Copy underlying generator outputs to their alias names (terrain.png etc)."""
    for alias, source_name in _PREVIEW_ALIASES.items():
        source = generated_dir / source_name
        target = generated_dir / alias
        if source.exists():
            shutil.copyfile(source, target)


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
    module_name = f"_mf_territory_{project_id.replace('-', '_')}"
    _inject_territory_module(module_name, territory_data)
    try:
        region_cfg = _build_region_config(generated_dir, config)
        map_generator.generate_maps(
            region_cfg,
            territory_module=module_name,
            draw_names=False,
        )
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
