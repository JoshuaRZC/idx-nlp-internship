"""Product web application for real estate NLP search."""

from __future__ import annotations

import time
import uuid

import streamlit as st

from web.api_client import ApiClient, ApiClientError
from web.config import WebSettings
from web.presentation import (
    applied_filter_chips,
    compact_listing_label,
    feature_labels,
    format_price,
    format_property_facts,
)


PROFILE_LABELS = {
    "fast": "Fast",
    "balanced": "Balanced",
    "quality": "Quality",
}
SORT_OPTIONS = {
    "Relevance": "relevance",
    "Price: Low to high": "price_asc",
    "Price: High to low": "price_desc",
}
PAGE_SIZE = 10


def main():
    st.set_page_config(page_title="IDX Exchange Search", page_icon="I", layout="wide")
    _apply_theme()
    _initialize_state()
    settings = WebSettings.from_env()
    client = ApiClient(
        settings.api_base_url,
        timeout_seconds=settings.request_timeout_seconds,
        metrics_token=settings.metrics_token,
        session_id=st.session_state.session_id,
    )

    with st.sidebar:
        brand_class = "brand-name" if settings.admin_mode else "brand-name public-brand"
        st.markdown(f'<div class="{brand_class}">IDX Exchange</div>', unsafe_allow_html=True)
        if settings.admin_mode:
            view = st.radio("Workspace", ["Search", "Metrics"], label_visibility="collapsed")
            st.divider()
        else:
            view = "Search"
            st.divider()
        if view == "Search":
            profile = st.selectbox(
                "Search profile",
                options=["quality", "balanced", "fast"],
                format_func=PROFILE_LABELS.get,
            )
            sort_label = st.selectbox("Sort", options=list(SORT_OPTIONS))
            if not settings.admin_mode:
                st.markdown('<div class="public-results-spacer"></div>', unsafe_allow_html=True)
            top_k = st.slider("Results", min_value=1, max_value=100, value=10, step=1)
            relevance_sort = SORT_OPTIONS[sort_label] == "relevance"
            compare_profiles = False
            if settings.admin_mode:
                compare_profiles = st.toggle(
                    "Compare profiles",
                    value=False,
                    disabled=not relevance_sort,
                    help="Compare the same query across profiles",
                    key="compare_profiles",
                )
            if not relevance_sort:
                compare_profiles = False
        else:
            profile = "quality"
            sort_label = "Relevance"
            top_k = 10
            compare_profiles = False

    if view == "Metrics":
        _render_metrics(client)
        return

    _render_search(client, profile, SORT_OPTIONS[sort_label], top_k, compare_profiles)


def _render_search(client, profile, sort_by, top_k, compare_profiles):
    st.markdown("# Intelligent Home Search")
    st.caption("Search active California listings that have passed compliance screening.")

    with st.form("search-form", clear_on_submit=False):
        st.markdown("#### Describe your ideal home")
        query = st.text_input(
            "Describe your ideal home",
            placeholder="3 bed home in Irvine under $900k with a backyard",
            label_visibility="collapsed",
            key="query_input",
        )
        submitted = st.form_submit_button("Search", type="primary", use_container_width=True)

    if submitted:
        _run_search(client, query, profile, sort_by, top_k, compare_profiles)

    state = st.session_state.search_state
    if not state:
        return

    selected_result = state["results"].get(state["selected_profile"])
    if selected_result:
        _render_query_understanding(selected_result.get("parsed_query", {}))

    if state["comparison_enabled"]:
        _render_profile_comparison(state)
    elif selected_result:
        _render_results(selected_result, client)

    for selected_profile, error in state["errors"].items():
        st.error(f"{PROFILE_LABELS[selected_profile]} search: {error}")

    if selected_result:
        _render_feedback(client, state, selected_result)


def _run_search(client, query, profile, sort_by, top_k, compare_profiles):
    if not query.strip():
        st.warning("Enter a search request to continue.")
        return

    with st.spinner("Searching listings..."):
        started_at = time.perf_counter()
        if compare_profiles:
            results, errors = client.search_profiles(query, top_k, sort_by)
        else:
            results, errors = {}, {}
            try:
                results[profile] = client.search(query, top_k, sort_by, profile)
            except ApiClientError as error:
                errors[profile] = str(error)
        client_latency_ms = round((time.perf_counter() - started_at) * 1000, 2)

    selected_result = results.get(profile)
    st.session_state.search_state = {
        "search_id": uuid.uuid4().hex,
        "query": query,
        "selected_profile": profile,
        "comparison_enabled": compare_profiles,
        "results": results,
        "errors": errors,
        "client_latency_ms": client_latency_ms,
    }
    st.session_state.feedback_submitted = False
    st.session_state.results_page = 1
    st.session_state.listing_details = {}

    if selected_result:
        _record_event(
            client,
            {
                "event_type": "search",
                "session_id": st.session_state.session_id,
                "search_profile": profile,
                "comparison_enabled": compare_profiles,
                "client_latency_ms": client_latency_ms,
                "api_latency_ms": selected_result.get("meta", {}).get("timings_ms", {}).get("total"),
                "result_count": len(selected_result.get("results", [])),
            },
        )


