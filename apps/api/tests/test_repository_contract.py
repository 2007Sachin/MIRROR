from app.repository import SESSION_READ_COLUMNS
from app.schemas import SessionRead


def test_session_repository_selects_only_public_session_contract() -> None:
    selected = set(SESSION_READ_COLUMNS.split(","))

    assert selected == set(SessionRead.model_fields)
    assert "skeptic_mode" not in selected
