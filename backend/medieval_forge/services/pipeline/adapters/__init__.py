"""Phase 02 ingestion adapters — wrap v1 ingest_* services into ProjectDataset.

D-05: wrap, don't rewrite. D-13: terrain is stub passthrough. D-15: no Wikidata wrapper.
"""
from .osm import build_dataset_from_osm
from .terrain import build_terrain

__all__ = ["build_dataset_from_osm", "build_terrain"]
