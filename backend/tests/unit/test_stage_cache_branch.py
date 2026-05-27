"""Branch-aware cache tests for Phase 08 D-23.

Covers REQ-IDs: BRANCH-01, BRANCH-02, DAG-04, DAG-05
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md

Atomic swap: this file replaces test_stage_cache.py (deleted in same commit).
"""
import numpy as np
import pytest

from medieval_forge.services.pipeline.cache import (
    _STAGE_CACHE,
    _VORONOI_CACHE,
    cache_clear_branch,
    cache_clear_project,
    cache_get,
    cache_put,
)


@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """Isolate each test — clear both caches before and after."""
    _STAGE_CACHE.clear()
    _VORONOI_CACHE.clear()
    yield
    _STAGE_CACHE.clear()
    _VORONOI_CACHE.clear()


ARR1 = np.array([[1, 2], [3, 4]], dtype=np.int16)
ARR2 = np.array([[5, 6], [7, 8]], dtype=np.int16)
ARR3 = np.array([[9, 10], [11, 12]], dtype=np.int16)


def test_cache_put_and_get_returns_entry_with_correct_token_for_branch():
    """BRANCH-01 + DAG-04: cache_put(project, branch, stage) stored separately per branch.

    Put landmask token 'tok1' on branch 'main'; get should return entry with token=='tok1'.
    """
    cache_put("p1", "main", "landmask", "tok1", ARR1)
    entry = cache_get("p1", "main", "landmask")
    assert entry is not None
    assert entry.token == "tok1"
    assert np.array_equal(entry.array, ARR1)
    assert entry.prior_token is None
    assert entry.prior_array is None


def test_cache_get_on_different_branch_returns_none_when_only_main_populated():
    """BRANCH-01: branch isolation — 'branch_a' cache miss when only 'main' was written.

    Put landmask on 'main'; get on 'branch_a' must return None (no cross-branch leak).
    """
    cache_put("p1", "main", "landmask", "tok1", ARR1)
    result = cache_get("p1", "branch_a", "landmask")
    assert result is None, "Cross-branch cache leak: branch_a saw main's entry"


def test_cache_put_second_write_promotes_prior_entry():
    """D-03 latest+prior: second put on same (project, branch, stage) promotes prior.

    First put: token='tok1'. Second put: token='tok2'. Entry has prior_token=='tok1'.
    """
    cache_put("p1", "main", "landmask", "tok1", ARR1)
    cache_put("p1", "main", "landmask", "tok2", ARR2)
    entry = cache_get("p1", "main", "landmask")
    assert entry is not None
    assert entry.token == "tok2"
    assert np.array_equal(entry.array, ARR2)
    assert entry.prior_token == "tok1"
    assert np.array_equal(entry.prior_array, ARR1)


def test_cache_clear_project_removes_all_branches_for_project():
    """DAG-05: cache_clear_project() drops ALL branches for that project_id.

    Populate 'main' and 'branch_a'; clear project; both branches should be gone.
    """
    cache_put("p1", "main", "landmask", "tok1", ARR1)
    cache_put("p1", "branch_a", "landmask", "tok2", ARR2)
    cache_put("p2", "main", "landmask", "tok3", ARR3)

    cache_clear_project("p1")

    assert cache_get("p1", "main", "landmask") is None
    assert cache_get("p1", "branch_a", "landmask") is None
    # p2 must be unaffected
    assert cache_get("p2", "main", "landmask") is not None


def test_voronoi_cache_also_branch_scoped_and_isolated():
    """DAG-04: _VORONOI_CACHE keyed by (project_id, branch_id) — branch isolation preserved.

    Write voronoi side-table on 'main'; 'branch_a' must not see it.
    """
    _VORONOI_CACHE.setdefault("p1", {})["main"] = {"vor": "data_main"}

    branch_a_voronoi = _VORONOI_CACHE.get("p1", {}).get("branch_a")
    assert branch_a_voronoi is None, "Cross-branch voronoi leak: branch_a saw main's entry"

    main_voronoi = _VORONOI_CACHE.get("p1", {}).get("main")
    assert main_voronoi == {"vor": "data_main"}


def test_cache_clear_branch_removes_only_target_branch_leaving_others():
    """BRANCH-02: cache_clear_branch(project, branch) evicts only that branch's entries.

    Populate 'main' and 'branch_a'; clear 'branch_a'; 'main' must survive.
    """
    cache_put("p1", "main", "landmask", "tok1", ARR1)
    cache_put("p1", "branch_a", "landmask", "tok2", ARR2)
    _VORONOI_CACHE.setdefault("p1", {})["main"] = {"vor": "main_data"}
    _VORONOI_CACHE.setdefault("p1", {})["branch_a"] = {"vor": "branch_a_data"}

    cache_clear_branch("p1", "branch_a")

    assert cache_get("p1", "branch_a", "landmask") is None
    assert _VORONOI_CACHE.get("p1", {}).get("branch_a") is None
    # main must survive
    assert cache_get("p1", "main", "landmask") is not None
    assert _VORONOI_CACHE.get("p1", {}).get("main") is not None
