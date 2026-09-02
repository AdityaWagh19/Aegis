# tests/conftest.py
"""
Session-wide test configuration.

Isolates integration tests from the development database by pointing
DATABASE_URL at a file-based test SQLite DB before models.db is imported
(the engine binds the URL at import time). The plan's risk table prescribes
file-based SQLite (aegis_test.db) with cleanup.
"""
import os
import asyncio
from pathlib import Path

_TEST_DB = Path("aegis_test.db")

# Must be set BEFORE any test module imports models.db.
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///./{_TEST_DB.name}"

import pytest


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    """Create all tables in the test DB for the session; delete the file after."""
    from models.db import init_db
    asyncio.run(init_db())
    yield
    if _TEST_DB.exists():
        try:
            _TEST_DB.unlink()
        except OSError:
            pass
