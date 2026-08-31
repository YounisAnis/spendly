
---
name: spendly-frontend-ui
description: Use this skill for any UI or frontend work on Spendly, the personal expense tracker at github.com/YounisAnis/spendly. Trigger it whenever the user says "design the ___ page", "create UI for ___", "build a component for ___", "redesign / improve ___", "add a modal / form / card / table to ___", or names any file under templates/, static/css/, or static/js/. It produces production-ready Flask + Jinja2 + vanilla CSS + vanilla JS output that matches Spendly's existing design system exactly, with Lucide inline-SVG icons. Do NOT use this skill for backend logic, database schema, auth rules, or non-Spendly projects.
---
# Spendly — Frontend UI Designer

Generates modern, production-ready UI components and pages for **Spendly**, a personal
expense tracker. Every output must be clean, responsive, usable, and visually
indistinguishable from the pages that already exist in the repository.

**Core loop:** Read the existing code → Confirm the target → Describe the structure →
Write the code → Verify against the design system → Report what changed.

---

##  1. Stack contract (non-negotiable)

| Layer     | What Spendly uses                                                                     | Never introduce                                                 |
| --------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Templates | Flask + Jinja2, all pages`{% extends "base.html" %}`                                | React, Vue, JSX, component frameworks                           |
| Styling   | One hand-written stylesheet:`static/css/style.css`                                  | Tailwind, Bootstrap, styled-components, SCSS, new`.css` files |
| Scripting | Vanilla JS only, IIFE-wrapped                                                         | jQuery, Alpine, HTMX, npm packages, build steps                 |
| Icons     | Lucide,**inline SVG** pasted into the template                                  | Emoji, Font Awesome, icon fonts, random glyphs                  |
| Fonts     | `DM Serif Display` (headings) + `DM Sans` (body), already loaded in `base.html` | Any new webfont                                                 |

`static/css/landing.css` was merged into `style.css`. There is exactly **one**
stylesheet — append to it, do not create siblings.

---

##  2. Repository map

```
spendly/
├── app.py                    # All routes. Flask, port 5001, debug=True
├── database/
│   ├── db.py                 # get_db, init_db, seed_db, create_user, get_user_by_email
│   └── __init__.py
├── templates/
│   ├── base.html             # navbar + {% block content %} + footer + main.js
│   ├── landing.html          # hero-new, features, cta, video modal
│   ├── login.html            # auth-section pattern
│   ├── register.html         # auth-section pattern
│   ├── terms.html            # legal-section pattern
│   └── privacy.html          # legal-section pattern
├── static/
│   ├── css/style.css         # single stylesheet, section-banner comments
│   └── js/main.js            # currently empty — shared JS goes here
└── .claude/
    ├── specs/                # 01-database-setup, 02-registration, 03-login-and-logout
    └── commands/             # create-spec, seed-user, seed-expense
```

**Always read the closest existing template before writing a new one.** A new form page
copies `login.html`. A new prose page copies `terms.html`. A new marketing section
copies `landing.html`.

---

##  3. Design system (read from `style.css`, do not invent)

### Design direction

Spendly is **not** a generic blue-gradient SaaS product. It is a *warm editorial fintech*
look: off-white paper background, serif display headings, deep-green and gold accents,
hairline borders, very soft shadows. When a request says "modern SaaS", deliver modern
*Spendly* — the consistency rule always outranks a generic style label.

### Tokens — use the variables, never raw hex

```css
--ink: #0f0f0f;          --paper: #f7f6f3;        --accent: #1a472a;    /* deep green */
--ink-soft: #2d2d2d;     --paper-warm: #f0ede6;   --accent-light: #e8f0eb;
--ink-muted: #6b6b6b;    --paper-card: #ffffff;   --accent-2: #c17f24;  /* gold */
--ink-faint: #a0a0a0;                             --accent-2-light: #fdf3e3;

--danger: #c0392b;       --danger-light: #fdecea;
--border: #e4e1da;       --border-soft: #eeebe4;

--font-display: 'DM Serif Display', Georgia, serif;   /* headings only */
--font-body: 'DM Sans', system-ui, sans-serif;        /* everything else */

--max-width: 1200px;     --auth-width: 440px;
--radius-sm: 6px;        --radius-md: 12px;       --radius-lg: 20px;
```

