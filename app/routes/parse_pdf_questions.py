#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path
from typing import Any

import pdfplumber
import pandas as pd


from app.services.pdf_parser import (
    clean_text,
    detect_answer_color,
    color_distance,
    extract_events,
    match_option_line,
    normalize_embedded_option,
)


def save_image_crop(page, bbox, media_dir: Path, resolution=200) -> str:
    import hashlib
    from io import BytesIO

    cropped = page.crop(bbox)
    page_image = cropped.to_image(resolution=resolution)

    buf = BytesIO()
    page_image.original.save(buf, format="PNG")
    data = buf.getvalue()

    h = hashlib.sha1(data).hexdigest()[:16]
    fname = f"{h}.png"
    out_path = media_dir / fname
    if not out_path.exists():
        out_path.write_bytes(data)
    return fname


def append_image(text: str, image_path: str | None, media_ref_prefix: str) -> str:
    if not image_path:
        return text
    tag = f"![]({media_ref_prefix}{image_path})"
    if text:
        return f"{text} {tag}"
    return tag


def parse_events(
    events, media_dir: Path, media_ref_prefix="media/", max_option_number=16
) -> pd.DataFrame:
    from app.services.pdf_parser import (
        ANSWER_LABEL_RE,
        INDENT_TOL,
        Q_HEADER,
    )

    questions = []
    cur = None
    cur_opt = None

    for ev in events:
        if ev["type"] == "text":
            normalized_lines = normalize_embedded_option(
                ev["text"], cur, max_option_number
            )
            for txt in normalized_lines:
                m_q = Q_HEADER.match(txt)
                if m_q:
                    if cur:
                        opt_match = match_option_line(txt, max_option_number)
                        if opt_match:
                            opt_num, _, opt_text = opt_match
                            qx0 = cur.get("question_x0")
                            ox0 = cur.get("option_x0")
                            indented = qx0 is not None and ev["x0"] > qx0 + INDENT_TOL
                            aligned_to_option = (
                                ox0 is not None and abs(ev["x0"] - ox0) <= INDENT_TOL
                            )
                            if indented or (
                                ox0 is not None
                                and qx0 is not None
                                and (ox0 - qx0) > INDENT_TOL
                                and aligned_to_option
                            ):
                                option = cur["options_map"].setdefault(
                                    opt_num,
                                    {
                                        "number": opt_num,
                                        "content": "",
                                        "image_path": None,
                                        "is_correct": False,
                                    },
                                )
                                if cur.get("option_x0") is None:
                                    cur["option_x0"] = ev["x0"]
                                cur_opt = opt_num
                                if opt_text:
                                    option["content"] = (
                                        option["content"] + " " + opt_text
                                    ).strip()
                                option["is_correct"] = (
                                    option["is_correct"] or ev["has_key"]
                                )
                                continue
                        questions.append(cur)
                    cur = {
                        "ID": m_q.group(1),
                        "Question": m_q.group(2).strip(),
                        "image_path": None,
                        "options_map": {},
                        "answer_lines": [],
                        "question_x0": ev["x0"],
                        "option_x0": None,
                    }
                    cur_opt = None
                    continue

                opt_match = match_option_line(txt, max_option_number)
                if opt_match and cur:
                    opt_num, _, opt_text = opt_match
                    option = cur["options_map"].setdefault(
                        opt_num,
                        {
                            "number": opt_num,
                            "content": "",
                            "image_path": None,
                            "is_correct": False,
                        },
                    )
                    if cur.get("option_x0") is None:
                        cur["option_x0"] = ev["x0"]
                    cur_opt = opt_num
                    if opt_text:
                        option["content"] = (option["content"] + " " + opt_text).strip()
                    option["is_correct"] = option["is_correct"] or ev["has_key"]
                    continue

                if not cur:
                    continue

                if cur_opt is None and not cur["options_map"]:
                    label_match = ANSWER_LABEL_RE.match(txt)
                    if label_match:
                        label_text = label_match.group(1).strip()
                        if label_text:
                            cur["answer_lines"].append(label_text)
                        continue
                    if ev["has_key"]:
                        cur["answer_lines"].append(txt)
                        continue

                if cur_opt is not None:
                    option = cur["options_map"].setdefault(
                        cur_opt,
                        {
                            "number": cur_opt,
                            "content": "",
                            "image_path": None,
                            "is_correct": False,
                        },
                    )
                    option["content"] = (option["content"] + " " + txt).strip()
                    option["is_correct"] = option["is_correct"] or ev["has_key"]
                else:
                    cur["Question"] = (cur["Question"] + " " + txt).strip()

        else:
            if not cur:
                continue

            page = ev["page_obj"]
            bbox = (ev["x0"], ev["top"], ev["x1"], ev["bottom"])
            fname = save_image_crop(page, bbox, media_dir)

            if cur_opt is not None:
                option = cur["options_map"].setdefault(
                    cur_opt,
                    {
                        "number": cur_opt,
                        "content": "",
                        "image_path": None,
                        "is_correct": False,
                    },
                )
                if not option["image_path"]:
                    option["image_path"] = fname
            else:
                if not cur["image_path"]:
                    cur["image_path"] = fname

    if cur:
        questions.append(cur)

    rows = []
    for q in questions:
        options = [q["options_map"][n] for n in sorted(q["options_map"])]
        answer_options = [opt["number"] for opt in options if opt["is_correct"]]

        question_text = append_image(
            q.get("Question", ""), q.get("image_path"), media_ref_prefix
        )

        row = {
            "ID": q.get("ID"),
            "Question": question_text.strip(),
            "AnswerOption": ",".join(str(n) for n in answer_options),
        }

        if options:
            answer_text = " | ".join(
                opt["content"]
                for opt in options
                if opt["is_correct"] and opt["content"]
            )
        else:
            answer_text = " ".join(q["answer_lines"]).strip()
        row["AnswerText"] = answer_text

        options_by_num = {opt["number"]: opt for opt in options}
        for i in range(1, max_option_number + 1):
            opt = options_by_num.get(i)
            if opt:
                opt_text = append_image(
                    opt.get("content", ""), opt.get("image_path"), media_ref_prefix
                )
                row[f"Option {i}"] = opt_text.strip()
            else:
                row[f"Option {i}"] = ""

        rows.append(row)

    return pd.DataFrame(rows)


def pdf_to_csv(pdf_path: str, output_csv: str | None = None, max_option_number=16):
    pdf_path = Path(pdf_path)

    if output_csv is None:
        output_csv = str(pdf_path.with_suffix(".csv"))
    else:
        output_csv = str(Path(output_csv))

    out_dir = Path(output_csv).resolve().parent
    media_root = out_dir / "media"
    media_root.mkdir(parents=True, exist_ok=True)
    media_subdir = media_root / pdf_path.stem
    media_subdir.mkdir(parents=True, exist_ok=True)

    with pdfplumber.open(str(pdf_path)) as pdf:
        answer_color = detect_answer_color(pdf)
        events = extract_events(pdf, answer_color)
        media_prefix = f"media/{pdf_path.stem}/"
        df = parse_events(
            events,
            media_subdir,
            media_ref_prefix=media_prefix,
            max_option_number=max_option_number,
        )

    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"변환 완료: {output_csv} ({len(df)}문항)")
    print(f"📁 이미지 폴더: {media_subdir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python parse_pdf_questions.py input.pdf [output.csv]")
        sys.exit(1)

    in_pdf = sys.argv[1]
    out_csv = sys.argv[2] if len(sys.argv) >= 3 else None
    pdf_to_csv(in_pdf, out_csv)
