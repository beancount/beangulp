"""Detect scan-like PDFs using image coverage and extractable text.

Install ``beangulp[pdf]`` to use this module (Python 3.9 or later).
Full-page photographs and rasterized digital documents can also look like scans.
A text layer on a scan-like page may be OCR or native text; this module does not
assess OCR quality. Blank and vector-only pages are classified as unknown.
"""

__copyright__ = "Copyright (C) 2026  Martin Blais"
__license__ = "GNU GPLv2"

import pymupdf


def _union_area(rectangles):
    """Compute rectangle union area without double-counting overlaps."""
    edges = sorted({x for rect in rectangles for x in (rect.x0, rect.x1)})
    area = 0.0
    for left, right in zip(edges, edges[1:]):
        intervals = sorted(
            (rect.y0, rect.y1)
            for rect in rectangles
            if rect.x0 < right and rect.x1 > left
        )
        height = 0.0
        end = float("-inf")
        for bottom, top in intervals:
            height += max(0.0, top - max(bottom, end))
            end = max(end, top)
        area += (right - left) * height
    return area


def classify_pdf(filename, image_threshold=0.8, min_text_chars=20):
    """Return JSON-compatible document and page classifications.

    ``has_scanned_pages`` is suitable for routing a document to a scan importer.
    ``ocr_candidate_pages`` lists scan-like pages with little extractable text.
    ``filename`` is a filesystem path (string or pathlib.Path). Each page
    contains ``page`` (one-based), ``classification`` (scan_with_text,
    scan_without_text, digital, or unknown), ``image_coverage`` (0 to 1), and
    ``text_chars`` (alphanumeric characters). Document classifications are
    scanned, mixed, digital, or unknown; mixed means at least one scan-like
    page and at least one other page.

    Invalid thresholds, encrypted PDFs requiring a password, non-PDF inputs,
    and empty documents raise ValueError. File access and parsing errors
    propagate from PyMuPDF.
    """
    if not 0 < image_threshold <= 1:
        raise ValueError("image_threshold must be greater than 0 and at most 1")
    if not isinstance(min_text_chars, int) or min_text_chars < 1:
        raise ValueError("min_text_chars must be a positive integer")
    pages = []
    with pymupdf.open(filename) as document:
        if not document.is_pdf:
            raise ValueError("Input is not a PDF")
        if document.needs_pass:
            raise ValueError("PDF requires a password")
        if not document.page_count:
            raise ValueError("PDF has no pages")
        for page in document:
            # Image bboxes use unrotated coordinates, unlike page.rect.
            bounds = pymupdf.Rect(0, 0, page.cropbox.width, page.cropbox.height)
            rectangles = []
            for info in page.get_image_info():
                rect = pymupdf.Rect(info["bbox"]) & bounds
                if not rect.is_empty and not rect.is_infinite:
                    rectangles.append(rect)
            coverage = _union_area(rectangles) / bounds.get_area() if bounds else 0.0
            text_chars = sum(char.isalnum() for char in page.get_text())
            has_text = text_chars >= min_text_chars
            if coverage >= image_threshold:
                classification = "scan_with_text" if has_text else "scan_without_text"
            elif has_text:
                classification = "digital"
            else:
                classification = "unknown"
            pages.append({
                "page": page.number + 1,
                "classification": classification,
                "image_coverage": round(coverage, 4),
                "text_chars": text_chars,
            })

    scanned = [page for page in pages if page["classification"].startswith("scan_")]
    if len(scanned) == len(pages):
        classification = "scanned"
    elif scanned:
        classification = "mixed"
    elif all(page["classification"] == "digital" for page in pages):
        classification = "digital"
    else:
        classification = "unknown"
    return {
        "file": str(filename),
        "classification": classification,
        "has_scanned_pages": bool(scanned),
        "ocr_candidate_pages": [
            page["page"] for page in pages
            if page["classification"] == "scan_without_text"
        ],
        "pages": pages,
    }
