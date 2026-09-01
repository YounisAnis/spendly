"""Tests for the /profile date-range filter (spec: 06-date-filter-profile.md).

These tests are written against the spec's stated behaviour, not against the
implementation. They treat the profile page's HTML as a black box: they look
for text/landmarks the spec itself guarantees (the flash message copy, the
"Rs" currency prefix, the active-preset highlighting requirement, the clean
"All Time" URL requirement, and the pre-existing empty-state copy that the
spec says must not change) rather than any internal computation.

Preset tests do not hardcode the server's date-window math. Instead they seed
one expense safely *inside* each window and one safely *outside* it (using
wide day-offset margins so the assertions hold under any reasonable reading
of "this month" / "last N months"), then follow the actual preset link the
server renders and check which expense shows up.
"""
import re
from datetime import date, timedelta
from html import unescape

from flask import url_for

from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)

TODAY = date.today()


# --------------------------------------------------------------------- #
# Small HTML-scraping helpers (regex-based; no new test dependency)      #
# --------------------------------------------------------------------- #

def _html(resp):
    return resp.data.decode()


def _stat_values(html):
    """Return (total_spent, transaction_count, top_category) as rendered text.

    Relies only on the fixed, spec-mandated section order (Total Spent,
    Transactions, Top Category) that Step 5 already established and this
    step must not restructure.
    """
    vals = re.findall(r'<span class="hero-new-stat-value">(.*?)</span>', html)
    assert len(vals) == 3, "Expected exactly 3 summary stat values on the profile page"
    return vals[0].strip(), vals[1].strip(), vals[2].strip()


def _category_names(html):
    return [n.strip() for n in re.findall(r'<span class="hero-new-cat-label">(.*?)</span>', html)]


def _chip(html, label):
    """Return (href, class_attr) for the preset chip with this visible label.

    The href is HTML-unescaped (Jinja autoescapes "&" to "&amp;" in attribute
    values) so it can be fed straight back into the test client's GET.
    """
    m = re.search(
        rf'<a\s+href="([^"]*)"\s+class="([^"]*)">\s*{re.escape(label)}\s*</a>',
        html,
    )
    assert m is not None, f"Could not find a preset chip labelled {label!r}"
    return unescape(m.group(1)), m.group(2)


def _url(app, endpoint, **kwargs):
    with app.test_request_context():
        return url_for(endpoint, **kwargs)


def _iso(d):
    return d.isoformat()


# --------------------------------------------------------------------- #
# Auth guard                                                             #
# --------------------------------------------------------------------- #

class TestProfileAuthGuard:
    def test_profile_unauthenticated_redirects_to_login(self, app, client):
        resp = client.get(_url(app, "profile"))
        assert resp.status_code == 302, "Unauthenticated /profile should redirect"
        assert "/login" in resp.headers["Location"], "Should redirect to the login page"

    def test_profile_unauthenticated_with_filter_params_still_redirects(self, app, client):
        resp = client.get(
            _url(app, "profile", date_from="2026-01-01", date_to="2026-01-31")
        )
        assert resp.status_code == 302, "Auth guard must apply before the filter is processed"
        assert "/login" in resp.headers["Location"]


# --------------------------------------------------------------------- #
# No filter params -> unchanged (pre-existing) behaviour                 #
# --------------------------------------------------------------------- #

