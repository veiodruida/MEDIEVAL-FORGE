"""SC-4a..f Wave 0 scaffold. Implementation in plan 07.1-05 (llamacpp_launcher)."""
import pytest


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_list_models_empty_dir_returns_empty_list() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_list_models_returns_sorted_gguf_filenames_only() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_list_models_case_insensitive_gguf_suffix() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_resolve_binary_uses_env_override_when_set() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_resolve_binary_falls_back_to_shutil_which() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_launch_picks_free_port_via_socket_bind() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_launch_rejects_path_traversal_dotdot_filename() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_launch_rejects_filename_with_directory_component() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_launch_rejects_non_gguf_suffix() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_launch_idempotent_same_model_returns_same_pid() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_launch_conflict_different_model_raises_LlamacppLaunchConflict() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_launch_missing_binary_raises_LlamacppBinaryMissing() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_shutdown_sync_kills_alive_subprocess_within_5s() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_shutdown_sync_idempotent_when_no_process() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_atexit_registered_exactly_once() -> None:
    pass


@pytest.mark.skip(reason="Wave 0 scaffold — implementation in plan 07.1-05")
def test_reset_state_for_tests_clears_module_state() -> None:
    pass
