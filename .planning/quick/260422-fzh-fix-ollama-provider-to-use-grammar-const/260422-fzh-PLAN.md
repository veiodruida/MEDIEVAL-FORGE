# Quick Task 260422-fzh

## Objective
Fix Ollama provider to use grammar-constrained structured output instead of format="json".

## Task
Edit `backend/medieval_forge/services/llm/ollama.py`:
- Change `format="json"` → `format=schema.model_json_schema()`
- This uses Ollama's GBNF grammar constraints to enforce all required fields
