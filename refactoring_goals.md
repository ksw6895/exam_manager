# Refactoring Goals (AI Agent Task Brief)
Project: exam_manager (refactor-all-in-one)
Date: 2026-01-18 (Asia/Seoul)

## Objective
Execute a focused refactor that improves **config responsibility separation**, adds **safety guards to destructive scripts**, and introduces a small set of **domain objects** to clarify boundaries and reduce implicit coupling.

Success = codebase remains functionally equivalent (same CLI behaviors, same API responses), but is safer to run and easier to extend.

---

## Scope (3 workstreams)

### 1) Split `config.py` responsibilities
**Problem**
`config.py` mixes runtime defaults, experiment-only toggles, operational settings (paths/DB), and evaluation/tuning thresholds. This makes changes risky and hard to reason about.

**Target design**
Introduce a small config package with clear layers:

```
config/
  __init__.py
  base.py          # stable defaults, safe for all environments
  runtime.py       # env-driven settings (paths, DB, secrets via env)
  experiment.py    # optional experimental toggles + thresholds
  schema.py        # dataclasses / pydantic-like lightweight validation
```
Keep a compatibility shim `config.py` during migration (optional but recommended).

**Implementation steps**
1. Create `config/schema.py`
   - Define dataclasses (or simple classes) like:
     - `RuntimeConfig` (DB path/URL, cache dirs, logging level, model names)
     - `ExperimentConfig` (autoconfirm thresholds, uncertainty thresholds, rerank pool sizes, feature flags)
     - `AppConfig` (composition: runtime + experiment + derived values)
   - Add basic validation (asserts/ValueError) for common mistakes (negative thresholds, missing paths).
2. Create `config/base.py`
   - Put stable defaults here (things that should not change often).
3. Create `config/runtime.py`
   - Read environment variables and override base defaults.
   - No experiment knobs here.
4. Create `config/experiment.py`
   - Hold experiment flags and tuning parameters; allow env overrides but clearly namespaced (e.g., `EXPERIMENT_*`).
5. Replace imports progressively:
   - Replace `from config import X` with `from config import get_config` or `from config.schema import AppConfig`.
6. Add a single entrypoint:
   - `config/__init__.py` exposes `get_config()` which returns an `AppConfig` singleton (cached).
7. Backward compatibility:
   - Keep existing `config.py` exporting the previous names but internally reading from new config objects.
   - Mark legacy exports with `# TODO(deprecate):`.

**Acceptance criteria**
- No module outside `config/` reads env vars directly.
- `get_config()` is the only supported way to obtain settings.
- Running existing scripts still works without requiring new flags.
- `config.py` (legacy) is either removed or reduced to a shim with no logic duplication.

---

### 2) Add safety guards to destructive scripts
**Problem**
Scripts can mutate DB or overwrite embeddings/caches. Easy to run the wrong command and destroy state.

**Target design**
- Every script declares its safety level and enforces confirmation for destructive actions.
- Provide a standard safety helper used by all scripts.

**Standard safety levels**
- `READ_ONLY` (safe, no writes)
- `MUTATES_STATE` (writes but non-destructive)
- `DESTRUCTIVE` (drops/overwrites large data; requires explicit opt-in)

**Implementation steps**
1. Create `scripts/_safety.py`
   - Helper functions:
     - `class SafetyLevel(Enum): ...`
     - `require_confirmation(level, message, env_flag=None, cli_flag=None)`
   - Behavior:
     - For `DESTRUCTIVE`: require either:
       - `--yes-i-really-mean-it` flag, OR
       - env var like `ALLOW_DESTRUCTIVE=1`
     - Also print a clear warning showing what will be modified (paths/db).
2. Update each script in `scripts/`:
   - Add module docstring at top:
     - `"""SAFETY: READ_ONLY|MUTATES_STATE|DESTRUCTIVE"""`
   - Identify destructive operations (e.g., rebuilding embeddings, deleting caches, dropping tables).
   - Wrap them with safety check.
3. Add `--dry-run` option to destructive scripts where feasible:
   - Dry-run prints what would happen without writing.
4. Standardize CLI:
   - Use `argparse` for consistent flags:
     - `--dry-run`
     - `--yes-i-really-mean-it`
     - `--target-db`
     - `--cache-dir`
5. Optional: add a shared “script header” function to print:
   - script name
   - timestamp
   - config snapshot (non-secret)

**Acceptance criteria**
- Any script that can delete/overwrite data fails fast unless opt-in flag/env is present.
- Scripts print the target DB/path before acting.
- `--dry-run` exists for at least the top 2 destructive scripts (embeddings build + any DB-reset like action).

---

### 3) Introduce 3–5 minimal domain objects
**Problem**
Core concepts exist only implicitly via dicts/tuples/function params, which obscures boundaries and creates accidental coupling.

**Target design**
Add lightweight dataclasses in a `domain/` module. Start small; do not over-engineer.

**Recommended domain objects (choose 3–5)**
1. `Question`
   - `id`, `text`, optional metadata
2. `LectureChunk`
   - `lecture_id`, `chunk_id`, `text`, optional `source_ref`
3. `Candidate`
   - `chunk` (LectureChunk or chunk_id), `bm25_score`, `embed_score`, `rank`
4. `RetrievalResult`
   - `question_id`, `candidates: list[Candidate]`, `timings`, `debug`
5. `ClassificationDecision`
   - `label`, `confidence`, `is_autoconfirmed`, `reason`

**Implementation steps**
1. Create `app/domain/` (or `domain/` at repo root; prefer under `app/` if this is a Flask app):
   - `app/domain/models.py` with dataclasses + type hints.
2. Add conversion helpers where needed:
   - `from_row(...)`, `to_dict()` (for JSON output), `from_dict()` (for cached artifacts).
3. Identify 2–3 hotspots in the pipeline where dicts are passed around:
   - retrieval output
   - embedding rerank output
   - classifier decision payload
   Replace with domain objects.
4. Keep boundaries clean:
   - Domain objects should not import Flask, DB drivers, or heavy ML libs.
   - They can hold primitive data only.
5. Add minimal tests (even without full test suite):
   - Roundtrip serialization tests for the domain objects.
   - These can be simple `python -m` runnable checks.

**Acceptance criteria**
- At least 3 domain objects are used in core flow (not just defined).
- Type hints reduce ambiguity in function signatures.
- Serialization for at least 2 domain objects exists (dict/JSON).

---

## Non-goals (explicitly out of scope)
- Changing retrieval/classifier algorithms or thresholds for performance improvements
- UI/Frontend migration
- Major DB schema redesign
- Large test framework adoption (keep minimal)

---

## Deliverables
1. New `config/` package (and optional `config.py` shim)
2. `scripts/_safety.py` + updated scripts enforcing safety levels
3. `domain` dataclasses integrated in at least one end-to-end path
4. Short changelog in `REFactoring_Issues.md` or new `docs/refactor_next.md`

---

## Definition of Done (quick checklist)
- [ ] `get_config()` exists and is used broadly
- [ ] Destructive scripts require `--yes-i-really-mean-it` or `ALLOW_DESTRUCTIVE=1`
- [ ] `--dry-run` implemented for key destructive scripts
- [ ] 3–5 domain objects added and used in production code paths
- [ ] Project runs as before (no behavioral regressions in the standard workflow)

---

## Suggested branch + commit plan
- Branch: `refactor/config-safety-domain`
- Commits:
  1) `config: introduce config package + get_config`
  2) `scripts: add safety helper + guard destructive operations`
  3) `domain: add dataclasses and integrate into retrieval/classifier flow`
  4) `docs: update refactoring notes and usage`
