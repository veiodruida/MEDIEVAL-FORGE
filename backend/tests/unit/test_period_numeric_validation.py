"""SC-1a..d Wave 0 scaffold. Implementation lands in plan 07.1-06 (period swap backend)."""
import pytest


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-06")
def test_period_start_below_min_rejects_zero() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-06")
def test_period_end_above_max_rejects_2101() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-06")
def test_period_start_greater_than_end_rejects_1000_vs_868() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-06")
def test_period_start_equals_end_accepts_snapshot_868_868() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-06")
def test_period_non_integer_float_rejected_868_5() -> None:
    pass
