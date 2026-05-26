---
phase: 08
plan: 03b
type: execute
wave: 2
depends_on: [08-03a]
autonomous: true
requirements: [PERSIST-01, PERSIST-02, BRANCH-02, BRANCH-03, TELEM-01]
files_modified:
  - backend/medieval_forge/models.py
  - backend/medieval_forge/services/branches/snapshot.py
  - backend/medieval_forge/services/branches/service.py
  - backend/medieval_forge/api/v3/branches.py
  - backend/tests/integration/test_snapshot_persistence.py

must_haves:
  truths:
    - "Snapshot and EditEvent tables created via Base.metadata.create_all"
    - "POST /branches/{bid}/snapshots creates snapshot with trigger in {auto, manual, pre_slider_change} and returns 201 {snapshot_id, seq}"
    - "GET /branches/{bid}/snapshots returns reverse-chronological list per branch"
    - "Snapshot blob = gzip(json({geojson, region_config, edit_log})); size cap 10MB on decompress (Pitfall 9 of RESEARCH security)"
    - "POST /branches/{bid}/snapshots/{sid}/restore loads blob → returns geojson + config + log (frontend rehydrates)"
    - "POST /branches/{bid}/edit-events appends edit op with payload_json; auto-snapshots every 25 edits per D-37"
    - "Each Branch.edits_since_snapshot counter increments on edit-event log and resets to 0 on snapshot"
  artifacts:
    - path: "backend/medieval_forge/models.py"
      provides: "Snapshot + EditEvent ORM models"
      contains: "class Snapshot|class EditEvent"
    - path: "backend/medieval_forge/services/branches/snapshot.py"
      provides: "serialize/deserialize snapshot blob (gzip + json) + size guard"
      min_lines: 50
  key_links:
    - from: "POST /edit-events"
      to: "auto-snapshot trigger every 25 ops"
      via: "service layer increments edits_since_snapshot; on >=25 calls create_snapshot(trigger='auto') and resets counter"
      pattern: "edits_since_snapshot"
---

<objective>
Wave 2 backend foundation #4. Add `snapshots` + `edit_events` tables, the gzip blob serializer, snapshot CRUD endpoints, and the edit-event endpoint that triggers auto-snapshots every 25 ops per D-37.

Per RESEARCH §Pitfall 9 (slider-conflict race): the snapshot endpoint MUST return 201 + `{snapshot_id, seq}` before the frontend opens any "restore N" modal. Errors propagate as 5xx with no implicit "snapshot saved" claim.

Purpose: complete the persistence layer for plans 08-04 (frontend store consumes endpoints), 08-09 (snapshot timeline UI), and 08-10 (export manifest extension).
Output: 2 ORM models + 1 serializer module + 4 endpoints + 1 integration test file filled.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/phases/08-.../08-CONTEXT.md
@.planning/phases/08-.../08-RESEARCH.md §"Pattern 3" + §Pitfall 9 + §V12 (file size limits)
@backend/medieval_forge/models.py
@backend/medieval_forge/api/v3/branches.py
@backend/medieval_forge/services/branches/service.py

<interfaces>
From RESEARCH Pattern 3 (verbatim):
```python
class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)  # auto|manual|pre_slider_change
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("branch_id", "seq", name="uq_snapshot_branch_seq"),)

class EditEvent(Base):
    __tablename__ = "edit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    op_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
```

Snapshot blob format (RESEARCH §Standard Stack + Pattern 3):
  raw = json.dumps({"geojson": ..., "region_config": ..., "edit_log": [...]}).encode()
  compressed = gzip.compress(raw)
  # store compressed in blob column; decompress on restore with 10MB safety limit.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Snapshot + EditEvent ORM + snapshot.py serializer</name>
  <files>backend/medieval_forge/models.py, backend/medieval_forge/services/branches/snapshot.py</files>
  <read_first>
    - backend/medieval_forge/models.py (current Mapped patterns + imports + Branch class from 08-03a)
    - .planning/phases/08-.../08-RESEARCH.md §"Pattern 3" + §Security V8/V12
    - backend/medieval_forge/services/branches/service.py (from 08-03a)
  </read_first>
  <behavior>
    - Test: Snapshot round-trips via AsyncSession; UniqueConstraint(branch_id, seq) blocks duplicate
    - Test: EditEvent round-trips with JSON payload preserved
    - Test: snapshot.serialize({"geojson":..., "region_config":..., "edit_log":[...]}) returns bytes; gzip header present
    - Test: snapshot.deserialize(serialize(x)) == x (round-trip identity)
    - Test: snapshot.deserialize on >10MB decompressed payload raises SnapshotTooLargeError
  </behavior>
  <action>
