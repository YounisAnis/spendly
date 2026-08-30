# Spec: Registration

## Overview

Turn the existing `/register` page from a static form into a working account
creation flow. The template, styling and `users` table already exist — what is
missing is the server side: accepting the POST, validating the submitted
fields, rejecting duplicate emails, hashing the password with werkzeug and
inserting the row through the parameterised data layer built in Step 1. This is
the first feature that writes user data, and every later step (login, profile,
expenses) needs real accounts in the `users` table to work against, so it comes
directly after the database foundation.

Session handling is deliberately **out of scope**. Registration ends by sending
the new user to `/login` with a success message; actually signing them in is
Step 3.

## Depends on

- **Step 1 — Database setup** (complete): `get_db()`, `init_db()`, `seed_db()`
  and the `users` table with its `UNIQUE` email constraint.

## Routes

- `GET /register` — renders the empty registration form — public *(exists; add
  explicit `methods` list)*
- `POST /register` — validates input, creates the user, redirects to
  `/login?registered=1` on success; re-renders the form with an error message on
  failure — public
- `GET /login` — unchanged behaviour, but now reads the `registered` query
  parameter to show a success banner — public

## Database changes

No schema changes. The `users` table from Step 1 already has `name`, `email`
(`UNIQUE NOT NULL`), `password_hash` and `created_at`.

Two new helper functions are added to `database/db.py`:

- `get_user_by_email(email)` — returns a `sqlite3.Row` or `None`
- `create_user(name, email, password)` — hashes the password with
  `generate_password_hash` and inserts the row, returning the new `id`

## Templates

- **Create:** none
- **Modify:**
  - `templates/register.html` — re-populate `name` and `email` inputs from the
    rejected submission (`value="{{ name or '' }}"`) so a failed attempt does
    not clear the form; password is never re-populated
  - `templates/login.html` — render a success banner when `registered` is set
- **Modify (CSS):** `static/css/style.css` — add `.auth-success`, mirroring the
  existing `.auth-error` rule but using `--accent` / `--accent-light`

## Files to change

- `app.py` — accept POST on `/register`, add validation and the create/redirect
  flow; pass `registered` through to the login template
- `database/db.py` — add `get_user_by_email()` and `create_user()`
- `templates/register.html` — sticky form values
- `templates/login.html` — success banner
- `static/css/style.css` — `.auth-success`

## Files to create

None.

## New dependencies

No new dependencies. `flask` and `werkzeug` are already in `requirements.txt`;
`generate_password_hash` is already imported in `database/db.py`.

## Validation rules

Applied in this order; the first failure re-renders the form with a single
error message.

| Field    | Rule                                                     | Error message                                   |
| -------- | -------------------------------------------------------- | ----------------------------------------------- |
| all      | `name`, `email`, `password` all present after `.strip()`  | `All fields are required.`                       |
| name     | 2–60 characters after stripping                           | `Name must be between 2 and 60 characters.`      |
| email    | contains a single `@` with text either side, max 120 chars | `Please enter a valid email address.`            |
| password | at least 8 characters (not stripped)                      | `Password must be at least 8 characters.`        |
| email    | not already present in `users`                            | `An account with that email already exists.`     |

Emails are stored lowercased and stripped so the `UNIQUE` constraint behaves
case-insensitively. Name is stored stripped.

## Rules for implementation

- No SQLAlchemy or ORMs — `sqlite3` only
- Parameterised queries only; never build SQL with string formatting or f-strings
- Passwords hashed with `werkzeug.security.generate_password_hash` — the plain
  password is never stored, logged or passed to the template
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Every connection opened via `get_db()` must be closed in a `finally` block,
  matching the existing style in `database/db.py`
- The duplicate-email check goes through `get_user_by_email()`, and the
  `sqlite3.IntegrityError` from the `UNIQUE` constraint is still caught as a
  backstop against the race between check and insert
- Do not add `session`, `secret_key`, `login_required` or logout wiring — that
  is Step 3
- Do not touch the landing page, terms, privacy or the placeholder routes

## Definition of done

- [ ] `python app.py` starts with no errors and `/register` renders as before
- [ ] Submitting a valid name, email and password creates exactly one row in
      `users` and redirects to `/login?registered=1`
- [ ] The login page shows a success banner after that redirect, and shows
      nothing extra when visited directly at `/login`
- [ ] The stored `password_hash` is a werkzeug hash, not the plain password
      (verify with `sqlite3 expense_tracker.db "SELECT email, password_hash FROM users"`)
- [ ] Registering with an email that already exists (e.g. `demo@spendly.com`)
      re-renders the form with `An account with that email already exists.` and
      creates no new row
- [ ] `DEMO@spendly.com` is also rejected as a duplicate (case-insensitive)
- [ ] A password shorter than 8 characters is rejected with the password error
      and creates no row
- [ ] A malformed email such as `abc` is rejected with the email error
- [ ] After any rejection the name and email fields are still filled in and the
      password field is empty
- [ ] Restarting the app does not duplicate or wipe registered users
