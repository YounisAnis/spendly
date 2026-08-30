"""SQLite data layer for Spendly.

Provides the connection helper plus schema creation and development seeding.
All queries are parameterised — never build SQL with string formatting.
"""

import os
import sqlite3
from datetime import date

from werkzeug.security import generate_password_hash

# Project root is the parent of this package, so the database file lands beside
# app.py no matter which directory the app is launched from.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "expense_tracker.db")

# The fixed category list — every expense must use one of these values.
CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


def get_db():
    """Return a SQLite connection with row access by name and foreign keys on.

    Foreign key enforcement is a per-connection setting in SQLite and is off by
    default, so the pragma has to be issued here rather than once at startup.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the tables if they do not exist. Safe to call on every startup."""
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      REAL    NOT NULL,
                category    TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                description TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_db():
    """Insert the demo user and sample expenses once.

    Returns early when the users table already holds data, so repeated runs do
    not duplicate records.
    """
    conn = get_db()
    try:
        if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None:
            return

        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
        )
        user_id = cursor.lastrowid

        # Days stay at 21 or below so the dates are valid in every month.
        samples = [
            (1250.00, "Food", 2, "Grocery run"),
            (480.00, "Food", 4, "Lunch with team"),
            (300.00, "Transport", 6, "Fuel top-up"),
            (3500.00, "Bills", 9, "Electricity bill"),
            (900.00, "Health", 12, "Monthly medication"),
            (750.00, "Entertainment", 15, "Cinema tickets"),
            (2200.00, "Shopping", 18, "Winter jacket"),
            (150.00, "Other", 21, None),
        ]
        today = date.today()
        rows = [
            (user_id, amount, category, today.replace(day=day).isoformat(), description)
            for amount, category, day, description in samples
        ]

        conn.executemany(
            """
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()