Category chart colors already in use — reuse these before adding new ones:
`--accent` (green), `--accent-2` (gold), `#5b7fa6` (blue), `#8b5e83` (plum),
`#f59e0b` food, `#3b82f6` travel, `#8b5cf6` bills.

### Type scale

| Use                  | Family  | Size                                               | Weight   |
| -------------------- | ------- | -------------------------------------------------- | -------- |
| Page / hero title    | display | `clamp(2.5rem, 5vw, 4rem)`, `line-height: 1.1` | normal   |
| Section + card title | display | `1.2rem`–`2rem`                               | normal   |
| Body                 | body    | `1rem`, `line-height: 1.6`–`1.7`            | 400      |
| Secondary / meta     | body    | `0.9rem`, color `--ink-muted`                  | 400–500 |
| Label / badge        | body    | `0.75rem`, `letter-spacing: 0.08em`, uppercase | 600      |

Serif is reserved for headings and money figures. Never set body copy in the serif.

### Spacing and radius

Spacing is expressed in `rem` on a 0.25rem (4px) step: `0.25 · 0.5 · 0.75 · 1 · 1.25 · 1.5 · 2 · 3 · 4 · 5`. Section padding is `5rem 2rem` on desktop, `3rem 1rem` on mobile.

> Honest note: the repo is **not** strictly on an 8px grid — real values include
> `0.35rem`, `0.45rem`, `0.65rem` on badges and buttons. When editing near existing
> components, copy the neighbouring value. Only apply the clean 4/8px steps in brand-new
> sections.

Radius: `6px` buttons and inputs · `12px` cards and panels · `20px` large feature cards
· `999px` pills and badges. Shadow: `0 8px 40px rgba(0,0,0,0.06)` — one soft elevation
only, never stacked drop shadows.

### Existing component classes — reuse before creating

| Group    | Classes available                                                                                                                     |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Shell    | `.navbar` `.nav-inner` `.nav-brand` `.brand-icon` `.nav-links` `.nav-cta` `.main-content` `.footer` `.footer-inner` |
| Buttons  | `.btn-primary` (ink → green on hover) · `.btn-ghost` (outlined) · `.btn-submit` (full-width form)                            |
| Cards    | `.mock-card` `.feature-card` `.auth-card` `.hero-new-category-card`                                                           |
| Forms    | `.form-group` `.form-input` `.auth-error` `.auth-success` `.auth-switch`                                                    |
| Sections | `.hero-new` `.features` `.features-inner` `.cta-section` `.auth-section` `.legal-section`                                 |
| Modal    | `.modal-overlay` `.modal-overlay.is-open` `.modal-box` `.modal-close` `.modal-video-wrap`                                   |
| Bars     | `.hero-new-cat-row` `.hero-new-cat-track` `.hero-new-cat-bar` `.hero-new-cat-pct`                                             |

`.hero` (legacy two-column) is superseded by `.hero-new` (centered, browser-window
mockup). Build new marketing sections from `.hero-new`; leave `.hero` untouched.

### CSS authoring convention

Append a new block at the end of `style.css` using the existing banner style:

```css
/* ------------------------------------------------------------------ */
/* Dashboard — summary cards                                           */
/* ------------------------------------------------------------------ */
```

Naming is flat and prefix-scoped, not strict BEM: `.dashboard-card`,
`.dashboard-card-label`, `.dashboard-card-value`. Every class in a feature shares one
prefix. No utility-class soup, no `!important` unless overriding `.nav-*` (the one place
the repo already uses it).

---

##  4. Icon system

Lucide, delivered as **inline SVG** in the template. Inline SVG is preferred over the
CDN `<script>` because the repo's own rule is "no page libraries or dependencies".
Only reach for `<script src="https://unpkg.com/lucide@latest"></script>` + `lucide.createIcons()`
if a page needs more than ~15 distinct icons, and say so explicitly when you do.

Standard markup — copy this shape every time:

```html
<svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none"
     stroke="currentColor" stroke-width="1.75" stroke-linecap="round"
     stroke-linejoin="round" aria-hidden="true">
  <!-- lucide: wallet -->
  ...paths...
</svg>
```

```css
.icon { width: 1.125rem; height: 1.125rem; flex-shrink: 0; vertical-align: -0.15em; }
```

