"""SC-2 prompt builder integer-acceptance lock (D-04c).

The prompt builders in services/llm/prompt.py have ALWAYS taken integer
period_start/period_end (Phase 07 literal-port). This test file locks that
contract so a future regression renaming back to a string parameter breaks
the build immediately.

Implemented in plan 07.1-04. The scaffold from plan 07.1-00 is replaced here.
"""
from medieval_forge.services.llm.prompt import build_research_prompt


def test_build_research_prompt_accepts_integer_period_868_1000() -> None:
    out = build_research_prompt(
        country_name="Iberia",
        period_start=868,
        period_end=1000,
        bbox=None,
    )
    assert isinstance(out, str)
    assert len(out) > 0


def test_build_research_prompt_period_range_renders_868_to_1000_AD() -> None:
    out = build_research_prompt(
        country_name="Iberia",
        period_start=868,
        period_end=1000,
        bbox=None,
    )
    assert "868" in out
    assert "1000" in out


def test_build_research_prompt_snapshot_renders_868_AD() -> None:
    """D-02 snapshot case: start == end."""
    out = build_research_prompt(
        country_name="Iberia",
        period_start=868,
        period_end=868,
        bbox=None,
    )
    assert "868" in out