class TestProfileNoFilter:
    def test_no_query_params_shows_all_expenses_unfiltered(
        self, app, auth_client, registered_user, insert_expense
    ):
        insert_expense(
            registered_user["id"], 100.00, "Food", _iso(TODAY - timedelta(days=1)), "RECENT_ITEM"
        )
        insert_expense(
            registered_user["id"],
            200.00,
            "Bills",
            _iso(TODAY - timedelta(days=900)),
            "ANCIENT_ITEM",
        )

        resp = auth_client.get(_url(app, "profile"))
        html = _html(resp)

        assert resp.status_code == 200
        assert "RECENT_ITEM" in html, "Unfiltered view must include every expense"
        assert "ANCIENT_ITEM" in html, "Unfiltered view must include every expense"

        total_spent, transaction_count, _ = _stat_values(html)
        assert transaction_count == "2"
        assert total_spent == "Rs300.00"

    def test_no_query_params_marks_all_time_as_active(
        self, app, auth_client, registered_user, insert_expense
    ):
        insert_expense(registered_user["id"], 50.00, "Food", _iso(TODAY), "ITEM")

        resp = auth_client.get(_url(app, "profile"))
        html = _html(resp)

        href, cls = _chip(html, "All Time")
        assert "filter-chip-active" in cls, "All Time must be highlighted when no filter is active"

    def test_no_query_params_all_time_link_has_no_query_string(
        self, app, auth_client, registered_user
    ):
        resp = auth_client.get(_url(app, "profile"))
        html = _html(resp)

        href, _cls = _chip(html, "All Time")
        assert href == "/profile", (
            f"All Time preset must link to a clean /profile URL with no query params, got {href!r}"
        )


# --------------------------------------------------------------------- #
# Presets: This Month / Last 3 Months / Last 6 Months / All Time         #
# --------------------------------------------------------------------- #

class TestProfilePresets:
    def test_this_month_preset_includes_current_month_excludes_previous_month(
        self, app, auth_client, registered_user, insert_expense
    ):
        inside = date(TODAY.year, TODAY.month, 1)  # first day of this month: always in range
        outside = inside - timedelta(days=1)  # last day of previous month: never in range

        insert_expense(registered_user["id"], 40.00, "Food", _iso(inside), "IN_THIS_MONTH")
        insert_expense(registered_user["id"], 999.00, "Bills", _iso(outside), "BEFORE_THIS_MONTH")

        unfiltered = auth_client.get(_url(app, "profile"))
        href, _cls = _chip(_html(unfiltered), "This Month")

        resp = auth_client.get(href)
        html = _html(resp)

        assert resp.status_code == 200
        assert "IN_THIS_MONTH" in html
        assert "BEFORE_THIS_MONTH" not in html
        _, cls = _chip(html, "This Month")
        assert "filter-chip-active" in cls, "This Month chip must be highlighted once applied"

    def test_last_3_months_preset_includes_recent_excludes_older(
        self, app, auth_client, registered_user, insert_expense
    ):
        inside = TODAY - timedelta(days=45)  # ~1.5 months back: safely inside
        outside = TODAY - timedelta(days=150)  # ~5 months back: safely outside

        insert_expense(registered_user["id"], 40.00, "Food", _iso(inside), "IN_LAST_3_MONTHS")
        insert_expense(registered_user["id"], 999.00, "Bills", _iso(outside), "OLDER_THAN_3_MONTHS")

        unfiltered = auth_client.get(_url(app, "profile"))
        href, _cls = _chip(_html(unfiltered), "Last 3 Months")

        resp = auth_client.get(href)
        html = _html(resp)

        assert resp.status_code == 200
        assert "IN_LAST_3_MONTHS" in html
        assert "OLDER_THAN_3_MONTHS" not in html
        _, cls = _chip(html, "Last 3 Months")
        assert "filter-chip-active" in cls

    def test_last_6_months_preset_includes_recent_excludes_older(
        self, app, auth_client, registered_user, insert_expense
    ):
        inside = TODAY - timedelta(days=120)  # ~4 months back: safely inside
        outside = TODAY - timedelta(days=240)  # ~8 months back: safely outside

        insert_expense(registered_user["id"], 40.00, "Food", _iso(inside), "IN_LAST_6_MONTHS")
        insert_expense(registered_user["id"], 999.00, "Bills", _iso(outside), "OLDER_THAN_6_MONTHS")

        unfiltered = auth_client.get(_url(app, "profile"))
        href, _cls = _chip(_html(unfiltered), "Last 6 Months")

        resp = auth_client.get(href)
        html = _html(resp)

        assert resp.status_code == 200
        assert "IN_LAST_6_MONTHS" in html
        assert "OLDER_THAN_6_MONTHS" not in html
        _, cls = _chip(html, "Last 6 Months")
        assert "filter-chip-active" in cls

    def test_all_time_preset_clears_an_active_filter(
        self, app, auth_client, registered_user, insert_expense
    ):
        insert_expense(
            registered_user["id"], 40.00, "Food", _iso(TODAY), "RECENT_FOR_ALL_TIME"
        )
        insert_expense(
            registered_user["id"],
            999.00,
            "Bills",
            _iso(TODAY - timedelta(days=900)),
            "ANCIENT_FOR_ALL_TIME",
        )

        # Start from a narrow custom range that excludes the ancient expense.
        filtered = auth_client.get(
            _url(
                app,
                "profile",
                date_from=_iso(TODAY - timedelta(days=1)),
                date_to=_iso(TODAY),
            )
        )
        href, _cls = _chip(_html(filtered), "All Time")
        assert href == "/profile", "All Time must always link to a clean, param-free URL"

        resp = auth_client.get(href)
        html = _html(resp)

        assert resp.status_code == 200
        assert "RECENT_FOR_ALL_TIME" in html
        assert "ANCIENT_FOR_ALL_TIME" in html
        _, cls = _chip(html, "All Time")
        assert "filter-chip-active" in cls