Rules: `stroke-width` is always `1.75`. Color always inherits via `currentColor` — never
hard-code a stroke color. Sizes are `16px` inline in text, `18px` in buttons and rows,
`24px` for feature/section icons. Decorative icons get `aria-hidden="true"`; an
icon-only button gets an `aria-label`.

### Icon vocabulary — one meaning, one icon

| Context                    | Lucide icon                                                     |
| -------------------------- | --------------------------------------------------------------- |
| Brand mark                 | `wallet` (replaces the `◈` glyph only if explicitly asked) |
| Dashboard / overview       | `layout-dashboard`                                            |
| Add expense                | `plus-circle`                                                 |
| Edit                       | `pencil`                                                      |
| Delete                     | `trash-2`                                                     |
| Filter / sort              | `sliders-horizontal`                                          |
| Date / period              | `calendar`                                                    |
| Amount / money             | `banknote`                                                    |
| Category                   | `tag`                                                         |
| Trend up (spending rose)   | `trending-up` (pair with `--danger`)                        |
| Trend down (spending fell) | `trending-down` (pair with `--accent`)                      |
| Category breakdown         | `pie-chart`                                                   |
| Profile / account          | `user-round`                                                  |
| Sign in                    | `log-in`                                                      |
| Sign out                   | `log-out`                                                     |
| Search                     | `search`                                                      |
| Close modal                | `x`                                                           |
| Success state              | `check-circle-2`                                              |
| Error state                | `alert-circle`                                                |
| Empty state                | `inbox`                                                       |
| Export / download          | `download`                                                    |

Never use an emoji as an icon. Never pick an icon that is merely decorative — if it does
not clarify the action or the data, leave it out.

---

##  5. Workflow

### Step 1 — Read before writing

Open `templates/base.html`, `static/css/style.css`, and the nearest sibling template.
Never write CSS for a component that already exists under another name.

### Step 2 — Resolve the target

Identify the page/component name, the route it belongs to, and whether it is **new** or a
**redesign**. If the route is missing from `app.py`, say so and state the one-line route
that must be added — do not silently invent backend behaviour.

### Step 3 — Ask only when genuinely blocked

Ask at most one focused question, and only if the answer changes the markup. Legitimate
blockers: the data shape is unknown, or a visual reference exists that has not been
shared ("if unclear → ask for photos of the existing design"). Otherwise proceed and
state the assumption inline.

### Step 4 — Structure before code

Write the UI Structure brief first (see §6). Structure is cheap to correct; code is not.

### Step 5 — Implement

Produce complete, paste-ready blocks per file, each with its path as a heading:
`templates/dashboard.html`, then the appended `static/css/style.css` section, then JS if
required. No pseudo-code, no `...rest of file`, no diff fragments.

### Step 6 — Verify

Run the Definition of Done checklist in §9 before responding.

### Step 7 — Report

State in two or three lines: files touched, classes added, icons used, and anything the
user still has to wire up (route, template variable, query).

---

##  6. Output contract

Every response from this skill contains these four parts, in order.

**1 · UI Structure (brief)** — layout, key sections top to bottom, and the important UX
decisions with their reasons. Six to ten lines, prose or short list. No code.

**2 · Code** — one fenced block per file, path stated above it. Clean CSS, modular
components, minimal boilerplate. Jinja blocks correct (`{% extends %}`,
`{% block title %}`, `{% block content %}`, `{% block scripts %}`).

**3 · Design quality** — three or four bullets confirming spacing, hierarchy,
card layout, colors and shadows against the tokens above.

**4 · Icons used** — the Lucide names and where each one appears.

---

##  7. Interaction patterns (reuse verbatim)

### Modal — the established pattern

Markup lives at the end of `{% block content %}`; behaviour lives in
`{% block scripts %}`, wrapped in an IIFE. Opens on trigger click, closes on the close
button **and** on overlay click. If the modal embeds media, blank the `src` on close so
playback stops. State is a single `.is-open` class toggle — never inline `style.display`.
Extend it with `Escape`-to-close and focus return to the trigger.

### Forms

`<form method="POST" action="{{ url_for('route') }}">` wrapping `.form-group` blocks
(`<label for>` + `.form-input`). Full-width `.btn-submit` at the end. First field gets
`autofocus`. Use native `required`, `type="email"`, `type="number" step="0.01"` before
reaching for JS validation. Repopulate on error: `value="{{ email or '' }}"`.

