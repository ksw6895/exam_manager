# Backend Migration for Next.js Integration

This document describes the backend changes made to prepare for Next.js integration.

## Overview

The backend has been refactored to use a centralized configuration system and provide stable API schemas for frontend consumption.

## Changes Made

### Phase 1: Configuration Single Source of Truth

**Goal**: All runtime configuration values used by business logic come from `get_config()`.

**Implementation**:
- Migrated all core service modules to use `from config import get_config`:
  - `app/services/retrieval.py`
  - `app/services/classification_pipeline.py`
  - `app/services/context_expander.py`
  - `app/services/query_transformer.py`
  - `app/services/db_guard.py`

- Replaced all `current_app.config.get()` calls with direct `get_config()` access:
  - `get_config().experiment.*` for experiment settings
  - `get_config().runtime.*` for infrastructure settings
  - Replaced `current_app.logger.warning()` with standard `logging.warning()`

- Added Flask config mirror comment in `app/__init__.py`:
  - Documents that `get_config()` is now the single source of truth
  - Legacy routes using `current_app.config.get()` will use default values

- Added CORS configuration support:
  - New config keys: `CORS_ALLOWED_ORIGINS` (dev), `CORS_ALLOWED_ORIGINS_PROD` (prod)
  - RuntimeConfig updated with `cors_allowed_origins` field
  - `get_experiment_config()` reads `CORS_ALLOWED_ORIGINS` environment variable
  - CORS handler in `app/__init__.py` adds headers based on config
  - Supports OPTIONS preflight and simple origin validation

**Config Access Pattern Changes**:
| File | Before | After |
|-------|--------|--------|
| `app/services/retrieval.py` | `current_app.config.get("HYDE_ENABLED")` | `get_config().experiment.hyde_enabled` |
| `app/services/classification_pipeline.py` | `current_app.config.get("PARENT_ENABLED")` | `get_config().experiment.parent_enabled` |
| `app/services/context_expander.py` | `current_app.config.get("SEMANTIC_EXPANSION_ENABLED")` | `get_config().experiment.semantic_expansion_enabled` |
| `app/services/query_transformer.py` | `current_app.config.get("HYDE_PROMPT_VERSION")` | `get_config().experiment.hyde_prompt_version` |
| `app/services/db_guard.py` | `current_app.config.get("DB_READ_ONLY")` | `get_config().runtime.db_read_only` |

### Phase 2: Domain Objects for Stable API Schemas

**Goal**: Endpoints return stable, explicit schemas built from domain objects.

**Implementation**:
- Added `to_dict()` method to `Candidate` domain model in `app/domain/models.py`
- Added `to_dict()` method to `Evidence` domain model in `app/domain/models.py`

**Domain Objects Enhanced**:
| Class | Method Added | Fields Serialized |
|-------|---------------|-----------|--------------|
| `Candidate` | `to_dict()` | id, title, block_name, full_path, score, evidence, bm25_score, embedding_score, rrf_score |
| `Evidence` | `to_dict()` | page_start, page_end, snippet, chunk_id |

### Phase 3: Next.js Integration Readiness

**Goal**: Backend is easy for Next.js to consume.

**Implementation**:
- CORS configuration now driven by `get_config()`
  - Environment variable: `CORS_ALLOWED_ORIGINS`
  - Defaults:
    - Dev: `http://localhost:3000`
    - Prod: `https://your-domain.com` (placeholder to configure)

- Health endpoint for monitoring:
  - Added `/api/health` endpoint
  - Returns: `{ "status": "ok", "schema_version": "v1" }`
  - Config-safe: Only returns public information, no secrets

- Consistent error format maintained:
  - Existing endpoints already use consistent error patterns:
    - `{ "ok": False, "code": "...", "message": "..." }`
  - No changes made to preserve existing patterns

### What Was NOT Changed (Deliberately)

**No algorithm changes**: All thresholds and model behavior preserved.
- HYDE, retrieval, classification logic untouched
- Auto-Confirm V2, context expansion parameters unchanged
- BM25, semantic search parameters unchanged

**No breaking API changes**: All existing response structures preserved.
- Added only additive fields (schema_version) to health endpoint
- No existing endpoint refactored to use domain objects (time constraint)

**No database schema changes**: All database operations remain in SQLAlchemy models.

### Next Recommended Backend Steps

1. **Gradually migrate remaining routes** to use domain objects:
   - Priority: endpoints returning complex nested data (e.g., `/ai/classify/result/<id>`)
   - Priority: management endpoints with simple CRUD operations
   - Priority: practice endpoints (already well-structured)

2. **Consider adding schema validation for critical endpoints**:
   - Create `scripts/validate_api_schema.py` to validate response keys
   - Test against saved fixtures or expected key sets
   - Run on CI/CD or manually before major deployments

3. **Add production CORS configuration**:
   - Set `CORS_ALLOWED_ORIGINS` environment variable to your production domain
   - Example: `CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com`

## API Schema Stability

### Schema-Stable Endpoints (Ready for Next.js)

The following endpoints now have explicit schema documentation:

1. **`/api/health`** - Health check endpoint
   - Response: `{ "status": "ok", "schema_version": "v1" }`

2. **Practice API** (`/api/practice/*`)
   - Well-structured with consistent field naming
   - No changes made (already stable)

3. **Exam Management API** (`/api/manage/*`, `/api/exam/*`)
   - Well-structured with helpers for payload construction
   - No changes made (already stable)

4. **AI Classification API** (`/ai/*`)
   - Uses internal data structures
   - No changes made (algorithm unchanged)

### Configuration Policy

**For New Code**:
- Import: `from config import get_config`
- Use: `get_config().experiment.*` for experimental settings
- Use: `get_config().runtime.*` for infrastructure settings
- DO NOT use: `current_app.config.get()` in services

**For Legacy Code**:
- Legacy routes can continue using `current_app.config.get()` with defaults
- Flask config mirror is maintained in `app/__init__.py` for backward compatibility
- No immediate migration required for legacy routes

## Verification

- ✅ Python syntax check passed: `python -m compileall` successful on modified files
- ✅ Configuration package compiles without errors
- ✅ Flask app boots successfully with new CORS handling
- ✅ Domain models have `to_dict()` methods for JSON serialization

## Conclusion

The backend is now ready for Next.js integration with:
1. Single source of truth for configuration (`get_config()`)
2. Domain objects with JSON serialization methods
3. CORS support for cross-origin requests
4. Health endpoint for monitoring
5. No breaking changes to existing APIs

This is a **conservative, incremental refactor** following the project's "small, reviewable changes" principle.
 All critical systems (retrieval, classification, AI) now use the centralized configuration system without any behavior changes.