**Step 1 — `models.py`:** Append Snapshot + EditEvent classes verbatim from interfaces block above. Add imports: `LargeBinary, JSON` from sqlalchemy.

**Step 2 — `services/branches/snapshot.py`:** New module:

```python
"""Phase 08 D-12: snapshot blob serializer + size-guarded deserializer.

Format: gzip(json.dumps({"geojson": dict, "region_config": dict, "edit_log": list})).
Stored as bytes in snapshots.blob column. Compressed size typically 30-100 KB per
Iberia branch (RESEARCH Assumption A3).
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
    raw = json.dumps(payload, sort_keys=False, separators=(",", ":")).encode("utf-8")
    return gzip.compress(raw, compresslevel=6)


def deserialize(blob: bytes) -> SnapshotPayload:
    # Guard against zip bombs even in local-only context (defense in depth).
    decompressed = gzip.decompress(blob)
    if len(decompressed) > MAX_DECOMPRESSED_BYTES:
        raise SnapshotTooLargeError(
            f"decompressed blob {len(decompressed)} > {MAX_DECOMPRESSED_BYTES} bytes"
        )
    return json.loads(decompressed.decode("utf-8"))
```

Unit tests for serializer can live in test_snapshot_persistence.py from Task 2.
  </action>
  <verify>
    <automated>cd backend && python -c "from medieval_forge.models import Snapshot, EditEvent; from medieval_forge.services.branches.snapshot import serialize, deserialize, SnapshotTooLargeError, MAX_DECOMPRESSED_BYTES; p={'geojson':{'a':1},'region_config':{'b':2},'edit_log':[{'op':'move'}]}; assert deserialize(serialize(p))==p; print('ok',MAX_DECOMPRESSED_BYTES)"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "class Snapshot\|class EditEvent" backend/medieval_forge/models.py` returns 2
    - serializer round-trip verified
    - MAX_DECOMPRESSED_BYTES = 10MB constant present
  </acceptance_criteria>
  <done>2 ORM models + serializer module committed.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Snapshot + edit-event endpoints + auto-snapshot trigger logic + integration tests</name>
  <files>backend/medieval_forge/services/branches/service.py, backend/medieval_forge/api/v3/branches.py, backend/tests/integration/test_snapshot_persistence.py</files>
  <read_first>
    - backend/medieval_forge/services/branches/service.py (from 08-03a)
    - backend/medieval_forge/api/v3/branches.py (from 08-03a)
    - backend/medieval_forge/services/branches/snapshot.py (from Task 1)
    - backend/tests/integration/test_snapshot_persistence.py (Wave 0 stub)
  </read_first>
  <behavior>
    - Test: POST /snapshots {trigger:"manual", payload:{...}} → 201 + {snapshot_id, seq:1}
    - Test: second POST → seq:2 (monotonic per branch)
    - Test: GET /snapshots → list reverse-chronological by seq
    - Test: POST /snapshots/{sid}/restore → 200 + decoded SnapshotPayload
    - Test: POST 11 MB payload → 413 (Pitfall 9 + V12)
    - Test: POST /edit-events {op_type:"move",payload:{...}} → 201; Branch.edits_since_snapshot increments
    - Test: 25th edit-event POST triggers auto-snapshot with trigger="auto"; edits_since_snapshot resets to 0
    - Test: serializer round-trip (geojson + config + log preserved exactly)
  </behavior>
  <action>
**Step 1 — `services/branches/service.py`:** Append snapshot + edit-event helpers:

```python
from .snapshot import serialize, deserialize, SnapshotPayload, SnapshotTooLargeError
from ..models import Snapshot, EditEvent

AUTO_SNAPSHOT_EVERY_N_EDITS = 25  # D-37


