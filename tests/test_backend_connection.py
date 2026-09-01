"""Unit tests for database/queries.py and route tests for GET /profile."""

from database.db import create_user
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)


def test_get_summary_stats_returns_seeded_totals(app, demo_user):
    stats = get_summary_stats(demo_user["id"])

    assert stats["transaction_count"] == 8
    assert stats["total_spent"] == "Rs9,530.00"
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_empty_state_for_new_user(app):
    new_id = create_user("New User", "new@spendly.com", "password123")

    stats = get_summary_stats(new_id)

    assert stats == {
        "total_spent": "Rs0.00",
        "transaction_count": 0,
        "top_category": "—",
    }


def test_get_recent_transactions_orders_newest_first(app, demo_user):
    txns = get_recent_transactions(demo_user["id"], limit=10)

    assert len(txns) == 8
    # Day 21 (Other, Rs150.00) is the latest-dated seeded expense.
    assert txns[0]["category"] == "Other"
    assert txns[0]["amount"] == "Rs150.00"


def test_get_recent_transactions_respects_limit(app, demo_user):
    txns = get_recent_transactions(demo_user["id"], limit=3)

    assert len(txns) == 3


def test_get_recent_transactions_empty_state_for_new_user(app):
    new_id = create_user("Empty Txns User", "emptytxns@spendly.com", "password123")

    assert get_recent_transactions(new_id) == []


def test_get_category_breakdown_percentages_sum_to_100(app, demo_user):
    breakdown = get_category_breakdown(demo_user["id"])

    assert sum(cat["pct"] for cat in breakdown) == 100
    assert breakdown[0]["name"] == "Bills"
    assert breakdown[0]["variant"] == "bills"


def test_get_category_breakdown_contains_all_seeded_categories(app, demo_user):
    breakdown = get_category_breakdown(demo_user["id"])

    names = {cat["name"] for cat in breakdown}
    assert names == {
        "Food",
        "Transport",
        "Bills",
        "Health",
        "Entertainment",
        "Shopping",
        "Other",
    }


def test_get_category_breakdown_empty_state_for_new_user(app):
    new_id = create_user("Empty User", "empty@spendly.com", "password123")

    assert get_category_breakdown(new_id) == []


def test_profile_redirects_when_logged_out(client):
    response = client.get("/profile")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_profile_shows_seeded_data_when_logged_in(auth_client):
    response = auth_client.get("/profile")

    assert response.status_code == 200
    assert b"Rs9,530.00" in response.data
    assert b"Bills" in response.data
    assert b"Demo User" in response.data


def test_profile_shows_empty_state_for_new_user(app, client):
    from database.db import create_user

    new_id = create_user("Fresh User", "fresh@spendly.com", "password123")
    with client.session_transaction() as sess:
        sess["user_id"] = new_id
        sess["user_name"] = "Fresh User"
        sess["user_email"] = "fresh@spendly.com"
        sess["user_created_at"] = "2026-01-01 00:00:00"

    response = client.get("/profile")

    assert response.status_code == 200
    assert b"Rs0.00" in response.data
    assert b"No transactions yet" in response.data
    assert b"No expenses yet" in response.data