### Messages

Server errors arrive through `get_flashed_messages()` or an `error` variable and render
in `.auth-error`; confirmations render in `.auth-success`. Both sit at the top of the
card, inside it.

### Page shell

Every page extends `base.html` and sets `{% block title %}Page — Spendly{% endblock %}`.
Nav and footer are never duplicated. Auth state is available everywhere as
`is_logged_in` via the context processor.

### Responsive

Two breakpoints only — `900px` (multi-column grids collapse to one, decorative visuals
hide, actions stack and center) and `600px` (section padding drops to `3rem 1rem`,
secondary nav links hide, dense grids retune their columns). Mobile-friendly, not
mobile-first: match the existing desktop-out approach.

### Empty and loading states

Every list or chart needs a designed empty state: `inbox` icon at 24px in `--ink-faint`,
one line of `--ink-muted` copy, and a `.btn-primary` pointing at the action that fills
it. Never ship a bare empty `<table>`.

---

##  8. Screens waiting to be built

`app.py` already declares these routes as placeholders. When one of them comes up, this
is the data available.

```sql
users    (id, name, email, password_hash, created_at)
expenses (id, user_id, amount REAL, category TEXT, date TEXT, description TEXT, created_at)
```

| Route                            | Template to create    | Shape                                               |
| -------------------------------- | --------------------- | --------------------------------------------------- |
| `GET /profile`                 | `profile.html`      | `.auth-card` width, account details + edit form   |
| `GET/POST /expenses/add`       | `add_expense.html`  | Form: amount, category, date, description           |
| `GET/POST /expenses/<id>/edit` | `edit_expense.html` | Same form, prefilled                                |
| `POST /expenses/<id>/delete`   | confirm modal         | Reuse the modal pattern,`--danger` confirm        |
| Dashboard                        | `dashboard.html`    | Summary cards + category bars + recent expense list |

Dashboard composition, when asked: a row of summary cards (total this month, top
category, expense count) built on `.mock-card`; a category breakdown reusing the
`.hero-new-cat-*` bar markup; then a recent-expenses list. Currency is **PKR** —
format as `Rs 12,450` and set figures in `--font-display`.

---

##  9. Definition of done

- [ ] Template extends `base.html` and sets a `{% block title %}`
- [ ] Every color, font, radius and width comes from a CSS variable
- [ ] New CSS appended to `style.css` under a banner comment, single shared prefix
- [ ] No new stylesheet, no framework, no npm dependency
- [ ] Icons are inline Lucide SVG at stroke-width `1.75` using `currentColor`
- [ ] Headings use `--font-display`; body uses `--font-body`
- [ ] Spacing matches neighbouring components
- [ ] `900px` and `600px` breakpoints handled
- [ ] Labels bound with `for` / `id`; icon-only buttons carry `aria-label`
- [ ] JS is vanilla, IIFE-wrapped, in `{% block scripts %}` or `main.js`
- [ ] Empty state designed for every list or chart
- [ ] Only the requested files were touched

---

##  10. Avoid

Generic or dated UI — bevels, gradient buttons, heavy borders, drop-shadow stacks,
default browser form styling. Unstructured code dumps with no structure brief.
Duplicate components under new names. Raw hex where a token exists. Emoji as icons.
Inline `style=` attributes. Editing files outside the request's scope. Inventing routes,
template variables or DB columns that do not exist — name what is missing instead.

---

##  11. Repo conventions to respect

Spendly is built through spec-driven feature branches: `feature/<slug>`, spec in
`.claude/specs/NN-<slug>.md`, plan in `.claude/plans/NN-<slug>.md`, then implement,
validate against the spec, commit, PR, delete the branch. When a UI task is large enough
to need a spec, follow `.claude/commands/create-spec.md` rather than improvising.

Commit messages are scope-prefixed and lowercase: `landing: add privacy policy page and route`, `dashboard: add summary cards`.

---

##  12. Extending this skill

Keep this file the single source of truth for Spendly's frontend. When the project
changes: add new tokens to §3 only after they exist in `style.css`; add a row to the icon
table in §4 when a new action needs an icon; add a new subsection to §7 when a new
interaction pattern is introduced; move a screen out of §8 once it ships and record its
classes in §3. Never document an intention here — only what is actually in the repo.