def _render_query_understanding(parsed_query):
    hard_filters, preferences = applied_filter_chips(parsed_query)
    if not hard_filters and not preferences:
        return

    details = []
    if hard_filters:
        details.append("Filters: " + " · ".join(hard_filters))
    if preferences:
        details.append("Preferences: " + " · ".join(preferences))
    st.caption("  |  ".join(details))


def _render_results(result, client):
    results = result.get("results", [])
    if not results:
        st.info(result.get("message", "No listings match your criteria."))
        return

    st.markdown(f"#### {len(results)} listings")
    page_count = max(1, (len(results) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(st.session_state.results_page, page_count)
    st.session_state.results_page = page

    start = (page - 1) * PAGE_SIZE
    visible_results = results[start : start + PAGE_SIZE]
    details_by_listing_id = _load_listing_details(
        client,
        [listing["listing_id"] for listing in visible_results],
    )
    for listing in visible_results:
        _render_listing(listing, details_by_listing_id.get(listing["listing_id"]))

    _render_pagination(page, page_count)


def _render_pagination(page, page_count):
    if page_count == 1:
        return
    _, previous, label, next_page, _ = st.columns([3, 1.15, 1.4, 1.15, 3])
    with previous:
        if st.button("Previous", disabled=page == 1, key="previous-page", use_container_width=True):
            st.session_state.results_page = page - 1
            st.rerun()
    with label:
        st.markdown(f'<div class="pagination-label">Page {page} of {page_count}</div>', unsafe_allow_html=True)
    with next_page:
        if st.button("Next", disabled=page == page_count, key="next-page", use_container_width=True):
            st.session_state.results_page = page + 1
            st.rerun()


def _load_listing_details(client, listing_ids):
    details = st.session_state.listing_details
    missing_ids = [listing_id for listing_id in listing_ids if listing_id not in details]
    if not missing_ids:
        return details

    try:
        response = client.get_listing_details(missing_ids)
    except ApiClientError:
        return details

    for detail in response.get("listings", []):
        details[detail["listing_id"]] = detail
    return details


def _render_listing(listing, detail):
    with st.container(border=True):
        title_column, price_column = st.columns([4, 1])
        with title_column:
            st.markdown(f"#### {compact_listing_label(listing)}")
            st.caption(format_property_facts(listing))
        with price_column:
            st.markdown(f"#### {format_price(listing.get('price'))}")
        st.write(listing.get("summary") or "Summary unavailable.")
        features = feature_labels(listing)
        if features:
            st.caption("Matched preferences: " + " · ".join(features))
        with st.expander("Listing details", expanded=False):
            st.caption(f"Listing ID: {listing.get('listing_id', 'Unavailable')}")
            left, right = st.columns(2)
            with left:
                st.caption("City")
                st.write(listing.get("city") or "Unavailable")
                st.caption("Bedrooms / bathrooms")
                st.write(
                    f"{listing.get('beds', 'Unavailable')} bd / "
                    f"{listing.get('baths', 'Unavailable')} ba"
                )
            with right:
                st.caption("List price")
                st.write(format_price(listing.get("price")))
                st.caption("Square feet")
                st.write(f"{listing['sqft']:,.0f} sqft" if listing.get("sqft") is not None else "Unavailable")
            excluded = feature_labels({"matched_signals": listing.get("excluded_signals", [])})
            if excluded:
                st.caption("Preferences not matched: " + " · ".join(excluded))
            _render_listing_description(detail)


def _render_listing_description(detail):
    if detail:
        st.caption("Full listing description")
        st.write(detail.get("listing_description") or "Description unavailable.")


def _render_profile_comparison(state):
    st.markdown("#### Profile comparison")
    columns = st.columns(3)
    for column, profile in zip(columns, ("fast", "balanced", "quality")):
        result = state["results"].get(profile)
        with column:
            st.markdown(f"##### {PROFILE_LABELS[profile]}")
            if result is None:
                st.caption("Unavailable")
                continue
            meta = result.get("meta", {})
            latency = meta.get("timings_ms", {}).get("total")
            st.metric("Search latency", f"{latency:.0f} ms" if latency is not None else "Unavailable")
            listings = result.get("results", [])
            st.caption(f"{len(listings)} listings")
            for listing in listings[:5]:
                st.markdown(f"**{listing.get('rank')}. {compact_listing_label(listing)}**")
                st.caption(f"{format_price(listing.get('price'))} · {format_property_facts(listing)}")


def _render_feedback(client, state, result):
    if st.session_state.feedback_submitted:
        return
    st.divider()
    st.caption("Were these results helpful?")
    response = st.feedback("thumbs", key=f"feedback-{state['search_id']}")
    if response is None:
        return

    _record_event(
        client,
        {
            "event_type": "feedback",
            "session_id": st.session_state.session_id,
            "search_profile": state["selected_profile"],
            "comparison_enabled": state["comparison_enabled"],
            "feedback": "helpful" if response == 1 else "not_helpful",
        },
    )
    st.session_state.feedback_submitted = True
    st.rerun()


def _render_metrics(client):
    st.markdown("# Search metrics")
    try:
        metrics = client.get_metrics()
    except ApiClientError as error:
        st.error(str(error))
        return

    first, second, third, fourth = st.columns(4)
    first.metric("Searches", metrics["query_volume"])
    second.metric("Sessions", metrics["unique_sessions"])
    third.metric("Zero-result rate", _percentage(metrics["zero_result_rate"]))
    fourth.metric("Helpful rate", _percentage(metrics["satisfaction"]["helpful_rate"]))

    st.markdown("#### Search profiles")
    st.bar_chart(metrics["profile_usage"], horizontal=True)

    st.markdown("#### Latency by profile")
    api_tab, client_tab = st.tabs(["API latency", "End-to-end latency"])
    with api_tab:
        st.dataframe(_latency_rows(metrics, "api"), use_container_width=True, hide_index=True)
    with client_tab:
        st.dataframe(_latency_rows(metrics, "client"), use_container_width=True, hide_index=True)

    left, right = st.columns(2)
    with left:
        st.metric("Profile comparisons", metrics["comparison_searches"])
    with right:
        st.metric("Feedback responses", metrics["satisfaction"]["responses"])


def _record_event(client, event):
    try:
        client.record_event(event)
    except ApiClientError:
        return


def _initialize_state():
    st.session_state.setdefault("session_id", uuid.uuid4().hex)
    st.session_state.setdefault("query_input", "")
    st.session_state.setdefault("search_state", None)
    st.session_state.setdefault("feedback_submitted", False)
    st.session_state.setdefault("results_page", 1)
    st.session_state.setdefault("listing_details", {})


def _latency_label(value):
    return f"{value:.0f} ms" if value is not None else "No data"


def _percentage(value):
    return f"{value * 100:.1f}%" if value is not None else "No data"


def _latency_rows(metrics, source):
    rows = []
    for profile in ("fast", "balanced", "quality"):
        latency = metrics["profile_latency_ms"][profile][source]
        rows.append(
            {
                "Profile": PROFILE_LABELS[profile],
                "Searches": metrics["profile_usage"][profile],
                "P50": _latency_label(latency["p50"]),
                "P90": _latency_label(latency["p90"]),
                "P95": _latency_label(latency["p95"]),
            }
        )
    return rows


def _apply_theme():
    st.markdown(
        """
        <style>
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
          background: #f4f6f8;
          color: #1f2937;
        }
        .block-container { max-width: 1180px; padding-top: 2.5rem; padding-bottom: 3rem; }
        [data-testid="stSidebar"] { background: #262b33; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] label span {
          color: #edf1f5 !important;
        }
        [data-testid="stSidebar"] .brand-name {
          color: #ffffff;
          font-size: 1.45rem;
          font-weight: 700;
          line-height: 1.2;
          margin: 0.35rem 0 1.5rem;
        }
        [data-testid="stSidebar"] .public-brand { margin-bottom: 0.8rem; }
        [data-testid="stSidebar"] [data-baseweb="select"] > div {
          background: #ffffff;
          border-color: #aeb8c4;
        }
        [data-testid="stSidebar"] [data-baseweb="select"] span {
          color: #202933 !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] hr {
          border-color: #4a5260;
        }
        [data-testid="stSidebar"] [data-testid="stTooltipIcon"] {
          position: relative;
          width: 18px;
          height: 18px;
          border: 1px solid #9aa4b2;
          border-radius: 50%;
          background: #394250;
        }
        [data-testid="stSidebar"] [data-testid="stTooltipIcon"] svg {
          opacity: 0;
        }
        [data-testid="stSidebar"] [data-testid="stTooltipIcon"]::after {
          position: absolute;
          inset: 0;
          color: #f8fafc;
          content: "?";
          font-size: 0.75rem;
          font-weight: 700;
          line-height: 16px;
          pointer-events: none;
          text-align: center;
        }
        [data-testid="stMain"] [data-testid="stMetric"] {
          background: #ffffff;
          border: 1px solid #d9dee6;
          border-radius: 6px;
          padding: 0.9rem;
        }
        [data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"] {
          border-color: #d9dee6;
          border-radius: 6px;
          background: #ffffff;
        }
        .stFormSubmitButton > button, .stButton > button {
          border-radius: 5px;
          background: #2563eb !important;
          color: #ffffff !important;
          border: 1px solid #2563eb !important;
        }
        .stFormSubmitButton > button:hover, .stButton > button:hover {
          background: #1d4ed8 !important;
          border-color: #1d4ed8 !important;
        }
        .pagination-label {
          color: #687386;
          padding-top: 0.55rem;
          text-align: center;
        }
        .public-results-spacer { height: 0.35rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
