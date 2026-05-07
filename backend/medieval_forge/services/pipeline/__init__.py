"""v3 deterministic pipeline — verbatim port of inicio/map_generator.py.

Wave 0 stub. Wave 1 (Plan 02) implements run_pipeline by wiring
landmask -> border -> voronoi -> cleanup -> render -> lookup -> export.
"""
from .contracts import RegionConfig


def run_pipeline(cfg: RegionConfig) -> None:
    """Entry point per D-03. Body filled by Plan 02 (port of inicio §13)."""
    raise NotImplementedError(
        "Plan 02 wires this to landmask -> border -> voronoi -> cleanup -> render -> lookup -> export"
    )


__all__ = ["RegionConfig", "run_pipeline"]