# --------------------------------------------------------------------- #
# Custom range                                                           #
# --------------------------------------------------------------------- #

class TestProfileCustomRange:
    def test_custom_range_includes_only_expenses_within_bounds(
        self, app, auth_client, registered_user, insert_expense
    ):
        date_from = TODAY - timedelta(days=10)
        date_to = TODAY - timedelta(days=5)
        inside = date_from + timedelta(days=2)
        before = date_from - timedelta(days=1)
        after = date_to + timedelta(days=1)

        insert_expense(registered_user["id"], 40.00, "Food", _iso(inside), "INSIDE_CUSTOM_RANGE")
        insert_expense(registered_user["id"], 10.00, "Food", _iso(before), "BEFORE_CUSTOM_RANGE")
        insert_expense(registered_user["id"], 10.00, "Food", _iso(after), "AFTER_CUSTOM_RANGE")

        resp = auth_client.get(
            _url(app, "profile", date_from=_iso(date_from), date_to=_iso(date_to))
        )
        html = _html(resp)

        assert resp.status_code == 200
        assert "INSIDE_CUSTOM_RANGE" in html
        assert "BEFORE_CUSTOM_RANGE" not in html
        assert "AFTER_CUSTOM_RANGE" not in html

        total_spent, transaction_count, _ = _stat_values(html)
        assert transaction_count == "1"
        assert total_spent == "Rs40.00"

    def test_custom_range_bounds_are_inclusive(
        self, app, auth_client, registered_user, insert_expense
    ):
        date_from = TODAY - timedelta(days=10)
        date_to = TODAY - timedelta(days=5)

        insert_expense(
            registered_user["id"], 15.00, "Food", _iso(date_from), "ON_START_BOUNDARY"
        )
        insert_expense(
            registered_user["id"], 25.00, "Food", _iso(date_to), "ON_END_BOUNDARY"
        )

        resp = auth_client.get(
            _url(app, "profile", date_from=_iso(date_from), date_to=_iso(date_to))
        )
        html = _html(resp)

        assert "ON_START_BOUNDARY" in html, "date_from must be an inclusive lower bound"
        assert "ON_END_BOUNDARY" in html, "date_to must be an inclusive upper bound"

    def test_custom_range_marks_form_active_and_echoes_values(
        self, app, auth_client, registered_user
    ):
        date_from = _iso(TODAY - timedelta(days=30))
        date_to = _iso(TODAY)

        resp = auth_client.get(
            _url(app, "profile", date_from=date_from, date_to=date_to)
        )
        html = _html(resp)

        assert "filter-custom-active" in html, (
            "The custom-range form must be visually marked active for a range "
            "that doesn't match any preset"
        )
        assert f'value="{date_from}"' in html
        assert f'value="{date_to}"' in html


