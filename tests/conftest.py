"""Shared pytest fixtures for the Spendly test suite.

Spendly's DB layer (database/db.py) does not read a Flask config key — it opens
every connection against a module-level `DB_PATH` constant. `app.py` also runs
`init_db()` and `seed_db()` once, at import time, against whatever `DB_PATH`
is current. To keep tests fully isolated from the real `expense_tracker.db`
file (and from each other), `DB_PATH` is redirected to a throwaway file
*before* `app` is imported for the first time, and then re-pointed to a fresh
empty temp file for every individual test via the `app` fixture below.
"""
import os
import tempfile

import pytest

import database.db as db_module

# Redirect DB_PATH before the first `import app`, so app.py's module-level
# `with app.app_context(): init_db(); seed_db()` never touches the real DB.
_bootstrap_fd, _bootstrap_path = tempfile.mkstemp(suffix=".db")
os.close(_bootstrap_fd)
db_module.DB_PATH = _bootstrap_path

from app import app as flask_app  # noqa: E402
from database.db import get_db, get_user_by_email, init_db  # noqa: E402


@pytest.fixture
def app(monkeypatch):
    """The Spendly Flask app, wired to a fresh, empty SQLite file per test."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    flask_app.config.update(TESTING=True, SECRET_KEY="test-secret")

    with flask_app.app_context():
        init_db()

    yield flask_app

    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def registered_user(app, client):
    """Register a brand-new user (not logged in) and return id/email/password."""
    email = "filtertest@example.com"
    password = "testpass123"
    resp = client.post(
        "/register",
        data={"name": "Filter Test", "email": email, "password": password},
        follow_redirects=True,
    )
    assert resp.status_code == 200, "Setup failed: registration request did not succeed"

    user = get_user_by_email(email)
    assert user is not None, "Setup failed: registration did not create a user"
    return {"id": user["id"], "email": email, "password": password}


@pytest.fixture
def auth_client(client, registered_user):
    """A test client already logged in as `registered_user`."""
    resp = client.post(
        "/login",
        data={"email": registered_user["email"], "password": registered_user["password"]},
        follow_redirects=True,
    )
    assert resp.status_code == 200, "Setup failed: login request did not succeed"
    return client


@pytest.fixture
def insert_expense(app):
    """Return a callable that inserts one expense row directly into the DB.

    `/expenses/add` is a not-yet-implemented stub (Step 7), so tests that need
    fixture expense data must write rows directly, using the same parameterised
    SQL style as the rest of the codebase.
    """

    def _insert(user_id, amount, category, expense_date, description=None):
        conn = get_db()
        try:
            conn.execute(
                """
                INSERT INTO expenses (user_id, amount, category, date, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, amount, category, expense_date, description),
            )
            conn.commit()
        finally:
            conn.close()

    return _insert
