"""PDF -> masked text chunks with page numbers (pdfplumber).

1. Extract text page by page. Almost no text -> it's a scan, we refuse it.
2. Mask VINs and long ID numbers (policy, driver license) to the last 4 characters BEFORE storing.
3. Split each page into ~800-char chunks on line boundaries, overlapping by one line so a quote
   that sits on a boundary is still inside one chunk. Each chunk keeps its page and nearest heading.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

MAX_CHUNK_CHARS = 800
MIN_TEXT_CHARS_PER_PAGE = 40
MASK = "••••"

# 17 chars, no I/O/Q, at least one digit and one letter.
_VIN = re.compile(r"\b(?=[A-HJ-NPR-Z0-9]*\d)(?=[A-HJ-NPR-Z0-9]*[A-HJ-NPR-Z])[A-HJ-NPR-Z0-9]{17}\b")
# Policy / license / member numbers: an uppercase-alphanumeric token (dashes allowed) with 6+ digits in a row.
# Money ("$100,000") and phones ("(800) 555-0199") never have 6 digits in a row, so they survive.
_LONG_ID = re.compile(r"\b(?=[A-Z0-9-]*\d{6})[A-Z0-9][A-Z0-9-]{4,}[A-Z0-9]\b")


class ScannedPdfError(ValueError):
    """The PDF has no extractable text (probably a scan or a photo)."""


@dataclass
class PageChunk:
    page: int  # 1-based
    section: str
    text: str


def _last4(token: str) -> str:
    return MASK + re.sub(r"[^A-Za-z0-9]", "", token)[-4:]


def mask_identifiers(text: str) -> str:
    text = _VIN.sub(lambda m: _last4(m.group(0)), text)
    return _LONG_ID.sub(lambda m: _last4(m.group(0)), text)


def _is_heading(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    return 4 <= len(line) <= 90 and len(letters) >= 4 and line.isupper()


def chunk_pages(pages: list[str], max_chars: int = MAX_CHUNK_CHARS) -> list[PageChunk]:
    chunks: list[PageChunk] = []
    section = ""
    for page_no, page_text in enumerate(pages, start=1):
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        current: list[str] = []
        current_section = section
        for line in lines:
            if current and len(" ".join(current)) + len(line) > max_chars:
                chunks.append(PageChunk(page_no, current_section, "\n".join(current)))
                current = current[-1:]  # one line of overlap
                current_section = section
            if _is_heading(line):
                section = line
                if not current:
                    current_section = section
            current.append(line)
        if current:
            chunks.append(PageChunk(page_no, current_section, "\n".join(current)))
    return chunks


WATERMARK_MIN_SIZE = 40  # pt; body text is ~10, a "SAMPLE"/"COPY" watermark is ~55


def _not_watermark(obj: dict) -> bool:
    return obj.get("object_type") != "char" or obj.get("size", 0) <= WATERMARK_MIN_SIZE


def extract_pages(path: Path) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [page.filter(_not_watermark).extract_text() or "" for page in pdf.pages]


def read_policy_pdf(path: Path) -> list[PageChunk]:
    pages = extract_pages(path)
    if sum(len(p.strip()) for p in pages) < MIN_TEXT_CHARS_PER_PAGE * max(len(pages), 1):
        raise ScannedPdfError("This looks like a scan; please upload a text PDF.")
    return chunk_pages([mask_identifiers(p) for p in pages])