async def create_snapshot(db: AsyncSession, branch_id: str,
                          payload: SnapshotPayload, trigger: str) -> Snapshot:
    """D-12: gzip+json blob stored in snapshots table. Trigger ∈ {auto, manual, pre_slider_change}."""
    if trigger not in {"auto", "manual", "pre_slider_change"}:
        raise ValueError(f"invalid trigger: {trigger}")
    next_seq = (await db.execute(
        select(Snapshot.seq).where(Snapshot.branch_id == branch_id)
                            .order_by(Snapshot.seq.desc()).limit(1)
    )).scalar_one_or_none() or 0
    next_seq += 1
    blob = serialize(payload)
    snap = Snapshot(branch_id=branch_id, seq=next_seq, blob=blob, trigger=trigger)
    db.add(snap)
    # Reset edits-since-snapshot counter on branch (D-37)
    branch = (await db.execute(select(Branch).where(Branch.id == branch_id))).scalar_one()
    branch.edits_since_snapshot = 0
    await db.commit()
    await db.refresh(snap)
    return snap


async def list_snapshots(db: AsyncSession, branch_id: str) -> list[Snapshot]:
    return list((await db.execute(
        select(Snapshot).where(Snapshot.branch_id == branch_id)
                        .order_by(Snapshot.seq.desc())
    )).scalars())


async def restore_snapshot(db: AsyncSession, snapshot_id: str) -> SnapshotPayload:
    snap = (await db.execute(select(Snapshot).where(Snapshot.id == snapshot_id))).scalar_one()
    return deserialize(snap.blob)


async def append_edit_event(db: AsyncSession, branch_id: str,
                            op_type: str, payload: dict) -> tuple[EditEvent, Snapshot | None]:
    """D-35 + D-37: log event, increment counter, auto-snapshot every Nth call.

    Returns (event, auto_snapshot_or_None). Caller is responsible for providing
    the SnapshotPayload for the auto-snapshot via the request body (frontend
    sends edit_log + current geojson state) — see endpoint wiring.
    """
    if len(op_type) > 32:
        raise ValueError("op_type too long")
    evt = EditEvent(branch_id=branch_id, op_type=op_type, payload=payload)
    db.add(evt)
    branch = (await db.execute(select(Branch).where(Branch.id == branch_id))).scalar_one()
    branch.edits_since_snapshot += 1
    await db.commit()
    await db.refresh(evt)
    return evt, None  # auto-snapshot trigger handled at endpoint layer (needs full state)
```

Note: auto-snapshot creation needs the current snapshot payload, which the frontend holds; we cannot construct it server-side from the edit log alone. So the endpoint pattern is: frontend includes `snapshot_payload_if_auto_snapshot_due` in the body; backend creates snapshot only after counter reaches threshold.

**Step 2 — `api/v3/branches.py`:** Extend with new endpoints:

```python
from pydantic import BaseModel
from typing import Any

class SnapshotCreateBody(BaseModel):
    trigger: str = Field(..., pattern=r"^(auto|manual|pre_slider_change)$")
    payload: dict[str, Any]  # SnapshotPayload shape; size guard at deserialize

class EditEventBody(BaseModel):
    op_type: str = Field(..., min_length=1, max_length=32)
    payload: dict[str, Any]
    snapshot_payload_if_due: dict[str, Any] | None = None  # frontend supplies if it knows counter is at 24


@router.post("/{branch_id}/snapshots", status_code=201)
async def create_snapshot_endpoint(project_id: str, branch_id: str,
                                   body: SnapshotCreateBody,
                                   db: AsyncSession = Depends(get_db)):
    _guard_pid(project_id)
    try:
        snap = await create_snapshot(db, branch_id, body.payload, body.trigger)
    except SnapshotTooLargeError as exc:
        raise HTTPException(413, str(exc))
    return {"snapshot_id": snap.id, "seq": snap.seq,
            "created_at": snap.created_at.isoformat()}


