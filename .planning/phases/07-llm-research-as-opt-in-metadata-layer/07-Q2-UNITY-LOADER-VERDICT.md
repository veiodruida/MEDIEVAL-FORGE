---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 00
question: Q2 — does the Reconquista Unity C# loader tolerate unknown JSON keys on `territory_metadata.json` entries?
verdict_date: 2026-05-14
verdict_status: confirmed_from_source
---

# Q2 Unity Loader Strictness — Verdict

## VERDICT: Tolerant

## Evidence

**Drive note:** The plan's `read_first` enumerates `D:\Projetos_Jogo\Reconquista\Assets\Scripts\`,
but on this machine the live Reconquista Unity project lives at
`C:\Users\veio_\Documents\Unity_Projects\Reconquista\Assets\Scripts\` (verified by
`ls C:/Users/veio_/Documents/Unity_Projects/Reconquista/Assets/Scripts/` returning
`Data Debug Editor Simulation UI Utils`). The `D:\Projetos_Jogo\...` path in CLAUDE.md
and 07-CONTEXT.md is stale; the canonical source tree is the `C:\` copy referenced above.
Both presumably hold the same committed Unity codebase — the verdict cites the actual
files read.

### Primary source: `MapLoader.cs` — territory metadata deserialization

File: `C:\Users\veio_\Documents\Unity_Projects\Reconquista\Assets\Scripts\Simulation\MapLoader.cs`

Line 193–227 — `ParseTerritoryMetadata(string folder)`:

```csharp
private void ParseTerritoryMetadata(string folder)
{
    string json = File.ReadAllText(Path.Combine(folder, "territory_metadata.json"));
    var root = JsonConvert.DeserializeObject<JObject>(json);          // line 196

    // Reinos
    Kingdoms = new Dictionary<string, string>();
    if (root["kingdoms"] is JObject kingdoms)
        foreach (var kv in kingdoms)
            Kingdoms[kv.Key] = kv.Value.Value<string>();

    // Condados
    var condadoList = new List<CondadoEntry>();
    if (root["condados"] is JArray condadosArr)
    {
        foreach (var c in condadosArr)
        {
            var entry = new CondadoEntry
            {
                id          = c["id"]?.Value<string>()  ?? "",        // line 212
                name        = c["name"]?.Value<string>() ?? "",       // line 213
                duchy       = c["duchy"]?.Value<string>() ?? "",
                kingdom     = c["kingdom"]?.Value<string>() ?? "",
                lon         = c["lon"]?.Value<float>() ?? 0f,
                lat         = c["lat"]?.Value<float>() ?? 0f,
                pixel_count = c["pixel_count"]?.Value<int>() ?? 0
            };
            ...
```

### Why this is Tolerant (not Strict)

1. **`JsonConvert.DeserializeObject<JObject>`** (line 196) materializes the file into
   a Newtonsoft.Json.Linq `JObject` — a dynamic key-indexed bag. There is no concrete
   POCO mirror of the schema and therefore no `MissingMemberHandling` setting to flip.
   `JObject` ignores any key the consumer never reads — it cannot "reject" keys it
   doesn't know about, because nothing tells it what is "known".
2. **Per-key access uses `?` null-conditional + `??` fallback** (lines 212–218, 237–240
   for baronies, 200–202 for kingdoms): every read is `c["key"]?.Value<T>() ?? default`,
   which silently falls back when a key is missing. Symmetrically, when the JSON
   contains *extra* keys the loader simply never indexes into them — they don't
   participate in any code path.
3. **No `[JsonExtensionData]`, no POCO contract, no `MissingMemberHandling.Error`** —
   confirmed by Grep across `Assets/Scripts/`:
   ```
   Grep("MissingMemberHandling|JsonExtensionData", path=Assets/Scripts/) → 0 matches
   ```
4. The same defensive-read pattern is used for baronies (line 237–240) and the
   top-level `kingdoms` map (line 200–202). The entire `territory_metadata.json`
   contract is consumed JObject-style.

### Cross-reference: other JSON consumers (defense in depth)

- `lookup_barony_colors.json` (line 158): `Dictionary<string, int>` — strongly typed
  but the schema is just a string→int map; new keys would still be tolerated.
- `lookup_condado_colors.json` (line 168): same pattern.
- `terrain_types.json` (line 178): `Dictionary<string, JObject>` — same JObject
  pattern as territory_metadata; unknown subkeys ignored.
- `SaveSystem.cs`, `SaveLoadPanelController.cs`, `MapKingdomLabels.cs` use
  `JsonUtility.FromJson<T>` for save/UI overrides — Unity's `JsonUtility` is also
  tolerant by design (silently drops unknown JSON keys; it cannot represent
  polymorphic dictionaries and so could never round-trip strict schemas anyway).
  These files do NOT touch `territory_metadata.json`.

## Plan 05 instruction

`backend/medieval_forge/services/research/overlay.py` MUST set the constant exactly as:

```python
_ZIP_BOUND_FIELDS: frozenset[str] = frozenset({"name", "kingdom_owner", "historical_notes"})
```

All three overlay fields (`name`, `kingdom_owner`, `historical_notes`) are safe to merge
into the zip's `territory_metadata.json` at build time. The Unity loader will silently
ignore the two new keys; existing behavior (consuming `name`, `id`, `duchy`, `kingdom`,
`lon`, `lat`, `pixel_count`, `pixel_center`, `baronies`) is preserved bit-for-bit.

## Rationale

- D-03 (overlay sidecar field semantics) is fully realizable in the zip: no need to
  fall back to the UI-served-only path of Pattern 12 for `kingdom_owner` /
  `historical_notes`. Pattern 12 still applies for the artifact endpoint (which
  returns the unfiltered overlay), but the zip is no longer field-restricted.
- D-04 (merge at zip-build) is unconstrained — `_ZIP_BOUND_FIELDS` equals
  `_ALL_OVERLAY_FIELDS`.
- D-12 (zero-LLM parity) is unaffected: when no overlay file exists, the merge is a
  no-op (Pitfall 8 — `extra='forbid'` only applies to *pydantic* parsing of the
  overlay file itself, not to the Unity loader).
- CLAUDE.md rule 4 (`original_idx` preserved) is unchanged — merge_overlay only adds
  fields, never removes them.
- RESEARCH §Pitfall 8 reminder: keep `ConfigDict(extra='forbid')` on the *pydantic*
  overlay model so typos in the user-edited `research_overlay.json` fail loudly at
  load time — this verdict ONLY clears the Unity-side path.

## NIT 1 disposition (checker retry guidance)

The user's NIT 1 guidance said: if Claude defaults to `Unverifiable-default-Strict`
because `D:\Projetos_Jogo\Reconquista` is not mounted, the user should manually
re-run `grep` before approving. **This verdict does NOT default to the conservative
fallback** — the actual Reconquista source tree was discovered at
`C:\Users\veio_\Documents\Unity_Projects\Reconquista\Assets\Scripts\` and read directly.
`MapLoader.cs:196` was inspected first-hand. The user can spot-check by opening that
exact file at that exact line.