# --------------------------------------------------------------------- #
# Validation errors                                                      #
# --------------------------------------------------------------------- #

class TestProfileValidation:
    def test_date_from_after_date_to_flashes_error_and_falls_back_to_unfiltered(
        self, app, auth_client, registered_user, insert_expense
    ):
        insert_expense(
            registered_user["id"], 40.00, "Food", _iso(TODAY - timedelta(days=900)), "ANY_EXPENSE"
        )

        resp = auth_client.get(
            _url(
                app,
                "profile",
                date_from=_iso(TODAY),
                date_to=_iso(TODAY - timedelta(days=30)),
            )
        )
        html = _html(resp)

        assert resp.status_code == 200
        assert "Start date must be before end date." in html
        assert "ANY_EXPENSE" in html, "Should fall back to the unfiltered view"
        _, cls = _chip(html, "All Time")
        assert "filter-chip-active" in cls, "Fallback must present as the All Time / unfiltered state"

    def test_malformed_date_from_does_not_crash_and_falls_back_silently(
        self, app, auth_client, registered_user, insert_expense
    ):
        insert_expense(
            registered_user["id"], 40.00, "Food", _iso(TODAY - timedelta(days=900)), "ANY_EXPENSE"
        )

        resp = auth_client.get(
            _url(app, "profile", date_from="not-a-date", date_to=_iso(TODAY))
        )
        html = _html(resp)

        assert resp.status_code == 200, "A malformed date must never produce a server error"
        assert "ANY_EXPENSE" in html
        assert "Start date must be before end date." not in html, (
            "A malformed date is a silent fallback, not a validation error"
        )

    def test_malformed_date_to_does_not_crash_and_falls_back_silently(
        self, app, auth_client, registered_user, insert_expense
    ):
        insert_expense(
            registered_user["id"], 40.00, "Food", _iso(TODAY - timedelta(days=900)), "ANY_EXPENSE"
        )

        resp = auth_client.get(
            _url(app, "profile", date_from=_iso(TODAY - timedelta(days=30)), date_to="banana")
        )
        html = _html(resp)

        assert resp.status_code == 200
        assert "ANY_EXPENSE" in html

    def test_both_dates_malformed_falls_back_silently(
        self, app, auth_client, registered_user, insert_expense
    ):
        insert_expense(
            registered_user["id"], 40.00, "Food", _iso(TODAY - timedelta(days=900)), "ANY_EXPENSE"
        )

        resp = auth_client.get(_url(app, "profile", date_from="xxxx", date_to="yyyy"))
        html = _html(resp)

        assert resp.status_code == 200
        assert "ANY_EXPENSE" in html

    def test_only_date_from_present_falls_back_to_unfiltered(
        self, app, auth_client, registered_user, insert_expense
    ):
        insert_expense(
            registered_user["id"], 40.00, "Food", _iso(TODAY - timedelta(days=900)), "ANY_EXPENSE"
        )

        resp = auth_client.get(_url(app, "profile", date_from=_iso(TODAY)))
        html = _html(resp)

        assert resp.status_code == 200
        assert "ANY_EXPENSE" in html, "A lone bound is not a usable range; must fall back"

    def test_only_date_to_present_falls_back_to_unfiltered(
        self, app, auth_client, registered_user, insert_expense
    ):
        insert_expense(
            registered_user["id"], 40.00, "Food", _iso(TODAY - timedelta(days=900)), "ANY_EXPENSE"
        )

        resp = auth_client.get(_url(app, "profile", date_to=_iso(TODAY)))
        html = _html(resp)

        assert resp.status_code == 200
        assert "ANY_EXPENSE" in html


# --------------------------------------------------------------------- #
# Empty-state results                                                    #
# --------------------------------------------------------------------- #

