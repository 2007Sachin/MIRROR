"""Dig Deeper answer checks: every question kind answers, in structured parts, without numbers or a grade."""

import re

import pytest
from fastapi.testclient import TestClient

from app.auth import get_token_verifier
from app.copy_guard import find_banned
from app.main import app
from app.pressure_test import CHECKS_FOR, QuestionKind
from tests.test_role_agent import RoleVerifier

A = {"Authorization": "Bearer role-a"}
BRIEF = "We improved the report."
FULL = (
    "I rebuilt the weekly report myself because the old one took two days to assemble, rather than "
    "patching it again. I chose a single shared data source, wrote the queries, and walked each manager "
    "through it. As a result reporting time was cut from two days to three hours, which meant the team "
    "could act on Monday instead of Wednesday, and I remember the first Monday we caught a stock issue early."
)


@pytest.fixture
def client():
    app.dependency_overrides[get_token_verifier] = lambda: RoleVerifier()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_token_verifier, None)


def feedback_text(body: dict) -> list[str]:
    return [*body["clear"], body["missing"] or "", body["next_sentence"], *(check["text"] for check in body["checks"])]


def test_every_kind_has_checks() -> None:
    assert set(CHECKS_FOR) == set(QuestionKind)


@pytest.mark.parametrize("kind", list(QuestionKind))
@pytest.mark.parametrize("answer", [BRIEF, FULL])
def test_every_kind_answers_with_structured_feedback(client, kind: QuestionKind, answer: str) -> None:
    response = client.post("/api/v1/answer-checks", headers=A, json={"kind": kind.value, "answer": answer})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["checks"] and isinstance(body["clear"], list)
    assert body["next_sentence"].strip()
    present = [check for check in body["checks"] if check["present"]]
    assert body["clear"] == [check["text"] for check in present]
    # A missing detail is named exactly when a check did not come through.
    assert (body["missing"] is None) == (len(present) == len(body["checks"]))
    for text in feedback_text(body):
        assert not re.search(r"\d|%", text), text
        assert not find_banned(text), text


def test_a_brief_answer_names_what_is_missing_and_offers_an_opening() -> None:
    from app.pressure_test import AnswerCheckRequest, check_answer

    result = check_answer(AnswerCheckRequest(kind=QuestionKind.SITUATION, answer=BRIEF))
    assert result.missing and result.next_sentence.endswith("…")


def test_answer_checks_need_sign_in(client) -> None:
    assert client.post("/api/v1/answer-checks", json={"kind": "SITUATION", "answer": BRIEF}).status_code == 401
