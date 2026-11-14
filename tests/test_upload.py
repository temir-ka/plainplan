import re
import tempfile
from pathlib import Path

import pypdfium2
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app
from app.models import Chunk, PolicyMember

AUTO = Path("samples/Sample_US_Personal_Auto_Policy.pdf")
needs_sample = pytest.mark.skipif(not AUTO.exists(), reason="sample PDF not present")


def new_client() -> TestClient:
    client = TestClient(app)
    client.get("/")
    return client


def add_member(client: TestClient, nickname: str) -> int:
    html = client.post("/members", data={"nickname": nickname, "role": "parent"}).text
    return int(re.findall(r'hx-delete="/members/(\d+)"', html)[-1])


def upload(client: TestClient, content: bytes, type_: str = "auto", member_ids: list[int] = ()):
    return client.post(
        "/policies",
        files={"file": ("policy.pdf", content, "application/pdf")},
        data={"type": type_, "member_ids": [str(m) for m in member_ids]},
        follow_redirects=False,
    )


def temp_pdfs() -> set[str]:
    return {p.name for p in Path(tempfile.gettempdir()).glob("*.pdf")}


@needs_sample
def test_upload_stores_masked_chunks_and_deletes_file():
    with new_client() as client:
        dad = add_member(client, "Dad")
        before = temp_pdfs()
        response = upload(client, AUTO.read_bytes(), "auto", [dad])
        assert temp_pdfs() == before  # the temp file is gone
        assert response.status_code == 303
        policy_id = int(response.headers["location"].rsplit("/", 1)[1])

        with Session(engine) as s:
            chunks = s.exec(select(Chunk).where(Chunk.policy_id == policy_id)).all()
            links = s.exec(select(PolicyMember).where(PolicyMember.policy_id == policy_id)).all()
        text = "\n".join(c.text for c in chunks)
        assert chunks and "1HGCV1F58NA042819" not in text
        assert [link.member_id for link in links] == [dad]

        page = client.get(f"/policy/{policy_id}").text
        assert "covers Dad" in page and "4 pages read" in page
        assert '<b class="hd">Auto</b>' in client.get(f"/member/{dad}").text  # the policy card
        assert 'title="Auto"' in client.get("/").text  # the icon on Dad's tile


@needs_sample
def test_upload_without_members_is_shared():
    with new_client() as client:
        policy_url = upload(client, AUTO.read_bytes(), "auto").headers["location"]
        assert "covers Shared" in client.get(policy_url).text
        assert "/policy/" in client.get("/shared").text


@needs_sample
def test_other_familys_member_ids_are_ignored():
    with new_client() as alice, new_client() as mallory:
        ava = add_member(alice, "Ava")
        policy_url = upload(mallory, AUTO.read_bytes(), "auto", [ava]).headers["location"]
        assert "covers Shared" in mallory.get(policy_url).text
        assert alice.get(policy_url).status_code == 404  # and Alice can't see Mallory's policy


def test_not_a_pdf_is_refused():
    with new_client() as client:
        response = upload(client, b"hello, not a pdf")
        assert response.headers["location"].endswith("error=notpdf")
        assert "not a PDF" in client.get(response.headers["location"]).text


def test_scan_is_refused(tmp_path):
    path = tmp_path / "scan.pdf"
    doc = pypdfium2.PdfDocument.new()
    doc.new_page(612, 792)
    doc.save(path)
    with new_client() as client:
        response = upload(client, path.read_bytes())
        assert response.headers["location"].endswith("error=scan")


def test_missing_type_is_refused():
    with new_client() as client:
        assert upload(client, b"%PDF-1.4", type_="pets").headers["location"].endswith("error=type")
