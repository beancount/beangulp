#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["beangulp[pdf]"]
# [tool.uv.sources]
# beangulp = { path = "..", editable = true }
# ///
"""Classify PDF pages by raster image coverage and extractable text.

Run with: uv run tools/classify_pdf.py document.pdf [other.pdf ...]

This is a structural heuristic, not proof of scanner provenance. Full-page
photographs and rasterized digital documents also look like scans. Text on an
image-dominated page may be OCR or native text; its presence does not establish
OCR quality. Blank and vector-only pages are reported as unknown.

Uses the classifier provided by beangulp.pdf.
"""

import argparse
import json
import sys

from beangulp.pdf import classify_pdf



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+")
    parser.add_argument("--image-threshold", type=float, default=0.8,
                        help="Minimum page image coverage (default: 0.8)")
    parser.add_argument("--min-text-chars", type=int, default=20,
                        help="Minimum alphanumeric text characters (default: 20)")
    args = parser.parse_args()
    if not 0 < args.image_threshold <= 1:
        parser.error("--image-threshold must be greater than 0 and at most 1")
    if args.min_text_chars < 1:
        parser.error("--min-text-chars must be positive")
    failed = False
    for filename in args.files:
        try:
            result = classify_pdf(filename, args.image_threshold, args.min_text_chars)
        except (RuntimeError, ValueError, OSError) as exc:
            result = {"file": filename, "error": str(exc)}
            failed = True
        print(json.dumps(result, indent=2))
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
