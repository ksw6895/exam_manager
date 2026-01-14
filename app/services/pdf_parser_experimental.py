#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Experimental PDF parser entrypoint.
Currently delegates to the legacy parser to keep behavior identical.
"""

from app.services.pdf_parser import parse_pdf_to_questions

__all__ = ["parse_pdf_to_questions"]