class TestProfileEmptyState:
    def test_user_with_no_expenses_at_all_sees_zero_state(self, app, auth_client):
        resp = auth_client.get(_url(app, "profile"))
        html = _html(resp)

        assert resp.status_code == 200
        total_spent, transaction_count, _ = _stat_values(html)
        assert total_spent == "Rs0.00"
        assert transaction_count == "0"
        assert _category_names(html) == []

    def test_custom_range_with_no_matching_expenses_shows_empty_state_not_error(
        self, app, auth_client, registered_user, insert_expense
    ):
        # The user has an expense, but it falls well outside the requested range.
        insert_expense(
            registered_user["id"],
            500.00,
            "Food",
            _iso(TODAY - timedelta(days=900)),
            "OUTSIDE_SELECTED_RANGE",
        )

        resp = auth_client.get(
            _url(
                app,
                "profile",
                date_from=_iso(TODAY - timedelta(days=2)),
                date_to=_iso(TODAY),
            )
        )
        html = _html(resp)

        assert resp.status_code == 200
        assert "OUTSIDE_SELECTED_RANGE" not in html
        total_spent, transaction_count, _ = _stat_values(html)
        assert total_spent == "Rs0.00"
        assert transaction_count == "0"
        assert _category_names(html) == []


# --------------------------------------------------------------------- #
# Currency display                                                       #
# --------------------------------------------------------------------- #

class TestProfileCurrencyDisplay:
    def test_amounts_show_rs_symbol_when_a_filter_is_active(
        self, app, auth_client, registered_user, insert_expense
    ):
        insert_expense(
            registered_user["id"], 123.45, "Food", _iso(TODAY), "FILTERED_ITEM"
        )

        resp = auth_client.get(
            _url(
                app,
                "profile",
                date_from=_iso(TODAY - timedelta(days=1)),
                date_to=_iso(TODAY),
            )
        )
        html = _html(resp)

        total_spent, _tc, _top = _stat_values(html)
        assert total_spent.startswith("Rs"), "Total spent must keep the Rs prefix under a filter"
        assert total_spent == "Rs123.45"


# --------------------------------------------------------------------- #
# database/queries.py — direct unit tests                                #
# --------------------------------------------------------------------- #

class TestGetSummaryStatsDateRange:
    def test_filters_totals_to_the_given_range(self, app, registered_user, insert_expense):
        uid = registered_user["id"]
        insert_expense(uid, 100.00, "Food", _iso(TODAY), "in range")
        insert_expense(uid, 500.00, "Bills", _iso(TODAY - timedelta(days=900)), "out of range")

        stats = get_summary_stats(
            uid, date_from=_iso(TODAY - timedelta(days=1)), date_to=_iso(TODAY)
        )

        assert stats["transaction_count"] == 1
        assert stats["total_spent"] == "Rs100.00"

    def test_none_args_match_pre_existing_unfiltered_form(
        self, app, registered_user, insert_expense
    ):
        uid = registered_user["id"]
        insert_expense(uid, 100.00, "Food", _iso(TODAY), "a")
        insert_expense(uid, 200.00, "Bills", _iso(TODAY - timedelta(days=900)), "b")

        assert get_summary_stats(uid) == get_summary_stats(uid, date_from=None, date_to=None)

    def test_no_matching_rows_returns_zero_state(self, app, registered_user, insert_expense):
        uid = registered_user["id"]
        insert_expense(uid, 100.00, "Food", _iso(TODAY - timedelta(days=900)), "old")

        stats = get_summary_stats(
            uid, date_from=_iso(TODAY - timedelta(days=2)), date_to=_iso(TODAY)
        )

        assert stats["total_spent"] == "Rs0.00"
        assert stats["transaction_count"] == 0

    def test_bounds_are_inclusive(self, app, registered_user, insert_expense):
        uid = registered_user["id"]
        d = TODAY - timedelta(days=5)
        insert_expense(uid, 77.00, "Food", _iso(d), "boundary")

        stats = get_summary_stats(uid, date_from=_iso(d), date_to=_iso(d))
        assert stats["transaction_count"] == 1
        assert stats["total_spent"] == "Rs77.00"


