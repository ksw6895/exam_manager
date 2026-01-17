"""
Grid search auto-confirm v2 thresholds on evalset without LLM calls.

Usage:
  python scripts/tune_autoconfirm_v2.py --db data/dev.db --precision-target 0.86
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")

from app import create_app
from app.models import EvaluationLabel, Question
from app.services import retrieval_features


def _parse_grid(raw: str) -> list[float]:
    raw = (raw or "").strip()
    if not raw:
        return []
    if ":" in raw:
        parts = raw.split(":")
        if len(parts) != 3:
            return []
        start, stop, step = parts
        try:
            start_f = float(start)
            stop_f = float(stop)
            step_f = float(step)
        except ValueError:
            return []
        values = []
        v = start_f
        while v <= stop_f + 1e-9:
            values.append(round(v, 6))
            v += step_f
        return values
    values = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.append(float(item))
        except ValueError:
            continue
    return values


def _parse_int_grid(raw: str) -> list[int]:
    raw = (raw or "").strip()
    if not raw:
        return []
    if ":" in raw:
        parts = raw.split(":")
        if len(parts) != 3:
            return []
        start, stop, step = parts
        try:
            start_i = int(start)
            stop_i = int(stop)
            step_i = int(step)
        except ValueError:
            return []
        return list(range(start_i, stop_i + 1, step_i))
    values = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.append(int(item))
        except ValueError:
            continue
    return values


def _build_question_text(question: Question) -> str:
    choices = [c.content for c in question.choices.order_by("choice_number").all()]
    question_text = question.content or ""
    if choices:
        question_text = f"{question_text}\n" + " ".join(choices)
    return question_text.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune auto-confirm v2 thresholds.")
    parser.add_argument("--db", default="data/dev.db", help="SQLite db path.")
    parser.add_argument("--precision-target", type=float, default=0.86, help="Minimum precision.")
    parser.add_argument("--delta-grid", default="0.0:0.2:0.01", help="Delta grid (list or start:stop:step).")
    parser.add_argument(
        "--bm25-rank-grid",
        default="1:10:1",
        help="BM25 rank grid (list or start:stop:step).",
    )
    parser.add_argument("--out", default="reports/autoconfirm_v2_tuning.md", help="Markdown output path.")
    parser.add_argument("--include-ambiguous", action="store_true", help="Include ambiguous labels.")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise FileNotFoundError(f"DB not found: {db_path}")

    deltas = _parse_grid(args.delta_grid)
    ranks = _parse_int_grid(args.bm25_rank_grid)
    if not deltas or not ranks:
        raise ValueError("Invalid grids for delta or bm25 rank.")

    app = create_app("default", db_uri_override=f"sqlite:///{db_path.resolve().as_posix()}")

    rows = []
    total_eval = 0
    with app.app_context():
        labels = EvaluationLabel.query.join(Question).order_by(EvaluationLabel.id.asc()).all()
        items = []
        for label in labels:
            if label.is_ambiguous and not args.include_ambiguous:
                continue
            if not label.gold_lecture_id:
                continue
            question = label.question
            if not question:
                continue
            question_text = _build_question_text(question)
            artifacts = retrieval_features.build_retrieval_artifacts(
                question_text,
                question.id,
                top_n=80,
                top_k=5,
            )
            items.append(
                {
                    "gold_lecture_id": label.gold_lecture_id,
                    "features": artifacts.features,
                }
            )

        total_eval = len(items)
        for delta in deltas:
            for max_rank in ranks:
                auto_total = 0
                auto_correct = 0
                for item in items:
                    features = item["features"]
                    auto = retrieval_features.auto_confirm_v2(
                        features, delta=delta, max_bm25_rank=max_rank
                    )
                    if not auto:
                        continue
                    auto_total += 1
                    if features.get("hybrid_top1_lecture_id") == item["gold_lecture_id"]:
                        auto_correct += 1
                precision = auto_correct / auto_total if auto_total else 0.0
                coverage = auto_total / total if total else 0.0
                rows.append(
                    {
                        "delta": delta,
                        "max_bm25_rank": max_rank,
                        "auto_total": auto_total,
                        "auto_correct": auto_correct,
                        "precision": precision,
                        "coverage": coverage,
                    }
                )

    viable = [r for r in rows if r["precision"] >= args.precision_target]
    viable.sort(key=lambda r: (r["coverage"], r["precision"]), reverse=True)
    best = viable[0] if viable else None

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# Auto-confirm v2 tuning report",
        "",
        f"- generated_at: {timestamp} UTC",
        f"- db: {db_path.as_posix()}",
        f"- total_eval: {total_eval}",
    ]
    lines.append(f"- precision_target: {args.precision_target}")
    if best:
        lines.append(
            f"- selected: delta={best['delta']}, max_bm25_rank={best['max_bm25_rank']}, "
            f"precision={best['precision']:.3f}, coverage={best['coverage']:.3f}"
        )
    else:
        lines.append("- selected: none (no config met target)")
    lines.append("")
    lines.append("## Precision/Coverage Tradeoff")
    lines.append("")
    lines.append("| delta | max_bm25_rank | auto_total | precision | coverage |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in sorted(rows, key=lambda r: (r["coverage"], r["precision"]), reverse=True)[:30]:
        lines.append(
            f"| {row['delta']:.3f} | {row['max_bm25_rank']} | {row['auto_total']} | "
            f"{row['precision']:.3f} | {row['coverage']:.3f} |"
        )

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote report to {out_path}")


if __name__ == "__main__":
    main()
