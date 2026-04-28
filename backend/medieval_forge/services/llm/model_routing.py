"""Model routing layer (Etapa 4 — quick-260428-f9x).

Centralizes model selection so each LLM task can be routed to the appropriate
effort tier (low / medium / high) per provider. Foundation for token economy:
Haiku for cheap validation tasks, Opus for deep narrative research.

Public API:
    - TASK_MODEL_TIERS  : provider_id -> {effort -> model_id}
    - TASK_DEFAULT_EFFORT : task name -> default effort tier
    - resolve_model(provider_id, task, effort_override=None) -> model_id

The llamacpp provider returns the sentinel "(server-default)" for every effort
tier — the local server decides which model to serve.
"""
from __future__ import annotations

# Per-provider effort tiers. Values copied verbatim from the master plan
# (hazy-hatching-abelson, sections B.1 + B.2). Do NOT paraphrase model ids.
TASK_MODEL_TIERS: dict[str, dict[str, str]] = {
    "claude":   {"low": "claude-haiku-4-5-20251001", "medium": "claude-sonnet-4-6", "high": "claude-opus-4-7"},
    "openai":   {"low": "gpt-4o-mini",               "medium": "gpt-4o",            "high": "gpt-4-turbo"},
    "gemini":   {"low": "gemini-2.0-flash",          "medium": "gemini-2.0-pro",    "high": "gemini-2.5-pro"},
    "ollama":   {"low": "qwen2.5:3b",                "medium": "qwen2.5:7b",        "high": "qwen2.5:32b"},
    "llamacpp": {"low": "(server-default)",          "medium": "(server-default)",  "high": "(server-default)"},
}

# Default effort per known task. Callers can override with effort_override.
TASK_DEFAULT_EFFORT: dict[str, str] = {
    "validate_barony_assignments": "low",
    "suggest_condado_grouping":    "medium",
    "map_research_full":           "high",
    "codex_genealogy":             "high",
    "codex_wars_battles":          "high",
    "codex_culture_religion":      "medium",
    "codex_population_economy":    "low",
    "codex_personalities":         "medium",
}


def resolve_model(
    provider_id: str,
    task: str,
    effort_override: str | None = None,
) -> str:
    """Resolve (provider, task, effort) to a concrete model id.

    Args:
        provider_id: One of the keys in TASK_MODEL_TIERS (e.g. "claude").
        task: Task name; must be in TASK_DEFAULT_EFFORT unless effort_override is given.
        effort_override: Optional "low" | "medium" | "high"; overrides the task default.

    Returns:
        The model id string for the resolved (provider, effort) pair. For
        ``llamacpp`` this is always the sentinel ``"(server-default)"``.

    Raises:
        ValueError: if provider_id, task, or effort tier is unknown. The error
        message includes the offending value to make diagnostics clear.
    """
    if provider_id not in TASK_MODEL_TIERS:
        raise ValueError(f"Unknown provider_id: {provider_id!r}")

    if effort_override is not None:
        effort = effort_override
    else:
        effort = TASK_DEFAULT_EFFORT.get(task)
        if effort is None:
            raise ValueError(f"Unknown task: {task!r}")

    tier = TASK_MODEL_TIERS[provider_id]
    if effort not in tier:
        raise ValueError(f"Unknown effort tier: {effort!r}")

    return tier[effort]
