import re

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.main import app
from app.models import Household, Member, Policy, PolicyMember


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


def add_policy(hh_id: str, type_: str, insurer: str, member_ids_: list[int]) -> None:
    with Session(engine) as s:
        policy = Policy(household_id=hh_id, type=type_, insurer=insurer)
        s.add(policy)
        s.flush()  # assigns policy.id
        for m in member_ids_:
            s.add(PolicyMember(policy_id=policy.id, member_id=m))
        s.commit()


def test_family_plan_shows_on_every_covered_member():
    with new_client() as client:
        hh_id = client.cookies["hh_id"]
        client.post("/members", data={"nickname": "Dad", "role": "parent"})
        client.post("/members", data={"nickname": "Mom", "role": "parent"})
        html = client.post("/members", data={"nickname": "Ava", "role": "child"}).text
        dad_id, mom_id, ava_id = member_ids(html)  # nobody has policies yet, so all are removable
        add_policy(hh_id, "health", "Aetna", [dad_id, ava_id])
        add_policy(hh_id, "home", "State Farm", [])

        assert "Aetna" in client.get(f"/member/{dad_id}").text
        assert "Aetna" in client.get(f"/member/{ava_id}").text
        assert "Aetna" not in client.get(f"/member/{mom_id}").text
        shared = client.get("/shared").text
        assert "State Farm" in shared and "Aetna" not in shared


def test_member_with_policies_cannot_be_removed():
    with new_client() as client:
        hh_id = client.cookies["hh_id"]
        [dad_id] = member_ids(client.post("/members", data={"nickname": "Dad", "role": "parent"}).text)
        add_policy(hh_id, "health", "Aetna", [dad_id])
        html = client.delete(f"/members/{dad_id}").text
        assert "Remove Dad&#39;s policies first" in html
        assert "Aetna" in client.get(f"/member/{dad_id}").text
        assert 'title="Health"' in client.get("/").text


def test_delete_data_removes_everything():
    with new_client() as client:
        hh_id = client.cookies["hh_id"]
        [mom_id] = member_ids(client.post("/members", data={"nickname": "Mom", "role": "parent"}).text)
        add_policy(hh_id, "health", "Aetna", [mom_id])
        client.post("/delete-data")
        with Session(engine) as s:
            assert s.get(Household, hh_id) is None
            assert s.query(Member).filter(Member.household_id == hh_id).count() == 0
            assert s.query(Policy).filter(Policy.household_id == hh_id).count() == 0
            assert s.query(PolicyMember).filter(PolicyMember.member_id == mom_id).count() == 0
        assert client.cookies.get("hh_id") != hh_id


def test_pricing_page_is_honest_about_the_pilot():
    with new_client() as client:
        html = client.get("/pricing").text
    assert "$59" in html and "During the pilot everything is free" in html
    assert "checkout" not in html.lower() and "4242" not in html  # no payment flow is promised
