---
type: seed
area: backend-voronoi
priority: high
created: 2026-04-23
status: parked
trigger: when user revisits map-generation quality OR before declaring milestone v1.0 done
---

# Seed — Voronoi output quality is too unrealistic

## User feedback (verbatim)

> "funcionou mas o territorio portugues bem com a sdivisa da fronteria me
> parece muito fora da realidade creio que a geração do mapa esta mesmo
> muito má" — 2026-04-23

User confirmed InspectorSidebar fix works, but surfaced a deeper concern:
the Voronoi-generated polygon shapes (especially in Portugal's frontier
region under `d_fronteira`) look geometrically artificial and historically
implausible.

## Technical context

Pipeline uses plain `scipy.spatial.Voronoi` over condado centroids.
Consequences:

- Frontier duchy (`d_fronteira` — Viseu, Coimbra, Aveiro, Leiria, etc.) has
  sparse centroids → oversized Voronoi cells with geometric (not
  historical) edges.
- Borders are perpendicular to centroid lines, ignoring real historical
  boundaries (Douro, Tejo, Mondego rivers; Estrela, Marão mountains).
- No weighting — small condados next to large ones split the gap 50/50.
- No historical seed polygons — only centroid + barony list; shape is
  100% inferred.

## Options (already discussed with user)

| Opt | Effort | Gain | Approach |
|-----|--------|------|----------|
| A | S | M | Add ~15 virtual centroids in sparse regions (Portugal interior, Estremadura, Aragón) to break up big cells |
| B | M | H | Weighted Voronoi / power diagram — weights from barony count or historical area |
| C | H | VH | Edge snapping to rivers/mountains from raw/municipalities.geojson |
| D | VH | Max | Ingest real historical boundary polygons (difficult to source) |

Recommended next step: **A + B combined**, ~2 days. Probably resolves 70%
of the visual artificiality.

## When to revisit

- Before declaring milestone v1.0 complete (this blocks "historically-accurate
  maps" core-value claim)
- OR when user explicitly prioritizes map quality over feature velocity
- OR during a Phase 4+ editing phase when users will be manually fixing
  these bad shapes anyway — may as well fix the generator first

## References

- `backend/medieval_forge/services/generator.py` — pipeline entry
- `backend/medieval_forge/lib/map_generator.py` — core Voronoi (D-04 black-box)
- `backend/medieval_forge/services/territory_iberia.json` — centroids source
- `backend/medieval_forge/services/mountain_river_data_iberia.json` — available
  for snapping (Option C)
