"""Read-only query helpers for the profile page.

Every function opens its own connection via get_db(), runs a parameterised
query against `expenses`/`users`, and closes the connection before
returning — callers never see an open connection or a raw cursor.
"""

from datetime import datetime

from database.db import get_db


def _format_currency(amount):
    """Format a numeric amount as "Rs1,250.00" (prefix, thousands sep, 2dp).

    Accepts None as 0 so callers can pass a raw SUM() result straight
    through even when it comes back NULL for a user with no expenses.
    """
    return f"Rs{(amount or 0):,.2f}"


def get_recent_transactions(user_id, limit=10):
    """Return the user's most recent expenses, newest first.

    Each item: {"date": "Aug 21", "description": str, "category": str,
    "amount": "Rs1,250.00"}. Empty-state (no expenses): [].
    """
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT amount, category, date, description
            FROM expenses
            WHERE user_id = ?
            ORDER BY date DESC, created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "date": datetime.strptime(row["date"], "%Y-%m-%d").strftime("%b %d"),
            "description": row["description"] or "",
            "category": row["category"],
            "amount": _format_currency(row["amount"]),
        }
        for row in rows
    ]


def get_summary_stats(user_id):
    """Return {"total_spent", "transaction_count", "top_category"}.

    Empty-state (no expenses): total_spent formatted zero, count 0,
    top_category "—".
    """
    conn = get_db()
    try:
        totals = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt
            FROM expenses
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        top = conn.execute(
            """
            SELECT category
            FROM expenses
            WHERE user_id = ?
            GROUP BY category
            ORDER BY SUM(amount) DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    return {
        "total_spent": _format_currency(totals["total"]),
        "transaction_count": totals["cnt"],
        "top_category": top["category"] if top is not None else "—",
    }


def get_category_breakdown(user_id):
    """Return per-category totals for the user, largest amount first.

    Each item: {"name": str, "amount": "Rs...", "pct": int, "variant": str}.
    pct values are integers that sum to exactly 100 (rounding remainder
    absorbed by the largest category). Empty-state (no expenses): [].
    """
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT category, SUM(amount) AS total
            FROM expenses
            WHERE user_id = ?
            GROUP BY category
            ORDER BY total DESC
            """,
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    grand_total = sum(row["total"] for row in rows)
    if grand_total <= 0:
        # All matched expenses sum to zero or less — degenerate case,
        # split percentages evenly rather than dividing by zero.
        pcts = [round(100 / len(rows))] * len(rows)
    else:
        pcts = [round(row["total"] / grand_total * 100) for row in rows]

    remainder = 100 - sum(pcts)
    pcts[0] += remainder  # rows[0] is the largest category (ORDER BY total DESC)

    return [
        {
            "name": row["category"],
            "amount": _format_currency(row["total"]),
            "pct": pct,
            "variant": row["category"].lower(),
        }
        for row, pct in zip(rows, pcts)
    ]
