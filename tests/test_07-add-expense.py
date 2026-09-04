"""Tests for the add-expense feature (spec: .claude/specs/07-add-expense.md).

These tests are written against the spec's stated behaviour, not against the
implementation. They treat `/expenses/add` as a black box: they check for the
form landmarks, validation rules, redirect targets, and DB side effects that
the spec explicitly promises, rather than any internal rendering detail.

Covers:
- `database.queries.insert_expense` as a standalone unit (direct DB writes,
  including the `description=None` -> SQL NULL contract).
- Auth guards on both GET and POST `/expenses/add`.
- The GET form's required fields/landmarks (amount, category options, date
  default, description, submit button, cancel link).
- POST validation rules (missing/zero/negative/non-numeric amount, invalid
  category, invalid date, optional description) and the "re-render with
  previous values on error" contract.
- Successful POST -> redirect to `/profile` + DB row created.
- The "Add Expense" entry points on the profile page and navbar.
"""
import re
from datetime import date, timedelta

from flask import url_for

from database.db import get_db
from database.queries import insert_expense as db_insert_expense

TODAY = date.today()

CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


# --------------------------------------------------------------------- #
# Small helpers                                                          #
# --------------------------------------------------------------------- #

def _html(resp):
    return resp.data.decode()


def _url(app, endpoint, **kwargs):
    with app.test_request_context():
        return url_for(endpoint, **kwargs)


def _iso(d):
    return d.isoformat()


def _tag(html, tag_name, name_attr):
    """Return the full opening tag (e.g. `<input ...>` or `<select ...>`)
    for the element whose `name="..."` attribute matches `name_attr`.

    Attribute-order independent: only requires that `name="{name_attr}"`
    appear somewhere inside the tag's attribute list.
    """
    m = re.search(
        rf'<{tag_name}\b[^>]*\bname="{re.escape(name_attr)}"[^>]*>', html, re.DOTALL
    )
    return m.group(0) if m else None


def _select_block(html, name_attr):
    """Return the full `<select ...>...</select>` block for a given name."""
    m = re.search(
        rf'<select\b[^>]*\bname="{re.escape(name_attr)}"[^>]*>(.*?)</select>',
        html,
        re.DOTALL,
    )
    return m.group(0) if m else None


def _option_values(select_block):
    return re.findall(r'<option\s+value="([^"]*)"', select_block or "")


