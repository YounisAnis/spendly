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


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    """Return the user's most recent expenses, newest first.

    Each item: {"date": "Aug 21", "description": str, "category": str,
    "amount": "Rs1,250.00"}. Empty-state (no expenses): [].

    When both date_from and date_to are given (inclusive ISO YYYY-MM-DD
    bounds), only expenses in that range are returned.
    """
    date_clause = " AND date BETWEEN ? AND ?" if date_from and date_to else ""
    date_params = (date_from, date_to) if date_from and date_to else ()

    conn = get_db()
    try:
        rows = conn.execute(
            f"""
            SELECT amount, category, date, description
            FROM expenses
            WHERE user_id = ?{date_clause}
            ORDER BY date DESC, created_at DESC
            LIMIT ?
            """,
            (user_id, *date_params, limit),
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


def get_summary_stats(user_id, date_from=None, date_to=None):
    """Return {"total_spent", "transaction_count", "top_category"}.

    Empty-state (no expenses): total_spent formatted zero, count 0,
    top_category "—".

    When both date_from and date_to are given (inclusive ISO YYYY-MM-DD
    bounds), stats are computed only over expenses in that range.
    """
    date_clause = " AND date BETWEEN ? AND ?" if date_from and date_to else ""
    date_params = (date_from, date_to) if date_from and date_to else ()

    conn = get_db()
    try:
        totals = conn.execute(
            f"""
            SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt
            FROM expenses
            WHERE user_id = ?{date_clause}
            """,
            (user_id, *date_params),
        ).fetchone()

        top = conn.execute(
            f"""
            SELECT category
            FROM expenses
            WHERE user_id = ?{date_clause}
            GROUP BY category
            ORDER BY SUM(amount) DESC
            LIMIT 1
            """,
            (user_id, *date_params),
        ).fetchone()
    finally:
        conn.close()

    return {
        "total_spent": _format_currency(totals["total"]),
        "transaction_count": totals["cnt"],
        "top_category": top["category"] if top is not None else "—",
    }


def get_category_breakdown(user_id, date_from=None, date_to=None):
    """Return per-category totals for the user, largest amount first.

    Each item: {"name": str, "amount": "Rs...", "pct": int, "variant": str}.
    pct values are integers that sum to exactly 100 (rounding remainder
    absorbed by the largest category). Empty-state (no expenses): [].

    When both date_from and date_to are given (inclusive ISO YYYY-MM-DD
    bounds), only expenses in that range are included.
    """
    date_clause = " AND date BETWEEN ? AND ?" if date_from and date_to else ""
    date_params = (date_from, date_to) if date_from and date_to else ()

    conn = get_db()
    try:
        rows = conn.execute(
            f"""
            SELECT category, SUM(amount) AS total
            FROM expenses
            WHERE user_id = ?{date_clause}
            GROUP BY category
            ORDER BY total DESC
            """,
            (user_id, *date_params),
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
