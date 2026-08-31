import os
import sqlite3
from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key-do-not-ship")


# ------------------------------------------------------------------ #
# Database bootstrap                                                  #
# ------------------------------------------------------------------ #

with app.app_context():
    init_db()
    seed_db()


@app.context_processor
def inject_is_logged_in():
    return {"is_logged_in": session.get("user_id") is not None}


# ------------------------------------------------------------------ #
# Form validation                                                     #
# ------------------------------------------------------------------ #

def _validate_registration(name, email, password):
    """Return an error message for the first broken rule, or None if valid.

    Expects name and email already stripped and the password untouched.
    """
    if not name or not email or not password:
        return "All fields are required."

    if not 2 <= len(name) <= 60:
        return "Name must be between 2 and 60 characters."

    # A single @ with text either side — deliberately loose, since the only way
    # to truly validate an address is to send mail to it.
    local, separator, domain = email.partition("@")
    if not separator or not local or not domain or "@" in domain or len(email) > 120:
        return "Please enter a valid email address."

    if len(password) < 8:
        return "Password must be at least 8 characters."

    return None


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id") is not None:
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    # Lowercased on the way in so the UNIQUE constraint rejects the same
    # address in different casing — SQLite compares TEXT case-sensitively.
    email = request.form.get("email", "").strip().lower()
    # Never stripped: spaces are legitimate password characters.
    password = request.form.get("password", "")

    error = _validate_registration(name, email, password)

    if error is None and get_user_by_email(email) is not None:
        error = "An account with that email already exists."

    if error is None:
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            # Backstop for the gap between the check above and this insert.
            error = "An account with that email already exists."

    if error:
        return render_template("register.html", error=error, name=name, email=email)

    return redirect(url_for("login", registered=1))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id") is not None:
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template(
            "login.html", registered=request.args.get("registered") == "1"
        )

    email = request.form.get("email", "").strip().lower()
    # Never stripped: spaces are legitimate password characters.
    password = request.form.get("password", "")

    user = get_user_by_email(email)
    # One generic message for every failure case — missing fields, unknown
    # email, wrong password — so the form never reveals which was wrong.
    if user is None or not password or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.")
        return render_template("login.html", email=email)

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    session["user_created_at"] = user["created_at"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if session.get("user_id") is None:
        return redirect(url_for("login"))

    name = session.get("user_name", "")
    initials = "".join(part[0] for part in name.split()[:2]).upper() or "?"

    created_at = session.get("user_created_at")
    member_since = (
        datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").strftime("%B %Y")
        if created_at
        else ""
    )

    user = {
        "initials": initials,
        "name": name,
        "email": session.get("user_email", ""),
        "member_since": member_since,
    }
    stats = {
        "total_spent": "Rs9,530",
        "transaction_count": 8,
        "top_category": "Food",
    }
    transactions = [
        {"date": "Aug 21", "description": "Grocery run", "category": "Food", "amount": "Rs1,250"},
        {"date": "Aug 18", "description": "Winter jacket", "category": "Shopping", "amount": "Rs2,200"},
        {"date": "Aug 15", "description": "Cinema tickets", "category": "Entertainment", "amount": "Rs750"},
        {"date": "Aug 12", "description": "Monthly medication", "category": "Health", "amount": "Rs900"},
        {"date": "Aug 09", "description": "Electricity bill", "category": "Bills", "amount": "Rs3,500"},
        {"date": "Aug 06", "description": "Fuel top-up", "category": "Transport", "amount": "Rs300"},
    ]
    categories = [
        {"name": "Bills", "amount": "Rs3,500", "pct": 37, "variant": "bills"},
        {"name": "Shopping", "amount": "Rs2,200", "pct": 23, "variant": "shopping"},
        {"name": "Food", "amount": "Rs1,250", "pct": 13, "variant": "food"},
        {"name": "Health", "amount": "Rs900", "pct": 9, "variant": "health"},
        {"name": "Entertainment", "amount": "Rs750", "pct": 8, "variant": "entertainment"},
        {"name": "Transport", "amount": "Rs300", "pct": 3, "variant": "transport"},
        {"name": "Other", "amount": "Rs150", "pct": 2, "variant": "other"},
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