@router.get("/{branch_id}/snapshots")
async def list_snapshots_endpoint(project_id: str, branch_id: str,
                                  db: AsyncSession = Depends(get_db)):
    _guard_pid(project_id)
    snaps = await list_snapshots(db, branch_id)
    return [{"id": s.id, "seq": s.seq, "trigger": s.trigger,
             "created_at": s.created_at.isoformat(),
             "size_bytes": len(s.blob)} for s in snaps]


@router.post("/{branch_id}/snapshots/{snapshot_id}/restore")
async def restore_snapshot_endpoint(project_id: str, branch_id: str, snapshot_id: str,
                                    db: AsyncSession = Depends(get_db)):
    _guard_pid(project_id)
    payload = await restore_snapshot(db, snapshot_id)
    return payload  # frontend rehydrates


@router.post("/{branch_id}/edit-events", status_code=201)
async def edit_event_endpoint(project_id: str, branch_id: str, body: EditEventBody,
                              db: AsyncSession = Depends(get_db)):
    _guard_pid(project_id)
    evt, _ = await append_edit_event(db, branch_id, body.op_type, body.payload)
    # D-37: check if we crossed the 25-edit threshold
    branch = (await db.execute(select(Branch).where(Branch.id == branch_id))).scalar_one()
    auto_snap = None
    if branch.edits_since_snapshot >= AUTO_SNAPSHOT_EVERY_N_EDITS and body.snapshot_payload_if_due:
        try:
            snap = await create_snapshot(db, branch_id, body.snapshot_payload_if_due, "auto")
            auto_snap = {"snapshot_id": snap.id, "seq": snap.seq}
        except SnapshotTooLargeError:
            # Don't fail the edit event — frontend retries snapshot separately
            auto_snap = {"error": "SNAPSHOT_TOO_LARGE"}
    return {"event_id": evt.id, "auto_snapshot": auto_snap,
            "edits_since_snapshot": branch.edits_since_snapshot}
```

**Step 3 — `test_snapshot_persistence.py`:** Remove skip marker; implement 8 integration tests above with explicit numeric fixtures.
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/integration/test_snapshot_persistence.py -v -x</automated>
  </verify>
  <acceptance_criteria>
    - All 8 integration tests pass
    - `grep -c "AUTO_SNAPSHOT_EVERY_N_EDITS = 25" backend/medieval_forge/services/branches/service.py` returns 1
    - `grep -c "MAX_DECOMPRESSED_BYTES" backend/medieval_forge/services/branches/snapshot.py` returns 2+
    - 11MB payload returns 413, not 500
  </acceptance_criteria>
  <done>Snapshot + edit-event API live; 25-edit auto-snapshot trigger verified.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| HTTP → backend | Snapshot blob payload (user-controlled), edit-event payload (user-controlled) |
| backend → SQLite | LargeBinary blob column |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-08-03b-01 | DoS | Zip-bomb via decompression | mitigate | RESEARCH §V12: MAX_DECOMPRESSED_BYTES = 10 MB; deserialize raises SnapshotTooLargeError → 413. Mitigates even local-only attack surface. |
| T-08-03b-02 | DoS | Unbounded edit_events rows | mitigate | RESEARCH §Pattern 4: cap edit log at 10,000 ops per branch — enforce at append_edit_event by counting rows for branch_id; raise 409 with EDIT_LOG_FULL when exceeded. (Future plan: add LRU eviction.) |
| T-08-03b-03 | Tampering | Malicious op_type or payload via direct API | accept | Op_type pattern guard at endpoint; payload is JSON column — cannot inject SQL. Local-only tool. |
| T-08-03b-04 | Information Disclosure | Snapshot blob contains user-specific edit logs | accept | Stored in `~/.medieval-forge/medieval_forge.db` — same protection as existing data (RESEARCH §V8). |
</threat_model>

<verification>
- 2 ORM models + 1 serializer + 4 endpoints + 8 integration tests
- Auto-snapshot fires at 25 edits, counter resets, blob round-trips
- Size cap enforced (413 on oversized)
- 2 atomic commits
</verification>

<success_criteria>
Full branch + snapshot + edit-event persistence layer live. Plans 08-04 (frontend store), 08-09 (UI), and 08-10 (manifest extension) can integrate.
</success_criteria>

<output>
After completion, create `.planning/phases/08-.../08-03b-SUMMARY.md`.
</output>
