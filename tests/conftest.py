"""Shared pytest fixtures: an isolated SQLite DB and a Flask test client.

app.py bootstraps the database (init_db() + seed_db()) as soon as it is
imported, reading database.db.DB_PATH — a module-level constant computed at
import time. To keep tests off the real expense_tracker.db, DB_PATH has to
be monkeypatched to a temp file *before* app.py's bootstrap code runs, which
means before app.py is (re-)imported.
"""

import importlib
import os
import sys

import pytest

# Make sure "app" and "database" are importable regardless of the directory
# pytest was invoked from.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import database.db as db_module  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    """A Flask app wired to a fresh, seeded, temporary SQLite file."""
    db_path = tmp_path / "test_expense_tracker.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))

    # Force a fresh import so app.py's module-level init_db()/seed_db()
    # bootstrap runs against the patched DB_PATH, not a cached module whose
    # bootstrap already ran against the real database.
    sys.modules.pop("app", None)
    app_module = importlib.import_module("app")
    app_module.app.config.update(TESTING=True)

    yield app_module.app

    sys.modules.pop("app", None)


@pytest.fixture
def demo_user(app):
    """The seeded demo user's row (id, name, email, created_at, ...)."""
    from database.db import get_user_by_email

    return get_user_by_email("demo@spendly.com")


@pytest.fixture
def auth_client(client, demo_user):
    """A test client already logged in as the seeded demo user."""
    with client.session_transaction() as sess:
        sess["user_id"] = demo_user["id"]
        sess["user_name"] = demo_user["name"]
        sess["user_email"] = demo_user["email"]
        sess["user_created_at"] = demo_user["created_at"]
    return client
