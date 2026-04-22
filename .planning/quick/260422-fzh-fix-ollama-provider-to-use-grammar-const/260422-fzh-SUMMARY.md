# Quick Task 260422-fzh: Summary

**Status:** Complete  
**Commit:** 7081547

## What was done
Changed `format="json"` to `format=schema.model_json_schema()` in `ollama.py` line 62.

Ollama 0.4+ accepts a JSON Schema dict as `format`, which triggers grammar-constrained
generation (GBNF via llama.cpp). This forces the model to emit all required fields
(kingdoms, duchies, condados_assignment, baronies) instead of stopping after the first key.

Root cause: `format="json"` only guarantees syntactically valid JSON. Local models like
gemma4 would output a partial object (just `kingdoms`) and consider the task done.