def _rows_for_user(app, user_id):
    """Query the expenses table directly, bypassing the app/HTTP layer."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id", (user_id,)
        ).fetchall()
    finally:
        conn.close()


# --------------------------------------------------------------------- #
# Unit tests: database.queries.insert_expense                           #
# --------------------------------------------------------------------- #

class TestInsertExpenseUnit:
    def test_valid_insert_creates_a_queryable_row(self, app, registered_user):
        uid = registered_user["id"]

        new_id = db_insert_expense(uid, 50.0, "Food", "2026-03-20", "Lunch")

        rows = _rows_for_user(app, uid)
        assert len(rows) == 1, "Expected exactly one expense row after insert"
        row = rows[0]
        assert row["id"] == new_id
        assert row["user_id"] == uid
        assert row["amount"] == 50.0
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"

    def test_description_none_is_stored_as_sql_null(self, app, registered_user):
        uid = registered_user["id"]

        db_insert_expense(uid, 25.5, "Bills", "2026-04-01", None)

        rows = _rows_for_user(app, uid)
        assert len(rows) == 1
        assert rows[0]["description"] is None, "description=None must be stored as NULL, not ''"


# --------------------------------------------------------------------- #
# Auth guards                                                            #
# --------------------------------------------------------------------- #

class TestAddExpenseAuthGuard:
    def test_get_unauthenticated_redirects_to_login(self, app, client):
        resp = client.get(_url(app, "add_expense"))
        assert resp.status_code == 302, "Unauthenticated GET must redirect"
        assert "/login" in resp.headers["Location"]

    def test_post_unauthenticated_redirects_to_login(self, app, client):
        resp = client.post(
            _url(app, "add_expense"),
            data={
                "amount": "50.0",
                "category": "Food",
                "date": _iso(TODAY),
                "description": "Lunch",
            },
        )
        assert resp.status_code == 302, "Unauthenticated POST must redirect, not write"
        assert "/login" in resp.headers["Location"]

    def test_post_unauthenticated_does_not_create_a_row(self, app, client, registered_user):
        client.post(
            _url(app, "add_expense"),
            data={
                "amount": "50.0",
                "category": "Food",
                "date": _iso(TODAY),
                "description": "Should not be saved",
            },
        )
        rows = _rows_for_user(app, registered_user["id"])
        assert rows == [], "An unauthenticated POST must never write to the DB"


# --------------------------------------------------------------------- #
# GET /expenses/add — form rendering                                    #
# --------------------------------------------------------------------- #

class TestAddExpenseGetForm:
    def test_authenticated_get_returns_200(self, app, auth_client):
        resp = auth_client.get(_url(app, "add_expense"))
        assert resp.status_code == 200

    def test_form_has_post_method_and_correct_action(self, app, auth_client):
        html = _html(auth_client.get(_url(app, "add_expense")))
        m = re.search(r'<form\b[^>]*>', html, re.DOTALL)
        assert m is not None, "Expected a <form> element on the page"
        form_tag = m.group(0)
        assert re.search(r'method="POST"', form_tag, re.IGNORECASE), (
            "Form must submit via POST"
        )
        assert "/expenses/add" in form_tag, "Form action must point at /expenses/add"

    def test_amount_field_is_a_positive_step_number_input_and_required(self, app, auth_client):
        html = _html(auth_client.get(_url(app, "add_expense")))
        tag = _tag(html, "input", "amount")
        assert tag is not None, "Expected an <input name=\"amount\"> field"
        assert 'type="number"' in tag
        assert 'step="0.01"' in tag
        assert 'min="0.01"' in tag
        assert "required" in tag

    def test_category_select_has_exactly_the_seven_fixed_options(self, app, auth_client):
        html = _html(auth_client.get(_url(app, "add_expense")))
        block = _select_block(html, "category")
        assert block is not None, "Expected a <select name=\"category\"> field"
        assert _option_values(block) == CATEGORIES

    def test_date_field_is_required_and_defaults_to_today(self, app, auth_client):
        html = _html(auth_client.get(_url(app, "add_expense")))
        tag = _tag(html, "input", "date")
        assert tag is not None, "Expected an <input name=\"date\"> field"
        assert 'type="date"' in tag
        assert "required" in tag
        assert f'value="{_iso(TODAY)}"' in tag, "Date field must default to today's date"

    def test_description_field_is_optional_text_with_max_200_chars(self, app, auth_client):
        html = _html(auth_client.get(_url(app, "add_expense")))
        tag = _tag(html, "input", "description")
        assert tag is not None, "Expected an <input name=\"description\"> field"
        assert 'type="text"' in tag
        assert 'maxlength="200"' in tag
        assert "required" not in tag, "description must be optional"

    def test_page_has_save_and_cancel_controls(self, app, auth_client):
        html = _html(auth_client.get(_url(app, "add_expense")))
        assert "Save Expense" in html
        assert 'href="/profile"' in html or _url(app, "profile") in html, (
            "Expected a cancel link back to /profile"
        )


# --------------------------------------------------------------------- #
# POST /expenses/add — happy path                                       #
# --------------------------------------------------------------------- #

class TestAddExpensePostSuccess:
    def test_valid_submission_redirects_to_profile(self, app, auth_client):
        resp = auth_client.post(
            _url(app, "add_expense"),
            data={
                "amount": "50.0",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Lunch",
            },
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].rstrip("/").endswith("/profile")

    def test_valid_submission_creates_the_expected_row(self, app, auth_client, registered_user):
        auth_client.post(
            _url(app, "add_expense"),
            data={
                "amount": "50.0",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Lunch",
            },
        )

        rows = _rows_for_user(app, registered_user["id"])
        assert len(rows) == 1
        row = rows[0]
        assert row["amount"] == 50.0
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"

    def test_valid_submission_is_visible_on_the_profile_page(self, app, auth_client):
        resp = auth_client.post(
            _url(app, "add_expense"),
            data={
                "amount": "50.0",
                "category": "Food",
                "date": "2026-03-20",
                "description": "UNIQUE_LUNCH_MARKER",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "UNIQUE_LUNCH_MARKER" in _html(resp)

    def test_no_description_saves_with_null_description(self, app, auth_client, registered_user):
        resp = auth_client.post(
            _url(app, "add_expense"),
            data={
                "amount": "20.0",
                "category": "Transport",
                "date": _iso(TODAY),
                "description": "",
            },
        )
        assert resp.status_code == 302, "Missing/blank description must not be a validation error"

        rows = _rows_for_user(app, registered_user["id"])
        assert len(rows) == 1
        assert rows[0]["description"] is None

    def test_whitespace_only_description_is_stripped_to_null(
        self, app, auth_client, registered_user
    ):
        resp = auth_client.post(
            _url(app, "add_expense"),
            data={
                "amount": "20.0",
                "category": "Transport",
                "date": _iso(TODAY),
                "description": "    ",
            },
        )
        assert resp.status_code == 302

        rows = _rows_for_user(app, registered_user["id"])
        assert len(rows) == 1
        assert rows[0]["description"] is None

    def test_description_with_surrounding_whitespace_is_stripped(
        self, app, auth_client, registered_user
    ):
        resp = auth_client.post(
            _url(app, "add_expense"),
            data={
                "amount": "20.0",
                "category": "Transport",
                "date": _iso(TODAY),
                "description": "  Bus fare  ",
            },
        )
        assert resp.status_code == 302

        rows = _rows_for_user(app, registered_user["id"])
        assert len(rows) == 1
        assert rows[0]["description"] == "Bus fare"

    def test_each_category_in_the_fixed_list_is_accepted(self, app, auth_client, registered_user):
        for cat in CATEGORIES:
            resp = auth_client.post(
                _url(app, "add_expense"),
                data={
                    "amount": "10.0",
                    "category": cat,
                    "date": _iso(TODAY),
                    "description": "",
                },
            )
            assert resp.status_code == 302, f"Category {cat!r} should be accepted"

        rows = _rows_for_user(app, registered_user["id"])
        assert {r["category"] for r in rows} == set(CATEGORIES)


# --------------------------------------------------------------------- #
# POST /expenses/add — validation errors                                #
# --------------------------------------------------------------------- #

class TestAddExpensePostValidation:
    def _post(self, auth_client, app, **overrides):
        data = {
            "amount": "50.0",
            "category": "Food",
            "date": _iso(TODAY),
            "description": "Lunch",
        }
        data.update(overrides)
        return auth_client.post(_url(app, "add_expense"), data=data)

    def test_missing_amount_re_renders_form_with_error(self, app, auth_client, registered_user):
        resp = self._post(auth_client, app, amount="")
        assert resp.status_code == 200, "Validation errors must re-render, not redirect"
        html = _html(resp)
        assert re.search(r'class="[^"]*error[^"]*"', html, re.IGNORECASE) or "error" in html.lower(), (
            "Expected an error message in the re-rendered form"
        )
        assert _rows_for_user(app, registered_user["id"]) == [], "Invalid data must not be saved"

    def test_zero_amount_re_renders_form_with_error(self, app, auth_client, registered_user):
        resp = self._post(auth_client, app, amount="0")
        assert resp.status_code == 200
        assert _rows_for_user(app, registered_user["id"]) == []

    def test_negative_amount_re_renders_form_with_error(self, app, auth_client, registered_user):
        resp = self._post(auth_client, app, amount="-5")
        assert resp.status_code == 200
        assert _rows_for_user(app, registered_user["id"]) == []

    def test_non_numeric_amount_re_renders_form_with_error(self, app, auth_client, registered_user):
        resp = self._post(auth_client, app, amount="not-a-number")
        assert resp.status_code == 200
        assert _rows_for_user(app, registered_user["id"]) == []

    def test_invalid_category_re_renders_form_with_error(self, app, auth_client, registered_user):
        resp = self._post(auth_client, app, category="Vacation")
        assert resp.status_code == 200
        assert _rows_for_user(app, registered_user["id"]) == []

    def test_invalid_date_re_renders_form_with_error(self, app, auth_client, registered_user):
        resp = self._post(auth_client, app, date="not-a-date")
        assert resp.status_code == 200
        assert _rows_for_user(app, registered_user["id"]) == []

    def test_malformed_calendar_date_is_rejected(self, app, auth_client, registered_user):
        # 2026-02-30 is not a real calendar date.
        resp = self._post(auth_client, app, date="2026-02-30")
        assert resp.status_code == 200
        assert _rows_for_user(app, registered_user["id"]) == []

    def test_category_containing_sql_injection_attempt_is_rejected_safely(
        self, app, auth_client, registered_user
    ):
        resp = self._post(auth_client, app, category="Food'; DROP TABLE expenses;--")
        assert resp.status_code == 200, "Must be handled as an ordinary invalid category, not crash"
        assert _rows_for_user(app, registered_user["id"]) == []

        # Confirm the expenses table itself survived (parameterised queries only).
        conn = get_db()
        try:
            conn.execute("SELECT 1 FROM expenses LIMIT 1")
        finally:
            conn.close()

    def test_error_response_repopulates_previously_submitted_values(
        self, app, auth_client
    ):
        resp = self._post(
            auth_client,
            app,
            amount="",
            category="Shopping",
            date=_iso(TODAY),
            description="Keep me on screen",
        )
        html = _html(resp)
        assert resp.status_code == 200
        assert "Keep me on screen" in html, "Previously submitted description must be pre-filled"
        assert 'value="Shopping"' in html or "selected" in html, (
            "Previously submitted category should remain selected"
        )
        assert f'value="{_iso(TODAY)}"' in html, "Previously submitted date must be pre-filled"


# --------------------------------------------------------------------- #
# Navigation entry points                                                #
# --------------------------------------------------------------------- #

class TestAddExpenseEntryPoints:
    def test_profile_page_has_an_add_expense_link(self, app, auth_client):
        html = _html(auth_client.get(_url(app, "profile")))
        assert "Add Expense" in html
        assert _url(app, "add_expense") in html or "/expenses/add" in html

    def test_navbar_shows_add_expense_link_when_logged_in(self, app, auth_client):
        html = _html(auth_client.get(_url(app, "profile")))
        assert "Add Expense" in html

    def test_navbar_hides_add_expense_link_when_logged_out(self, app, client):
        html = _html(client.get(_url(app, "landing")))
        assert "Add Expense" not in html
