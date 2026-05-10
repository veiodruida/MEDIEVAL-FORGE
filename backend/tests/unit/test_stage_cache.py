"""Tests for Plan 04-01 D-03: _STAGE_CACHE lifecycle + thread-safety.

Verifies:
  - cache_put then cache_get returns correct StageEntry
  - Second put promotes current to prior
  - cache_clear_project removes all entries for that project, others untouched
  - Concurrent reads + writes from 2 threads don't raise
"""
from __future__ import annotations

import threading
import numpy as np
import pytest

from medieval_forge.services.pipeline.cache import (
    cache_get,
    cache_put,
    cache_clear_project,
    StageEntry,
    _STAGE_CACHE,
)

pytestmark = pytest.mark.unit


def _fresh_project() -> str:
    """Generate a unique project id per test to avoid cross-test cache pollution."""
    import uuid
    return str(uuid.uuid4())


def test_cache_put_then_get_returns_entry() -> None:
    pid = _fresh_project()
    arr = np.zeros((10, 10), dtype=np.int16)
    cache_put(pid, "median", "tok_abc", arr)
    entry = cache_get(pid, "median")
    assert entry is not None
    assert entry.token == "tok_abc"
    assert entry.prior_token is None
    assert entry.prior_array is None
    assert np.array_equal(entry.array, arr)


def test_second_put_promotes_prior() -> None:
    pid = _fresh_project()
    arr1 = np.zeros((10, 10), dtype=np.int16)
    arr2 = np.ones((10, 10), dtype=np.int16)
    cache_put(pid, "median", "tok_abc", arr1)
    cache_put(pid, "median", "tok_def", arr2)
    entry = cache_get(pid, "median")
    assert entry is not None
    assert entry.token == "tok_def"
    assert entry.prior_token == "tok_abc"
    assert entry.prior_array is not None
    assert np.array_equal(entry.prior_array, arr1)


def test_clear_project_removes_all_entries() -> None:
    pid1 = _fresh_project()
    pid2 = _fresh_project()
    arr = np.zeros((5, 5), dtype=np.int16)

    # Put 2 stages for pid1 and 1 stage for pid2
    cache_put(pid1, "median", "tok1", arr)
    cache_put(pid1, "smooth", "tok2", arr)
    cache_put(pid2, "median", "tok3", arr)

    cache_clear_project(pid1)

    assert cache_get(pid1, "median") is None
    assert cache_get(pid1, "smooth") is None
    # pid2 untouched
    assert cache_get(pid2, "median") is not None


def test_concurrent_put_get_thread_safe() -> None:
    pid = _fresh_project()
    arr = np.zeros((8, 8), dtype=np.int16)
    errors: list[Exception] = []

    def writer():
        for i in range(1000):
            try:
                cache_put(pid, "median", f"tok_{i}", arr)
            except Exception as e:
                errors.append(e)

    def reader():
        for _ in range(1000):
            try:
                entry = cache_get(pid, "median")
                # If we got an entry, it must be a complete StageEntry
                if entry is not None:
                    assert isinstance(entry, StageEntry)
                    assert isinstance(entry.token, str)
                    assert entry.array.shape == (8, 8)
            except Exception as e:
                errors.append(e)

    t1 = threading.Thread(target=writer)
    t2 = threading.Thread(target=reader)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors, f"Thread safety violations: {errors}"
