"""Product demo for real estate NLP search."""

from __future__ import annotations

import time
import uuid

import streamlit as st

from demo.api_client import ApiClient, ApiClientError
from demo.config import DemoSettings
from demo.presentation import (
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


def main():
    st.set_page_config(page_title="IDX Realty Search", page_icon="I", layout="wide")
    _apply_theme()
    settings = DemoSettings.from_env()
    client = ApiClient(
        settings.api_base_url,
        timeout_seconds=settings.request_timeout_seconds,
        metrics_token=settings.metrics_token,
    )
    _initialize_state()

    with st.sidebar:
        st.markdown("### IDX Realty")
        view = st.radio("Workspace", ["Search", "Metrics"], label_visibility="collapsed")
        st.divider()
        if view == "Search":
            profile = st.selectbox(
                "Search profile",
                options=["quality", "balanced", "fast"],
                format_func=PROFILE_LABELS.get,
            )
            sort_label = st.selectbox("Sort", options=list(SORT_OPTIONS))
            top_k = st.select_slider("Results", options=[5, 10, 15, 20], value=10)
            relevance_sort = SORT_OPTIONS[sort_label] == "relevance"
            compare_profiles = st.toggle(
                "Compare profiles",
                value=False,
                disabled=not relevance_sort,
                help="Profile comparison is available for relevance ranking.",
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
    st.markdown("# Find the right home")
    st.caption("Search active, compliance-screened listings.")

    with st.form("search-form", clear_on_submit=False):
        query = st.text_input(
            "What are you looking for?",
            value=st.session_state.query,
            placeholder="3 bed home in Irvine under $900k with a backyard",
        )
        submitted = st.form_submit_button("Search", type="primary", use_container_width=True)

    if submitted:
        st.session_state.query = query
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
        _render_results(selected_result)

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

    st.markdown("#### Applied search criteria")
    if hard_filters:
        st.caption("Filters")
        st.write("  ".join(f"`{value}`" for value in hard_filters))
    if preferences:
        st.caption("Preferences")
        st.write("  ".join(f"`{value}`" for value in preferences))
    st.divider()


def _render_results(result):
    results = result.get("results", [])
    if not results:
        st.info(result.get("message", "No listings match your criteria."))
        return

    st.markdown(f"#### {len(results)} listings")
    for listing in results:
        _render_listing(listing)


def _render_listing(listing):
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
        with st.expander("Listing details"):
            st.write(f"Result #{listing.get('rank')}")
            excluded = feature_labels({"matched_signals": listing.get("excluded_signals", [])})
            if excluded:
                st.caption("Not matched: " + " · ".join(excluded))


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
    third.metric("P95 API latency", _latency_label(metrics["latency_ms"]["api"]["p95"]))
    fourth.metric("Helpful rate", _percentage(metrics["satisfaction"]["helpful_rate"]))

    st.markdown("#### Search profiles")
    st.bar_chart(metrics["profile_usage"], horizontal=True)

    left, right = st.columns(2)
    with left:
        st.markdown("#### Reliability")
        st.metric("Zero-result rate", _percentage(metrics["zero_result_rate"]))
        st.metric("Profile comparisons", metrics["comparison_searches"])
    with right:
        st.markdown("#### Feedback")
        st.metric("Responses", metrics["satisfaction"]["responses"])
        st.metric("Helpful", metrics["satisfaction"]["helpful"])


def _record_event(client, event):
    try:
        client.record_event(event)
    except ApiClientError:
        return


def _initialize_state():
    st.session_state.setdefault("session_id", uuid.uuid4().hex)
    st.session_state.setdefault("query", "")
    st.session_state.setdefault("search_state", None)
    st.session_state.setdefault("feedback_submitted", False)


def _latency_label(value):
    return f"{value:.0f} ms" if value is not None else "No data"


def _percentage(value):
    return f"{value * 100:.1f}%" if value is not None else "No data"


def _apply_theme():
    st.markdown(
        """
        <style>
        .stApp { background: #f7f8f7; color: #1e2a25; }
        .block-container { max-width: 1180px; padding-top: 2.5rem; padding-bottom: 3rem; }
        [data-testid="stSidebar"] { background: #123c36; }
        [data-testid="stSidebar"] * { color: #f5fbf7; }
        [data-testid="stSidebar"] [data-baseweb="select"] * { color: #1e2a25; }
        [data-testid="stSidebar"] [data-baseweb="radio"] label { color: #f5fbf7; }
        [data-testid="stMetric"] { background: #ffffff; border: 1px solid #dce4df; border-radius: 6px; padding: 0.9rem; }
        [data-testid="stVerticalBlockBorderWrapper"] { border-color: #dce4df; border-radius: 6px; background: #ffffff; }
        .stButton > button { border-radius: 5px; background: #0d6b5f; color: #ffffff; border: 1px solid #0d6b5f; }
        .stButton > button:hover { background: #09574e; border-color: #09574e; color: #ffffff; }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
