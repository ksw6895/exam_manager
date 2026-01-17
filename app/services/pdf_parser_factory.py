#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF Parser Factory
Centralized parser selection based on PDF_PARSER_MODE configuration.

This module provides a single entry point for selecting and using PDF parsers,
ensuring that parser mode selection logic is in one place only.
"""

from typing import Any, Callable
from pathlib import Path


def get_pdf_parser(mode: str = "legacy") -> Callable[..., Any]:
    """
    Get the PDF parser function based on the specified mode.

    Args:
        mode: Parser mode ("legacy" or "experimental"). Defaults to "legacy".

    Returns:
        Parser function with signature: parse_pdf_to_questions(pdf_path, upload_dir, exam_prefix, max_option_number=16)

    Raises:
        ValueError: If an invalid parser mode is specified.
    """
    if mode == "experimental":
        from app.services.pdf_parser_experimental import parse_pdf_to_questions
    elif mode == "legacy":
        from app.services.pdf_parser import parse_pdf_to_questions
    else:
        raise ValueError(
            f"Invalid PDF parser mode: {mode}. Must be 'legacy' or 'experimental'."
        )

    return parse_pdf_to_questions


def parse_pdf(
    pdf_path: str | Path,
    upload_dir: str | Path,
    exam_prefix: str,
    mode: str = "legacy",
    max_option_number: int = 16,
) -> list[dict]:
    """
    Parse PDF to questions using the specified parser mode.

    This is the main entry point for PDF parsing. It handles parser selection
    and delegates to the appropriate parser implementation.

    Args:
        pdf_path: Path to the PDF file.
        upload_dir: Directory for storing cropped images.
        exam_prefix: Prefix for image filenames.
        mode: Parser mode ("legacy" or "experimental"). Defaults to "legacy".
        max_option_number: Maximum number of options to parse. Defaults to 16.

    Returns:
        List of parsed question dictionaries.

    Raises:
        ValueError: If an invalid parser mode is specified.
    """
    parser = get_pdf_parser(mode)
    return parser(pdf_path, upload_dir, exam_prefix, max_option_number)


__all__ = ["get_pdf_parser", "parse_pdf"]
