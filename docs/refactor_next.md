# Refactoring Summary

This document summarizes the refactoring work completed based on `refactoring_goals.md`.

## What Changed

### Phase 1: Config Responsibility Split

**Created `config/` package with layered configuration:**
- `config/schema.py` - Dataclasses for RuntimeConfig, ExperimentConfig, AppConfig with validation
- `config/base.py` - Stable defaults (DB paths, directories, default values)
- `config/runtime.py` - Environment-driven settings (reads env vars, applies overrides)
- `config/experiment.py` - Experimental toggles and thresholds (namespaced EXPERIMENT_* or specific)
- `config/__init__.py` - `get_config()` singleton that composes runtime + experiment config

**Updated `config.py` to backward compatibility shim:**
- Imports from new config package
- Exports all legacy config names to maintain compatibility
- Existing code using `from config import Config` continues to work

**Updated `app/__init__.py`:**
- Now calls `set_config_name()` before loading config
- Loads from new `get_config()` singleton instead of old config mapping

**Acceptance Criteria Met:**
- No module outside `config/` reads env vars directly
- `get_config()` is the authoritative way to obtain settings
- Running existing scripts still works without new flags

### Phase 2: Script Safety Guards

**Created `scripts/_safety.py`:**
- `SafetyLevel` enum: READ_ONLY, MUTATES_STATE, DESTRUCTIVE
- `require_confirmation()` function for checking opt-in:
  - Checks `ALLOW_DESTRUCTIVE=1` env var
  - Checks `--yes-i-really-mean-it` CLI flag
  - Supports `--dry-run` mode
- `print_script_header()` for standardized script output

**Updated Destructive Scripts with Safety Guards:**

1. **`scripts/build_embeddings.py`**
   - Added SAFETY docstring: "DESTRUCTIVE (if --rebuild specified)"
   - Added `--dry-run` and `--yes-i-really-mean-it` CLI flags
   - Wrapped rebuild operations with `require_confirmation()`
   - Dry-run shows what would be done without writing

2. **`scripts/init_fts.py`**
   - Added SAFETY docstring: "DESTRUCTIVE (if --rebuild specified)"
   - Added `--dry-run` and `--yes-i-really-mean-it` CLI flags
   - Wrapped FTS table clear operation with `require_confirmation()`
   - Dry-run shows what would be done without writing

3. **`scripts/drop_lecture_keywords.py`**
   - Added SAFETY docstring: "DESTRUCTIVE (modifies database schema)"
   - Added `--dry-run` and `--yes-i-really-mean-it` CLI flags
   - Wrapped schema modification with `require_confirmation()`
   - Dry-run shows what would be done without writing
   - Added print_script_header() for standardized output

4. **`scripts/build_queries.py`**
   - Added SAFETY docstring: "DESTRUCTIVE (if --force specified)"
   - Added `--dry-run` and `--yes-i-really-mean-it` CLI flags
   - Wrapped query deletion with `require_confirmation()`
   - Dry-run support for all operations
   - Added print_script_header() for standardized output

**Acceptance Criteria Met:**
- Destructive scripts fail fast without explicit opt-in
- Scripts print target DB/path before acting
- `--dry-run` produces no writes

### Phase 3: Domain Object Introduction

**Created `app/domain/` package:**
- `app/domain/models.py` - Dataclasses for domain concepts
- `app/domain/__init__.py` - Package exports

**Domain Models Implemented:**
1. `LectureChunk` - Lecture note chunk with page ranges and content
2. `Question` - Question from database with metadata
3. `Candidate` - Retrieval candidate with scores and evidence
4. `Evidence` - Evidence snippet for a candidate
5. `RetrievalResult` - Output from retrieval stage with candidates and timings
6. `ClassificationDecision` - LLM classification decision with confidence and evidence

**Key Properties:**
- Pure data only - No Flask, DB, or ML imports
- All models have `to_dict()` for JSON serialization
- All models have `from_dict()` class method for deserialization where applicable
- Type hints for clearer function signatures

**Acceptance Criteria Status: Partially Met**
- ✅ Domain models are defined and available
- ✅ Serialization helpers (`to_dict` / `from_dict`) exist
- ⚠️ Domain models are not yet used broadly in core retrieval/classification flows (intentionally deferred to avoid regressions)
- ✅ External interfaces unchanged (JSON in/out)

### What Was NOT Done

Per refactoring goals:

- **Replacing all dict usage in retrieval.py and ai_classifier.py with domain objects**
  - **Reason**: The existing codebase has extensive `current_app.config.get()` patterns and dict structures throughout the pipeline. Replacing these all at once would:
    1. Risk regressions in complex AI classification and retrieval flows
    2. Violate the "small, reviewable changes" principle
    3. The `classification_pipeline.py` already has dataclasses (RetrievalResult, JudgmentResult) that serve similar purpose
  - **Note**: The `ClassificationContext`, `RetrievalResult`, `ExpansionResult`, and `JudgmentResult` in `classification_pipeline.py` were preserved and NOT modified, as they already provide the domain model pattern intended by this refactoring.
  - **Note:** `classification_pipeline.py` contains existing dataclasses serving similar roles. To avoid introducing competing parallel models in a single PR, those were preserved unchanged. A future cleanup may consolidate these representations, but this refactor intentionally avoids that scope.


- **Changing algorithms, thresholds, or model behavior**
  - All experiment configs preserve original values
  - No changes to AI_CONFIDENCE_THRESHOLD, RETRIEVAL_MODE, HYDE settings, etc.

- **UI/Frontend migration**
  - Next.js and Legacy Flask UI were not touched

- **Major DB schema redesign**
  - No changes to SQLAlchemy models

- **Large test framework adoption**
  - No new test suite beyond existing scripts

  ## Configuration Policy (Source of Truth)

- **Single Source of Truth:** `get_config()` is authoritative for all configuration.
- **Legacy compatibility only:** `current_app.config` is a **read-only mirror** maintained temporarily to avoid breaking existing code paths.
- **Rule:** New code MUST NOT introduce new `current_app.config.get(...)` usage. Use `from config import get_config` instead.
- **Deprecation:** The mirror and `config.py` shim are intended to be removed after migrations are complete.


## Behavioral Equivalence

All changes are backward compatible:
- `config.py` shim ensures old code continues to work
- New `get_config()` pattern is internal; scripts still use legacy config
- Safety checks are opt-in with `--yes-i-really-mean-it` or `ALLOW_DESTRUCTIVE=1`
- `--dry-run` allows previewing destructive operations

## Recommended Next Steps

1. **Lock config usage:** Treat `get_config()` as authoritative; reject new usages of `current_app.config.get(...)` in reviews.
2. **DTO at API boundaries:** Apply domain DTOs to at least one endpoint (recommended: `/api/health` or a read-only `/ai/classify/result/<id>`).
3. **Schema validation:** Add `scripts/validate_api_schema.py` to assert stable response keys for critical endpoints.
4. **Production CORS:** Set `CORS_ALLOWED_ORIGINS` to the deployed Next.js domain.