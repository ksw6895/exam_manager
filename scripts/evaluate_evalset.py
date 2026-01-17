"""
Evaluate retrieval/classification against evaluation_labels.

Usage:
  python scripts/evaluate_evalset.py --db data/dev.db
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")

from app import create_app
from app import db
from app.models import EvaluationLabel, Question
from app.services import retrieval, retrieval_features
from app.services.classifier_cache import ClassifierResultCache, build_config_hash


def _parse_list(value: str, cast=float):
    if not value:
        return []
    items = []
    for raw in value.split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            items.append(cast(raw))
        except ValueError:
            continue
    return items


def _build_question_text(question: Question) -> str:
    choices = [c.content for c in question.choices.order_by("choice_number").all()]
    question_text = question.content or ""
    if choices:
        question_text = f"{question_text}\n" + " ".join(choices)
    return question_text.strip()


def _candidate_payload(candidates):
    payload = []
    for cand in candidates:
        payload.append(
            {
                "id": cand.get("id"),
                "full_path": cand.get("full_path"),
                "evidence": [
                    {
                        "page_start": ev.get("page_start"),
                        "page_end": ev.get("page_end"),
                        "snippet": ev.get("snippet"),
                        "chunk_id": ev.get("chunk_id"),
                    }
                    for ev in (cand.get("evidence") or [])
                ],
            }
        )
    return payload


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, title: str, rows: list[dict]) -> None:
    lines = [f"# {title}", ""]
    for row in rows:
        lines.append(f"## Q{row['question_id']}")
        lines.append(f"- gold_lecture_id: {row['gold_lecture_id']}")
        lines.append(f"- predicted_lecture_id: {row['predicted_lecture_id']}")
        lines.append("- top_candidates:")
        for cand in row["top_candidates"]:
            lines.append(f"  - {cand['id']}: {cand['full_path']}")
            for ev in cand.get("evidence", []):
                page_start = ev.get("page_start")
                page_end = ev.get("page_end")
                if page_start is None:
                    page_label = "p.?"
                elif page_end and page_end != page_start:
                    page_label = f"p.{page_start}-{page_end}"
                else:
                    page_label = f"p.{page_start}"
                snippet = ev.get("snippet") or ""
                lines.append(f"    - {page_label}: {snippet}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _load_question_ids(path: str) -> set[int]:
    ids = set()
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            ids.add(int(raw))
        except ValueError:
            continue
    return ids


def _classifier_config_hash(app, retrieval_mode: str, max_k: int, evidence_per_lecture: int) -> str:
    cfg = {
        "retrieval_mode": retrieval_mode,
        "max_k": max_k,
        "evidence_per_lecture": evidence_per_lecture,
        "parent_enabled": bool(app.config.get("PARENT_ENABLED", False)),
        "parent_max_chars": int(app.config.get("PARENT_MAX_CHARS", 3500)),
        "semantic_expansion_enabled": bool(app.config.get("SEMANTIC_EXPANSION_ENABLED", True)),
        "semantic_expansion_top_n": int(app.config.get("SEMANTIC_EXPANSION_TOP_N", 6)),
        "semantic_expansion_max_extra": int(app.config.get("SEMANTIC_EXPANSION_MAX_EXTRA", 2)),
        "semantic_expansion_query_max_chars": int(app.config.get("SEMANTIC_EXPANSION_QUERY_MAX_CHARS", 1200)),
        "auto_confirm_v2_delta": float(app.config.get("AUTO_CONFIRM_V2_DELTA", 0.05)),
        "auto_confirm_v2_max_bm25_rank": int(app.config.get("AUTO_CONFIRM_V2_MAX_BM25_RANK", 5)),
        "auto_confirm_v2_delta_uncertain": float(app.config.get("AUTO_CONFIRM_V2_DELTA_UNCERTAIN", 0.03)),
        "auto_confirm_v2_min_chunk_len": int(app.config.get("AUTO_CONFIRM_V2_MIN_CHUNK_LEN", 200)),
        "embedding_model": app.config.get("EMBEDDING_MODEL_NAME"),
        "embedding_top_n": int(app.config.get("EMBEDDING_TOP_N", 300)),
        "rrf_k": int(app.config.get("RRF_K", 60)),
        "hyde_enabled": bool(app.config.get("HYDE_ENABLED", False)),
        "hyde_strategy": app.config.get("HYDE_STRATEGY", "blend"),
        "hyde_bm25_variant": app.config.get("HYDE_BM25_VARIANT", "mixed_light"),
        "hyde_negative_mode": app.config.get("HYDE_NEGATIVE_MODE", "stopwords"),
    }
    return build_config_hash(cfg)


def _classify_worker(app, question_id: int, candidates: list[dict], expand_context: bool) -> tuple[int, dict]:
    from app.models import Question
    from app.services.ai_classifier import GeminiClassifier
    from app.services.context_expander import expand_candidates

    with app.app_context():
        question = db.session.get(Question, question_id)
        if not question:
            return question_id, {
                "lecture_id": None,
                "confidence": 0.0,
                "reason": "Missing question",
                "study_hint": "",
                "evidence": [],
                "no_match": True,
                "model_name": app.config.get("GEMINI_MODEL_NAME", ""),
            }
        if expand_context:
            candidates = expand_candidates(candidates)
        classifier = GeminiClassifier()
        result = classifier.classify_single(question, candidates)
        return question_id, result


def evaluate(db_path: Path, args) -> dict:
    db_uri = f"sqlite:///{db_path.resolve().as_posix()}"
    app = create_app("default", db_uri_override=db_uri, skip_migration_check=True)

    with app.app_context():
        current_threshold = float(app.config.get("AI_CONFIDENCE_THRESHOLD", 0.7))
        current_margin = float(app.config.get("AI_AUTO_APPLY_MARGIN", 0.2))
        retrieval_mode = args.retrieval_mode or app.config.get("RETRIEVAL_MODE", "bm25")
        labels_query = EvaluationLabel.query.join(Question).order_by(EvaluationLabel.id.asc())
        if args.question_ids_file:
            ids = _load_question_ids(args.question_ids_file)
            if ids:
                labels_query = labels_query.filter(EvaluationLabel.question_id.in_(ids))
        labels = labels_query.all()

        max_k = max(args.top_k) if args.top_k else 10
        evidence_per_lecture = 2

        total = 0
        skipped_no_gold = 0
        skipped_ambiguous = 0
        skipped_only_uncertain = 0

        metrics = {
            "top1": 0,
            "top3": 0,
            "top5": 0,
            "top10": 0,
            "mrr_sum": 0.0,
            "final_correct": 0,
            "final_total": 0,
            "out_of_candidate": 0,
            "out_of_candidate_final": 0,
        }

        auto_current = {"total": 0, "correct": 0}
        auto_sweep = {}
        auto_v2 = {"total": 0, "correct": 0}

        thresholds = args.thresholds or []
        margins = args.margins or []
        for threshold in thresholds:
            for margin in margins:
                auto_sweep[(threshold, margin)] = {"total": 0, "correct": 0}

        misses_top10 = []
        wrong_final = []

        items = []

        for label in labels:
            if label.is_ambiguous and not args.include_ambiguous:
                skipped_ambiguous += 1
                continue
            if not label.gold_lecture_id:
                skipped_no_gold += 1
                continue

            question = label.question
            if not question:
                continue

            question_text = _build_question_text(question)
            artifacts = retrieval_features.build_retrieval_artifacts(
                question_text,
                question.id,
                top_n=80,
                top_k=max_k,
            )

            if retrieval_mode == "hybrid_rrf":
                chunks = artifacts.hybrid_chunks
                candidates = retrieval.aggregate_candidates_rrf(
                    chunks,
                    top_k_lectures=max_k,
                    evidence_per_lecture=evidence_per_lecture,
                )
            else:
                chunks = artifacts.bm25_chunks
                candidates = retrieval.aggregate_candidates(
                    chunks,
                    top_k_lectures=max_k,
                    evidence_per_lecture=evidence_per_lecture,
                )

            candidate_ids = [c.get("id") for c in candidates]
            rank = None
            for idx, cand_id in enumerate(candidate_ids):
                if cand_id == label.gold_lecture_id:
                    rank = idx
                    break

            features = artifacts.features
            auto_confirm = False
            if app.config.get("AUTO_CONFIRM_V2_ENABLED", True):
                auto_confirm = retrieval_features.auto_confirm_v2(
                    features,
                    delta=args.auto_confirm_delta
                    if args.auto_confirm_delta is not None
                    else float(app.config.get("AUTO_CONFIRM_V2_DELTA", 0.05)),
                    max_bm25_rank=args.auto_confirm_bm25_rank
                    if args.auto_confirm_bm25_rank is not None
                    else int(app.config.get("AUTO_CONFIRM_V2_MAX_BM25_RANK", 5)),
                )

            uncertain = retrieval_features.is_uncertain(
                features,
                delta_uncertain=args.delta_uncertain
                if args.delta_uncertain is not None
                else float(app.config.get("AUTO_CONFIRM_V2_DELTA_UNCERTAIN", 0.03)),
                min_chunk_len=args.min_chunk_len
                if args.min_chunk_len is not None
                else int(app.config.get("AUTO_CONFIRM_V2_MIN_CHUNK_LEN", 200)),
                auto_confirm=auto_confirm,
            )

            items.append(
                {
                    "label": label,
                    "question": question,
                    "question_text": question_text,
                    "candidates": candidates,
                    "candidate_ids": candidate_ids,
                    "rank": rank,
                    "auto_confirm": auto_confirm,
                    "uncertain": uncertain,
                    "auto_confirm_lecture_id": features.get("hybrid_top1_lecture_id"),
                }
            )

        if args.only_uncertain:
            filtered = []
            for item in items:
                if not item["uncertain"]:
                    skipped_only_uncertain += 1
                    continue
                filtered.append(item)
            items = filtered

        if args.limit:
            items = items[: args.limit]

        total = len(items)

        model_name = app.config.get("GEMINI_MODEL_NAME", "gemini-1.5-flash-002")
        cache = None
        config_hash = None
        if args.run_classifier and not args.no_cache:
            cache_path = args.cache_path or app.config.get("CLASSIFIER_CACHE_PATH")
            cache = ClassifierResultCache(cache_path)
            config_hash = _classifier_config_hash(app, retrieval_mode, max_k, evidence_per_lecture)

        pending = []
        for item in items:
            if not args.run_classifier:
                question = item["question"]
                item["ai_suggested_lecture_id"] = question.ai_suggested_lecture_id
                item["ai_final_lecture_id"] = question.ai_final_lecture_id or question.lecture_id
                item["ai_confidence"] = question.ai_confidence or 0.0
                item["ai_model_name"] = question.ai_model_name or ""
                continue

            if item["auto_confirm"]:
                item["ai_suggested_lecture_id"] = item["auto_confirm_lecture_id"]
                item["ai_final_lecture_id"] = item["auto_confirm_lecture_id"]
                item["ai_confidence"] = 1.0
                item["ai_model_name"] = "auto_confirm_v2"
                continue

            cached = None
            if cache and config_hash:
                cached = cache.get(item["question"].id, config_hash, model_name)
            if cached:
                result = cached.get("result") or {}
                item["ai_suggested_lecture_id"] = result.get("lecture_id")
                item["ai_final_lecture_id"] = result.get("lecture_id")
                item["ai_confidence"] = float(result.get("confidence") or 0.0)
                item["ai_model_name"] = result.get("model_name") or model_name
                continue

            pending.append(item)

        if args.run_classifier and pending:
            max_workers = max(1, int(args.max_workers))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for item in pending:
                    expand_context = bool(app.config.get("PARENT_ENABLED", False)) and item["uncertain"]
                    candidates = copy.deepcopy(item["candidates"])
                    futures[
                        executor.submit(
                            _classify_worker,
                            app,
                            item["question"].id,
                            candidates,
                            expand_context,
                        )
                    ] = item

                for future in as_completed(futures):
                    item = futures[future]
                    try:
                        question_id, result = future.result()
                    except Exception as exc:
                        question_id = item["question"].id
                        result = {
                            "lecture_id": None,
                            "confidence": 0.0,
                            "reason": f"Error: {exc}",
                            "study_hint": "",
                            "evidence": [],
                            "no_match": True,
                            "model_name": model_name,
                        }
                    item["ai_suggested_lecture_id"] = result.get("lecture_id")
                    item["ai_final_lecture_id"] = result.get("lecture_id")
                    item["ai_confidence"] = float(result.get("confidence") or 0.0)
                    item["ai_model_name"] = result.get("model_name") or model_name

                    if cache and config_hash:
                        cache.set(question_id, config_hash, model_name, result)

        if cache:
            cache.save()

        for item in items:
            label = item["label"]
            candidate_ids = item["candidate_ids"]
            rank = item["rank"]

            for k in args.top_k:
                if rank is not None and rank < k:
                    metrics[f"top{k}"] += 1

            if rank is not None:
                metrics["mrr_sum"] += 1.0 / (rank + 1)

            pred_value = None
            if args.pred_field == "ai_final_lecture_id":
                pred_value = item.get("ai_final_lecture_id")
                if pred_value is None:
                    pred_value = item["question"].lecture_id
            elif args.pred_field == "ai_suggested_lecture_id":
                pred_value = item.get("ai_suggested_lecture_id")
            else:
                pred_value = getattr(item["question"], args.pred_field, None)

            metrics["final_total"] += 1
            if pred_value == label.gold_lecture_id:
                metrics["final_correct"] += 1

            raw_pred = item.get("ai_suggested_lecture_id")
            if raw_pred and raw_pred not in candidate_ids:
                metrics["out_of_candidate"] += 1
            if pred_value and pred_value not in candidate_ids:
                metrics["out_of_candidate_final"] += 1

            ai_conf = item.get("ai_confidence") or 0.0
            auto_threshold = current_threshold + current_margin
            if (
                raw_pred
                and raw_pred in candidate_ids
                and ai_conf >= auto_threshold
            ):
                auto_current["total"] += 1
                if raw_pred == label.gold_lecture_id:
                    auto_current["correct"] += 1

            for threshold in thresholds:
                for margin in margins:
                    gate = threshold + margin
                    if (
                        raw_pred
                        and raw_pred in candidate_ids
                        and ai_conf >= gate
                    ):
                        auto_sweep[(threshold, margin)]["total"] += 1
                        if raw_pred == label.gold_lecture_id:
                            auto_sweep[(threshold, margin)]["correct"] += 1

            if item["auto_confirm"] and item["auto_confirm_lecture_id"]:
                auto_v2["total"] += 1
                if item["auto_confirm_lecture_id"] == label.gold_lecture_id:
                    auto_v2["correct"] += 1

            if rank is None and len(misses_top10) < args.max_failures:
                misses_top10.append(
                    {
                        "question_id": item["question"].id,
                        "gold_lecture_id": label.gold_lecture_id,
                        "predicted_lecture_id": pred_value,
                        "top_candidates": _candidate_payload(item["candidates"]),
                    }
                )
            if rank is not None and pred_value != label.gold_lecture_id and len(wrong_final) < args.max_failures:
                wrong_final.append(
                    {
                        "question_id": item["question"].id,
                        "gold_lecture_id": label.gold_lecture_id,
                        "predicted_lecture_id": pred_value,
                        "top_candidates": _candidate_payload(item["candidates"]),
                    }
                )

        results = {
            "total": total,
            "skipped_no_gold": skipped_no_gold,
            "skipped_ambiguous": skipped_ambiguous,
            "skipped_only_uncertain": skipped_only_uncertain,
            "metrics": metrics,
            "auto_current": auto_current,
            "auto_sweep": auto_sweep,
            "auto_v2": auto_v2,
            "misses_top10": misses_top10,
            "wrong_final": wrong_final,
            "retrieval_mode": retrieval_mode,
        }
        return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate eval labels.")
    parser.add_argument("--db", default="data/dev.db", help="SQLite db path.")
    parser.add_argument(
        "--pred-field",
        default="ai_final_lecture_id",
        help="Question field to use as prediction.",
    )
    parser.add_argument("--top-k", default="1,3,5,10", help="Comma-separated top-k values.")
    parser.add_argument(
        "--retrieval-mode",
        default=None,
        help="bm25 or hybrid_rrf (default: use config).",
    )
    parser.add_argument("--include-ambiguous", action="store_true", help="Include ambiguous labels.")
    parser.add_argument("--max-failures", type=int, default=15, help="Max failures per report.")
    parser.add_argument("--thresholds", default="0.6,0.7,0.8", help="Threshold sweep list.")
    parser.add_argument("--margins", default="0.0,0.1,0.2", help="Margin sweep list.")
    parser.add_argument("--question-ids-file", default=None, help="Restrict eval to question ids.")

    # Live classification options
    parser.add_argument("--run-classifier", action="store_true", help="Run live classification.")
    parser.add_argument("--max-workers", type=int, default=4, help="Max concurrent classifier workers.")
    parser.add_argument("--no-cache", action="store_true", help="Disable classifier cache.")
    parser.add_argument("--cache-path", default=None, help="Override classifier cache path.")
    parser.add_argument("--only-uncertain", action="store_true", help="Evaluate only uncertain items.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of eval items.")

    # Auto-confirm v2 overrides
    parser.add_argument("--auto-confirm-delta", type=float, default=None, help="Override auto-confirm delta.")
    parser.add_argument(
        "--auto-confirm-bm25-rank",
        type=int,
        default=None,
        help="Override auto-confirm bm25 rank limit.",
    )
    parser.add_argument("--delta-uncertain", type=float, default=None, help="Override uncertain delta.")
    parser.add_argument("--min-chunk-len", type=int, default=None, help="Override min chunk length.")

    args = parser.parse_args()

    args.top_k = [int(v) for v in _parse_list(args.top_k, int) if int(v) > 0]
    args.thresholds = _parse_list(args.thresholds, float)
    args.margins = _parse_list(args.margins, float)

    db_path = Path(args.db)
    if not db_path.exists():
        raise FileNotFoundError(f"DB not found: {db_path}")

    result = evaluate(db_path, args)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_dir = ROOT_DIR / "reports" / f"eval_{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)

    out_rate = (
        result["metrics"]["out_of_candidate"] / result["metrics"]["final_total"]
        if result["metrics"]["final_total"]
        else 0.0
    )
    out_rate_final = (
        result["metrics"]["out_of_candidate_final"] / result["metrics"]["final_total"]
        if result["metrics"]["final_total"]
        else 0.0
    )
    summary = {
        "generated_at": timestamp,
        "db": db_path.as_posix(),
        "pred_field": args.pred_field,
        "retrieval_mode": result["retrieval_mode"],
        "total": result["total"],
        "skipped_no_gold": result["skipped_no_gold"],
        "skipped_ambiguous": result["skipped_ambiguous"],
        "skipped_only_uncertain": result["skipped_only_uncertain"],
        "metrics": result["metrics"],
        "out_of_candidate_rate_raw": out_rate,
        "out_of_candidate_rate_final": out_rate_final,
        "auto_current": result["auto_current"],
        "auto_v2": result["auto_v2"],
        "auto_sweep": {f"{k[0]}+{k[1]}": v for k, v in result["auto_sweep"].items()},
    }

    (report_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    misses = result["misses_top10"]
    wrongs = result["wrong_final"]

    _write_markdown(report_dir / "top10_miss.md", "Top-10 Misses", misses)
    _write_markdown(report_dir / "top10_wrong_final.md", "Top-10 Contains Gold but Wrong Final", wrongs)

    csv_fields = ["question_id", "gold_lecture_id", "predicted_lecture_id", "top_candidates"]
    _write_csv(
        report_dir / "top10_miss.csv",
        [
            {
                "question_id": row["question_id"],
                "gold_lecture_id": row["gold_lecture_id"],
                "predicted_lecture_id": row["predicted_lecture_id"],
                "top_candidates": json.dumps(row["top_candidates"], ensure_ascii=False),
            }
            for row in misses
        ],
        csv_fields,
    )
    _write_csv(
        report_dir / "top10_wrong_final.csv",
        [
            {
                "question_id": row["question_id"],
                "gold_lecture_id": row["gold_lecture_id"],
                "predicted_lecture_id": row["predicted_lecture_id"],
                "top_candidates": json.dumps(row["top_candidates"], ensure_ascii=False),
            }
            for row in wrongs
        ],
        csv_fields,
    )

    print(f"Report dir: {report_dir}")


if __name__ == "__main__":
    main()