class TestGetRecentTransactionsDateRange:
    def test_filters_to_the_given_range(self, app, registered_user, insert_expense):
        uid = registered_user["id"]
        insert_expense(uid, 10.00, "Food", _iso(TODAY), "in range")
        insert_expense(uid, 20.00, "Bills", _iso(TODAY - timedelta(days=900)), "out of range")

        txns = get_recent_transactions(
            uid, date_from=_iso(TODAY - timedelta(days=1)), date_to=_iso(TODAY)
        )

        descriptions = [t["description"] for t in txns]
        assert descriptions == ["in range"]

    def test_none_args_match_pre_existing_unfiltered_form(
        self, app, registered_user, insert_expense
    ):
        uid = registered_user["id"]
        insert_expense(uid, 10.00, "Food", _iso(TODAY), "a")
        insert_expense(uid, 20.00, "Bills", _iso(TODAY - timedelta(days=900)), "b")

        assert get_recent_transactions(uid) == get_recent_transactions(
            uid, date_from=None, date_to=None
        )

    def test_no_matching_rows_returns_empty_list(self, app, registered_user, insert_expense):
        uid = registered_user["id"]
        insert_expense(uid, 10.00, "Food", _iso(TODAY - timedelta(days=900)), "old")

        txns = get_recent_transactions(
            uid, date_from=_iso(TODAY - timedelta(days=2)), date_to=_iso(TODAY)
        )
        assert txns == []

    def test_limit_still_applies_within_a_filtered_range(
        self, app, registered_user, insert_expense
    ):
        uid = registered_user["id"]
        for i in range(3):
            insert_expense(
                uid, 10.00, "Food", _iso(TODAY - timedelta(days=i)), f"item-{i}"
            )

        txns = get_recent_transactions(
            uid,
            limit=2,
            date_from=_iso(TODAY - timedelta(days=10)),
            date_to=_iso(TODAY),
        )
        assert len(txns) == 2


class TestGetCategoryBreakdownDateRange:
    def test_filters_to_the_given_range(self, app, registered_user, insert_expense):
        uid = registered_user["id"]
        insert_expense(uid, 10.00, "Food", _iso(TODAY), "in range")
        insert_expense(uid, 20.00, "Bills", _iso(TODAY - timedelta(days=900)), "out of range")

        cats = get_category_breakdown(
            uid, date_from=_iso(TODAY - timedelta(days=1)), date_to=_iso(TODAY)
        )

        names = [c["name"] for c in cats]
        assert names == ["Food"]

    def test_none_args_match_pre_existing_unfiltered_form(
        self, app, registered_user, insert_expense
    ):
        uid = registered_user["id"]
        insert_expense(uid, 10.00, "Food", _iso(TODAY), "a")
        insert_expense(uid, 20.00, "Bills", _iso(TODAY - timedelta(days=900)), "b")

        assert get_category_breakdown(uid) == get_category_breakdown(
            uid, date_from=None, date_to=None
        )

    def test_no_matching_rows_returns_empty_list(self, app, registered_user, insert_expense):
        uid = registered_user["id"]
        insert_expense(uid, 10.00, "Food", _iso(TODAY - timedelta(days=900)), "old")

        cats = get_category_breakdown(
            uid, date_from=_iso(TODAY - timedelta(days=2)), date_to=_iso(TODAY)
        )
        assert cats == []

    def test_percentages_recompute_over_the_filtered_subset_only(
        self, app, registered_user, insert_expense
    ):
        uid = registered_user["id"]
        # Outside the range: would skew the split toward Bills if wrongly included.
        insert_expense(uid, 900.00, "Bills", _iso(TODAY - timedelta(days=900)), "out")
        # Inside the range: split evenly 50/50 between two categories.
        insert_expense(uid, 50.00, "Food", _iso(TODAY), "in-food")
        insert_expense(uid, 50.00, "Shopping", _iso(TODAY), "in-shopping")

        cats = get_category_breakdown(
            uid, date_from=_iso(TODAY - timedelta(days=1)), date_to=_iso(TODAY)
        )

        assert {c["name"] for c in cats} == {"Food", "Shopping"}
        assert sum(c["pct"] for c in cats) == 100
