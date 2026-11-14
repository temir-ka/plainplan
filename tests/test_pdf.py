from pathlib import Path

import pytest

from app.services.pdf import (
    MASK, ScannedPdfError, chunk_pages, mask_identifiers, read_policy_pdf,
)

SAMPLES = Path("samples")
AUTO = Path("tests/fixtures/fictional_auto_policy.pdf")
HOME = SAMPLES / "homeowners-3-special-form.pdf"
HEALTH = SAMPLES / "cms_sample_sbc_2025.pdf"


def test_mask_vin_policy_and_license_numbers():
    text = "VIN 1HGCV1F58NA042819, policy PAP-8492031-04, license OH-RM482910"
    masked = mask_identifiers(text)
    assert "1HGCV1F58NA042819" not in masked and f"{MASK}2819" in masked
    assert "8492031" not in masked and f"{MASK}3104" in masked
    assert "482910" not in masked and f"{MASK}2910" in masked


def test_mask_keeps_money_phones_dates_and_form_numbers():
    text = ("$100,000 Each Person / $300,000 Each Accident. Claims 24/7: (800) 555-0199, "
            "1-800-555-0100. Period 01/15/2026 to 07/15/2026. Form PP 00 01 06 98. ZIP 43215-2841.")
    assert mask_identifiers(text) == text


def test_chunks_keep_page_numbers_and_headings():
    pages = ["SECTION I - PROPERTY\nWe cover the dwelling.", "DUTIES AFTER LOSS\nNotify us promptly."]
    chunks = chunk_pages(pages)
    assert [(c.page, c.section) for c in chunks] == [(1, "SECTION I - PROPERTY"), (2, "DUTIES AFTER LOSS")]


def test_long_page_is_split_with_one_line_overlap():
    lines = [f"Line {i} " + "x" * 90 for i in range(20)]
    chunks = chunk_pages(["\n".join(lines)], max_chars=300)
    assert len(chunks) > 1
    assert all(len(c.text) <= 300 + 100 for c in chunks)
    for a, b in zip(chunks, chunks[1:]):
        assert a.text.splitlines()[-1] == b.text.splitlines()[0]
    assert all(c.page == 1 for c in chunks)


@pytest.mark.skipif(not AUTO.exists(), reason="sample PDF not present")
def test_real_auto_policy_is_masked_and_chunked():
    chunks = read_policy_pdf(AUTO)
    text = "\n".join(c.text for c in chunks)
    assert "1HGCV1F58NA042819" not in text  # VIN
    assert "PAP-8492031-04" not in text  # policy number
    assert "(800) 555-0199" in text  # claims phone survives
    duties = [c for c in chunks if "notified promptly" in c.text]
    assert duties and duties[0].page == 3


@pytest.mark.skipif(not HOME.exists(), reason="sample PDF not present")
def test_real_home_policy_keeps_the_60_day_deadline():
    chunks = read_policy_pdf(HOME)
    assert {c.page for c in chunks} == set(range(1, 22))
    assert any("within 60 days after our request" in " ".join(c.text.split()) for c in chunks)


@pytest.mark.skipif(not HEALTH.exists(), reason="sample PDF not present")
def test_real_health_sbc_has_its_deductible():
    chunks = read_policy_pdf(HEALTH)
    assert any("overall deductible" in c.text.lower() and "$500" in c.text for c in chunks)


def test_scanned_pdf_is_refused(tmp_path):
    import pypdfium2  # installed together with pdfplumber

    path = tmp_path / "blank.pdf"  # a page with no text layer, like a scan
    doc = pypdfium2.PdfDocument.new()
    doc.new_page(612, 792)
    doc.save(path)
    with pytest.raises(ScannedPdfError):
        read_policy_pdf(path)


AAA = SAMPLES / "aaa_alabama_personal_auto_policy_sample.pdf"


@pytest.mark.skipif(not AAA.exists(), reason="sample PDF not present")
def test_sample_watermark_letters_are_dropped():
    chunks = read_policy_pdf(AAA)
    text = "\n".join(c.text for c in chunks)
    assert "household" in text and "houPsehold" not in text
    duties = [c for c in chunks if "we must be notified promptly" in c.text]
    assert duties and duties[0].page == 47
