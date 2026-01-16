# Ops Playbook (SQLite)

## Standard change checklist (Dev -> Prod)
- [ ] Clone prod -> dev: `python scripts/clone_db.py --db data/exam.db --out data/dev.db`
- [ ] Run migrations on dev: `python scripts/run_migrations.py --db data/dev.db`
- [ ] Rebuild FTS on dev (if needed): `python scripts/init_fts.py --db data/dev.db --rebuild`
- [ ] Verify dev results (UI + quick queries)
- [ ] Hot backup prod: `python scripts/backup_db.py --db data/exam.db --keep 30`
- [ ] Run migrations on prod: `python scripts/run_migrations.py --db data/exam.db`
- [ ] Rebuild FTS on prod (if needed): `python scripts/init_fts.py --db data/exam.db --rebuild`
- [ ] Verify prod results (UI + quick queries)

## Emergency recovery (<=5 steps)
1) Roll back feature flags: `AI_AUTO_APPLY=0`, `RETRIEVAL_MODE=bm25`
2) Block writes: `DB_READ_ONLY=1`
3) Restore latest backup:
```bash
copy backups/exam.db.YYYYMMDD_HHMMSS data/exam.db
```
4) Check migration status:
```bash
sqlite3 data/exam.db "SELECT version, applied_at FROM schema_migrations ORDER BY applied_at DESC;"
```
5) Rebuild FTS:
```bash
python scripts/init_fts.py --db data/exam.db --rebuild
```

## Destructive changes (drop/alter) standard
SQLite requires a table rebuild for column drops or type changes. Example:
```sql
BEGIN;
CREATE TABLE questions_new (
    id INTEGER PRIMARY KEY,
    exam_id INTEGER NOT NULL,
    question_number INTEGER NOT NULL,
    lecture_id INTEGER,
    is_classified BOOLEAN DEFAULT 0
    -- add remaining columns here
);
INSERT INTO questions_new (id, exam_id, question_number, lecture_id, is_classified)
SELECT id, exam_id, question_number, lecture_id, is_classified
FROM questions;
DROP TABLE questions;
ALTER TABLE questions_new RENAME TO questions;
CREATE INDEX IF NOT EXISTS idx_questions_exam_id ON questions(exam_id);
COMMIT;
```

## FTS notes
- Rebuild required when:
  - `lecture_chunks` schema changes
  - chunking logic changes (page boundaries/normalization)
  - bulk edits/deletes bypass the indexer
- Command (supports `--db`):
```bash
python scripts/init_fts.py --db data/exam.db --rebuild
```
- Verification after rebuild:
```bash
sqlite3 data/exam.db "SELECT count(*) FROM lecture_chunks_fts;"
```
  - Also run a known query in the UI to confirm candidates appear.

## Startup safety checks
- Pending migrations are checked on app start (`app/__init__.py` -> `app/services/migrations.py`).
- Flags:
  - `CHECK_PENDING_MIGRATIONS=1` (default) to enable detection
  - `FAIL_ON_PENDING_MIGRATIONS=1` to abort in production when pending/mismatched
- Backup enforcement on writes:
  - `AUTO_BACKUP_BEFORE_WRITE=1` enables hot backups per write
  - `ENFORCE_BACKUP_BEFORE_WRITE=1` blocks prod writes if backups are disabled

## Read-only / safety flags
- `DB_READ_ONLY=1` blocks write paths (uploads, indexing, classification apply, practice submit).
- `AI_AUTO_APPLY=0` prevents automatic classification apply.
- `RETRIEVAL_MODE=bm25` (default) or `off` to disable retrieval.
- Optional hot backup hook: `AUTO_BACKUP_BEFORE_WRITE=1` and `AUTO_BACKUP_KEEP=30`.

## Manual verification (no automated tests)
- [ ] Open `/manage` and confirm CRUD still works (dev only).
- [ ] Run a known FTS query and check candidate results.
- [ ] Start an AI classification job and ensure apply respects `AI_AUTO_APPLY`.

## Example Commands (5)
```bash
python scripts/clone_db.py --db data/exam.db --out data/dev.db
python scripts/run_migrations.py --db data/dev.db
python scripts/init_fts.py --db data/dev.db --rebuild
python scripts/backup_db.py --db data/exam.db --keep 30
DB_READ_ONLY=1 python run.py
```
