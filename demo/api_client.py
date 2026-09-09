"""Small HTTP client for the public real estate NLP API."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


class ApiClientError(RuntimeError):
    """Raised when the API cannot return a usable response."""


class ApiClient:
    def __init__(self, base_url, timeout_seconds=30.0, metrics_token=""):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.metrics_token = metrics_token
        self.session = requests.Session()

    def search(self, query, top_k, sort_by, search_profile):
        payload = {
            "query": query,
            "top_k": top_k,
            "sort_by": None if sort_by == "relevance" else sort_by,
            "search_profile": search_profile,
        }
        return self._post("/search", payload)

    def search_profiles(self, query, top_k, sort_by):
        results = {}
        errors = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self.search, query, top_k, sort_by, profile): profile
                for profile in ("fast", "balanced", "quality")
            }
            for future in as_completed(futures):
                profile = futures[future]
                try:
                    results[profile] = future.result()
                except ApiClientError as error:
                    errors[profile] = str(error)
        return results, errors

    def record_event(self, event):
        return self._post("/demo/events", event)

    def get_listing_details(self, listing_ids):
        return self._post("/listings/details", {"listing_ids": listing_ids})

    def get_metrics(self):
        headers = {"X-Demo-Metrics-Token": self.metrics_token} if self.metrics_token else {}
        return self._get("/demo/metrics", headers=headers)

    def _post(self, path, payload):
        return self._request("post", path, json=payload)

    def _get(self, path, headers=None):
        return self._request("get", path, headers=headers)

    def _request(self, method, path, **kwargs):
        try:
            response = getattr(self.session, method)(
                f"{self.base_url}{path}",
                timeout=self.timeout_seconds,
                **kwargs,
            )
        except requests.RequestException as error:
            raise ApiClientError("The search service is unavailable.") from error

        if response.ok:
            return response.json()
        try:
            detail = response.json().get("error", {}).get("message") or response.json().get("detail")
        except ValueError:
            detail = None
        raise ApiClientError(detail or f"The search service returned HTTP {response.status_code}.")
