"""Phase 08 D-12: snapshot blob serializer + size-guarded deserializer.

Format: gzip(json.dumps({"geojson": dict, "region_config": dict, "edit_log": list})).
Stored as bytes in snapshots.blob column. Compressed size typically 30-100 KB per
Iberia branch (RESEARCH Assumption A3).

Security (T-08-03b-01, RESEARCH §V12): MAX_DECOMPRESSED_BYTES = 10 MB cap enforced
in BOTH serialize (pre-compress) and deserialize (post-decompress) to guard against
zip-bomb payloads even in this local-only context.
"""
from __future__ import annotations

import gzip
import json
from typing import Any, TypedDict

MAX_DECOMPRESSED_BYTES = 10 * 1024 * 1024  # 10 MB cap per RESEARCH §V12 zip-bomb mitigation


class SnapshotPayload(TypedDict):
    geojson: dict[str, Any]
    region_config: dict[str, Any]
    edit_log: list[dict[str, Any]]


class SnapshotTooLargeError(Exception):
    """RESEARCH §V12: decompressed blob exceeds MAX_DECOMPRESSED_BYTES."""


def serialize(payload: SnapshotPayload) -> bytes:
    """Encode payload to gzip-compressed JSON bytes.

    Raises SnapshotTooLargeError if raw JSON exceeds MAX_DECOMPRESSED_BYTES
    (checked pre-compress so the cap is applied consistently with deserialize).
    """
    raw = json.dumps(payload, sort_keys=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_DECOMPRESSED_BYTES:
        raise SnapshotTooLargeError(
            f"payload {len(raw)} > {MAX_DECOMPRESSED_BYTES} bytes"
        )
    return gzip.compress(raw, compresslevel=6)


def deserialize(blob: bytes) -> SnapshotPayload:
    """Decompress and decode snapshot blob.

    Raises SnapshotTooLargeError if decompressed size exceeds MAX_DECOMPRESSED_BYTES
    (defense-in-depth guard against zip bombs even for locally-stored blobs).
    """
    decompressed = gzip.decompress(blob)
    if len(decompressed) > MAX_DECOMPRESSED_BYTES:
        raise SnapshotTooLargeError(
            f"decompressed blob {len(decompressed)} > {MAX_DECOMPRESSED_BYTES} bytes"
        )
    return json.loads(decompressed.decode("utf-8"))
