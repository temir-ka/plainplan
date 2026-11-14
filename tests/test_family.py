import re

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.main import app
from app.models import Household, Member, Policy


def new_client() -> TestClient:
    client = TestClient(app)
    client.get("/")  # first visit -> guest cookie
    return client


def member_ids(html: str) -> list[int]:
    return [int(x) for x in re.findall(r'hx-delete="/members/(\d+)"', html)]


def test_home_always_has_shared_tile():
    with new_client() as client:
        html = client.get("/").text
    assert 'href="/shared"' in html
    assert "Something happened?" in html


def test_start_creates_a_new_household_and_cookie():
    with new_client() as client:
        old_id = client.cookies["hh_id"]
        response = client.post("/start", data={"name": "The Smiths"})
        assert response.status_code == 200  # followed the redirect to /family
        assert client.cookies["hh_id"] != old_id
        assert "The Smiths" in response.text


def test_first_visit_post_start_keeps_the_new_family_cookie():
    with TestClient(app) as client:  # no cookie at all
        client.post("/start", data={"name": "The Lees"})
        assert "The Lees" in client.get("/").text


def test_add_and_remove_member():
    with new_client() as client:
        html = client.post("/members", data={"nickname": "Ava", "role": "child"}).text
        assert "Ava" in html
        [ava_id] = member_ids(html)

        assert client.get(f"/member/{ava_id}").status_code == 200
        assert "Ask about Ava&#39;s policies" in client.get(f"/member/{ava_id}").text

        html = client.delete(f"/members/{ava_id}").text
        assert "Ava" not in html


def test_bad_member_input_shows_error():
    with new_client() as client:
        html = client.post("/members", data={"nickname": "  ", "role": "child"}).text
        assert "Add a nickname" in html
        html = client.post("/members", data={"nickname": "Bob", "role": "boss"}).text
        assert "Add a nickname" in html


def test_cannot_open_another_familys_member():
    with new_client() as alice, new_client() as mallory:
        [ava_id] = member_ids(alice.post("/members", data={"nickname": "Ava", "role": "child"}).text)
        assert mallory.get(f"/member/{ava_id}").status_code == 404
        assert mallory.delete(f"/members/{ava_id}").status_code == 404


def test_member_with_policies_cannot_be_removed():
    with new_client() as client:
        hh_id = client.cookies["hh_id"]
        [dad_id] = member_ids(client.post("/members", data={"nickname": "Dad", "role": "parent"}).text)
        with Session(engine) as s:
            s.add(Policy(household_id=hh_id, member_id=dad_id, type="health", insurer="Aetna"))
            s.commit()
        html = client.delete(f"/members/{dad_id}").text
        assert "Remove Dad&#39;s policies first" in html
        assert "Aetna" in client.get(f"/member/{dad_id}").text
        assert "🩺" in client.get("/").text


def test_delete_data_removes_everything():
    with new_client() as client:
        hh_id = client.cookies["hh_id"]
        client.post("/members", data={"nickname": "Mom", "role": "parent"})
        client.post("/delete-data")
        with Session(engine) as s:
            assert s.get(Household, hh_id) is None
            assert s.query(Member).filter(Member.household_id == hh_id).count() == 0
        assert client.cookies.get("hh_id") != hh_id
