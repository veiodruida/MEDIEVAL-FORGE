"""SC-1a..d unit coverage for period_start/period_end pydantic validation (D-01, D-02, D-04c).

Implemented in plan 07.1-04. The scaffolds from plan 07.1-00 are replaced here.
"""
import pytest
from pydantic import ValidationError

from medieval_forge.api.v3.research import StartResearchBody


_BASE = dict(
    project_id="00000000-0000-0000-0000-000000000001",
    provider="claude",
    model="claude-sonnet-4",
    country_qid="Q29",
    condado_ids=["c1", "c2"],
)


def test_period_start_below_min_rejects_zero() -> None:
    with pytest.raises(ValidationError):
        StartResearchBody(**_BASE, period_start=0, period_end=900)


def test_period_end_above_max_rejects_2101() -> None:
    with pytest.raises(ValidationError):
        StartResearchBody(**_BASE, period_start=800, period_end=2101)


def test_period_start_greater_than_end_rejects_1000_vs_868() -> None:
    with pytest.raises(ValidationError) as exc_info:
        StartResearchBody(**_BASE, period_start=1000, period_end=868)
    msg = str(exc_info.value)
    assert "period_start" in msg and "period_end" in msg


def test_period_start_equals_end_accepts_snapshot_868_868() -> None:
    body = StartResearchBody(**_BASE, period_start=868, period_end=868)
    assert body.period_start == 868
    assert body.period_end == 868


def test_period_non_integer_float_rejected_868_5() -> None:
    with pytest.raises(ValidationError):
        StartResearchBody(**_BASE, period_start=868.5, period_end=900)  # type: ignore[arg-type]
