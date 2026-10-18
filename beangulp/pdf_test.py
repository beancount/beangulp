"""Exercise classification with generated PDFs, without private documents."""

import pytest

pymupdf = pytest.importorskip("pymupdf")

pdf = pytest.importorskip("beangulp.pdf")


@pytest.fixture
def document():
    with pymupdf.open() as doc:
        yield doc


@pytest.fixture
def image():
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), False)
    pixmap.clear_with(255)
    return pixmap.tobytes("png")


def save_and_classify(document, tmp_path, **kwargs):
    filename = tmp_path / "input.pdf"
    document.save(filename)
    return pdf.classify_pdf(filename, **kwargs)


def add_scan(document, image):
    page = document.new_page(width=200, height=300)
    page.insert_image(page.rect, stream=image, keep_proportion=False)
    return page


def test_scan(document, image, tmp_path):
    add_scan(document, image)
    add_scan(document, image)
    result = save_and_classify(document, tmp_path)
    assert result["classification"] == "scanned"
    assert result["has_scanned_pages"] is True
    assert result["ocr_candidate_pages"] == [1, 2]
    assert result["pages"][0] == {
        "page": 1, "classification": "scan_without_text",
        "image_coverage": 1.0, "text_chars": 0,
    }


def test_ocr_rotated_crop(document, image, tmp_path):
    page = add_scan(document, image)
    page.insert_text((20, 40), "Searchable OCR text for testing", render_mode=3)
    page.set_cropbox(pymupdf.Rect(10, 20, 190, 280))
    page.set_rotation(90)
    result = save_and_classify(document, tmp_path)
    assert result["classification"] == "scanned"
    assert result["pages"][0]["classification"] == "scan_with_text"
    assert result["pages"][0]["image_coverage"] == 1.0
    assert result["ocr_candidate_pages"] == []


def test_digital_with_logo(document, image, tmp_path):
    page = document.new_page()
    page.insert_text((30, 30), "Native digital text for testing detection")
    page.insert_image(pymupdf.Rect(30, 50, 80, 100), stream=image)
    result = save_and_classify(document, tmp_path)
    assert result["classification"] == "digital"
    assert result["has_scanned_pages"] is False
    assert result["ocr_candidate_pages"] == []


def test_mixed(document, image, tmp_path):
    add_scan(document, image)
    page = document.new_page()
    page.insert_text((30, 30), "Native digital text for testing detection")
    result = save_and_classify(document, tmp_path)
    assert result["classification"] == "mixed"
    assert result["has_scanned_pages"] is True
    assert result["ocr_candidate_pages"] == [1]


@pytest.mark.parametrize("draw", [False, True])
def test_unknown(document, tmp_path, draw):
    page = document.new_page()
    if draw:
        page.draw_rect(pymupdf.Rect(10, 10, 100, 100))
    result = save_and_classify(document, tmp_path)
    assert result["classification"] == "unknown"
    assert result["has_scanned_pages"] is False


def test_tiled_images(document, image, tmp_path):
    page = document.new_page(width=200, height=300)
    for rect in [(0, 0, 200, 150), (0, 150, 200, 300)]:
        page.insert_image(pymupdf.Rect(rect), stream=image, keep_proportion=False)
    assert save_and_classify(document, tmp_path)["classification"] == "scanned"


def test_overlapping_images(document, image, tmp_path):
    page = document.new_page(width=200, height=300)
    for _ in range(2):
        page.insert_image(pymupdf.Rect(0, 0, 200, 150), stream=image,
                          keep_proportion=False)
    result = save_and_classify(document, tmp_path)
    assert result["pages"][0]["image_coverage"] == 0.5
    assert result["has_scanned_pages"] is False


def test_custom_thresholds(document, image, tmp_path):
    page = document.new_page(width=200, height=300)
    page.insert_image(pymupdf.Rect(0, 0, 200, 150), stream=image,
                      keep_proportion=False)
    page.insert_text((20, 200), "Hi")
    result = save_and_classify(document, tmp_path, image_threshold=0.5, min_text_chars=2)
    assert result["pages"][0]["classification"] == "scan_with_text"


@pytest.mark.parametrize("kwargs", [
    {"image_threshold": 0}, {"image_threshold": 1.1},
    {"image_threshold": float("nan")}, {"min_text_chars": 0},
    {"min_text_chars": 1.5},
])
def test_invalid_thresholds(kwargs):
    with pytest.raises(ValueError):
        pdf.classify_pdf("unused.pdf", **kwargs)


def test_password(document, tmp_path):
    document.new_page()
    filename = tmp_path / "encrypted.pdf"
    document.save(filename, encryption=pymupdf.PDF_ENCRYPT_AES_256,
                  owner_pw="owner", user_pw="reader")
    with pytest.raises(ValueError, match="password"):
        pdf.classify_pdf(filename)


def test_non_pdf(image, tmp_path):
    filename = tmp_path / "image.png"
    filename.write_bytes(image)
    with pytest.raises(ValueError, match="not a PDF"):
        pdf.classify_pdf(filename)


def test_missing(tmp_path):
    with pytest.raises(pymupdf.FileNotFoundError):
        pdf.classify_pdf(tmp_path / "missing.pdf")


def test_malformed(tmp_path):
    filename = tmp_path / "broken.pdf"
    filename.write_bytes(b"%PDF-1.4\ninvalid")
    with pytest.raises(pymupdf.FileDataError):
        pdf.classify_pdf(filename)
