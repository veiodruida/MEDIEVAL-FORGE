"""SC-2 cache_key signature lock (D-04 + D-11 carry).

Implemented in plan 07.1-04. The scaffold from plan 07.1-00 is replaced here.
"""
import inspect

from medieval_forge.services.research.cache import cache_key


def test_cache_key_differs_when_period_start_differs_by_one() -> None:
    k1 = cache_key("q29", 868, 1000, "claude", "m", ["c1"])
    k2 = cache_key("q29", 869, 1000, "claude", "m", ["c1"])
    assert k1 != k2


def test_cache_key_differs_when_period_end_differs_by_one() -> None:
    k1 = cache_key("q29", 868, 1000, "claude", "m", ["c1"])
    k2 = cache_key("q29", 868, 1001, "claude", "m", ["c1"])
    assert k1 != k2


def test_cache_key_identical_for_same_country_start_end_provider_model_condados() -> None:
    k1 = cache_key("q29", 868, 1000, "claude", "m", ["c1", "c2"])
    k2 = cache_key("q29", 868, 1000, "claude", "m", ["c1", "c2"])
    assert k1 == k2


def test_cache_key_signature_takes_period_start_int_period_end_int_not_period_label() -> None:
    sig = inspect.signature(cache_key)
    params = list(sig.parameters)
    assert "period_start" in params
    assert "period_end" in params
    assert "period_label" not in params
