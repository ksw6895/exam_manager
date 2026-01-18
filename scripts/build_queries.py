"""
Build HyDE-lite query transformations for questions.

SAFETY: DESTRUCTIVE (if --force specified)

Usage:
  python scripts/build_queries.py --provider gemini --concurrency 10 --skip-existing
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv()

from app import create_app, db
from app.models import Question, QuestionQuery
from app.services.query_transformer import get_query_payload


def _normalize_db_uri(db_value: str | None) -> str | None:
    if not db_value:
        return None
    if "://" in db_value:
        return db_value
    path = Path(db_value).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def _build_question_text(question: Question) -> str:
    choices = [c.content for c in question.choices.order_by("choice_number").all()]
    question_text = question.content or ""
    if choices:
        question_text = f"{question_text}\n" + " ".join(choices)
    return question_text.strip()


def _load_question_ids(path: str) -> list[int]:
    ids: list[int] = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            ids.append(int(raw))
        except ValueError:
            continue
    return ids


def _collect_question_ids(
    app,
    skip_existing: bool,
    limit: int | None,
    question_ids_file: str | None,
) -> list[int]:
    prompt_version = app.config.get("HYDE_PROMPT_VERSION", "hyde_v1")
    query = Question.query.order_by(Question.id.asc())

    if question_ids_file:
        ids = _load_question_ids(question_ids_file)
        if not ids:
            return []
        query = query.filter(Question.id.in_(ids))

    if skip_existing:
        query = query.outerjoin(
            QuestionQuery,
            (QuestionQuery.question_id == Question.id)
            & (QuestionQuery.prompt_version == prompt_version),
        ).filter(QuestionQuery.question_id.is_(None))
    if limit:
        query = query.limit(limit)
    return [row.id for row in query.all()]


def _process_question(
    app, question_id: int, force: bool, dry_run: bool = False
) -> bool:
    with app.app_context():
        prompt_version = app.config.get("HYDE_PROMPT_VERSION", "hyde_v1")
        if force:
            if not dry_run:
                QuestionQuery.query.filter_by(
                    question_id=question_id, prompt_version=prompt_version
                ).delete(synchronize_session=False)
                db.session.commit()
            else:
                print(f"[DRY-RUN] Would delete query for Q{question_id}")
            return False

        question = Question.query.get(question_id)
        if not question:
            return False
        question_text = _build_question_text(question)
        payload = get_query_payload(
            question_id,
            question_text,
            allow_generate=True,
        )
        return payload is not None


def main() -> None:
    try:
        from scripts._safety import (
            SafetyLevel,
            require_confirmation,
            print_script_header,
        )
    except ModuleNotFoundError:
        from _safety import SafetyLevel, require_confirmation, print_script_header

    parser = argparse.ArgumentParser(description="Build HyDE-lite queries.")
    parser.add_argument("--db", default="data/dev.db", help="SQLite db path.")
    parser.add_argument(
        "--provider",
        default="gemini",
        help="Provider name (only gemini supported).",
    )
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--question-ids-file", default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing.",
    )
    parser.add_argument(
        "--yes-i-really-mean-it",
        action="store_true",
        help="Confirm destructive operation.",
    )
    args = parser.parse_args()

    print_script_header("build_queries.py", _normalize_db_uri(args.db))

    if not require_confirmation(
        SafetyLevel.DESTRUCTIVE,
        "overwrite existing HyDE queries with --force",
        env_flag="ALLOW_DESTRUCTIVE",
        cli_flag="--yes-i-really-mean-it" in sys.argv,
        dry_run=args.dry_run,
    ):
        return

    if args.provider != "gemini":
        raise ValueError("Only gemini provider is supported.")

    db_uri = _normalize_db_uri(args.db)
    if not db_uri:
        raise ValueError("DB path is required.")

    app = create_app("default", db_uri_override=db_uri, skip_migration_check=True)

    with app.app_context():
        question_ids = _collect_question_ids(
            app,
            args.skip_existing and not args.force,
            args.limit,
            args.question_ids_file,
        )

    total = len(question_ids)
    if total == 0:
        print("No questions to process.")
        return

    success = 0
    failures = 0
    max_workers = max(1, args.concurrency)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_question, app, qid, args.force, args.dry_run): qid
            for qid in question_ids
        }
        for future in as_completed(futures):
            qid = futures[future]
            try:
                ok = future.result()
            except Exception as exc:
                ok = False
                app.logger.warning("Query build failed for Q%s: %s", qid, exc)
            if ok:
                success += 1
            else:
                failures += 1

    print(f"Processed {total} questions (success={success}, failed={failures}).")


if __name__ == "__main__":
    main()
