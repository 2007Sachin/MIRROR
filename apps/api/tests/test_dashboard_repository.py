import asyncio
import logging
from uuid import uuid4

import httpx
import pytest

from app.dashboard_repository import DashboardUnavailable, SupabaseDashboardRepository


class _Records(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def test_database_failure_is_logged_and_still_reported_as_unavailable():
    repository = object.__new__(SupabaseDashboardRepository)

    async def missing_column(*_args, **_kwargs):
        raise httpx.HTTPError("column sessions.role_profile_id does not exist")

    repository._get = missing_column

    # The "mirror" logger stops propagating once the app is imported, so listen on it directly.
    logger = logging.getLogger("mirror.dashboard")
    handler = _Records()
    logger.addHandler(handler)
    try:
        with pytest.raises(DashboardUnavailable):
            asyncio.run(repository.list_for_user(uuid4()))
    finally:
        logger.removeHandler(handler)

    record = handler.records[-1]
    assert record.levelno == logging.ERROR
    assert "role_profile_id" in str(record.exc_info[1])
