"""Kit (ConvertKit) v4 API client for mentorship broadcasts.

Synchronous on purpose, like the other hand-written REST clients here; async
callers wrap each call in ``asyncio.to_thread`` and do their own pacing
against Kit's 120 requests / 60 s limit.
"""

import os
from typing import NamedTuple

import requests

from backend.common.environment_constants import KIT_API_KEY
from backend.common.exceptions import RateLimitedError

_BASE_URL = "https://api.kit.com/v4"
_HTTP_TIMEOUT_SECONDS = 15


class KitApiError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"Kit API error {status}: {body[:300]}")
        self.status = status
        self.body = body


class TagResult(NamedTuple):
    found: bool
    subscriber_id: int | None
    state: str | None


class KitClient:
    def __init__(self, logger, session=None):
        """
        Args:
            logger: Application logger.
            session: A requests-compatible session; tests pass a fake.
        """
        self._api_key = os.getenv(KIT_API_KEY)
        self._session = session or requests.Session()
        self._logger = logger

    def _call(self, method: str, path: str, *, json=None, params=None, ok_404=False):
        if not self._api_key:
            raise KitApiError(0, f"Missing environment variable: {KIT_API_KEY}")
        resp = self._session.request(
            method,
            f"{_BASE_URL}/{path}",
            headers={"X-Kit-Api-Key": self._api_key, "Accept": "application/json"},
            json=json,
            params=params,
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        if resp.status_code == 429:
            raise RateLimitedError("Kit rate limit reached")
        if resp.status_code == 404 and ok_404:
            return None
        if resp.status_code >= 400:
            self._logger.warning("[Kit] %s %s -> %s", method, path, resp.status_code)
            raise KitApiError(resp.status_code, resp.text)
        if resp.status_code == 204:
            return {}
        return resp.json()

    def list_tag_names(self) -> set[str]:
        names: set[str] = set()
        params = {"per_page": 1000}
        while True:
            data = self._call("GET", "tags", params=params)
            names.update(t["name"] for t in data["tags"])
            page = data.get("pagination") or {}
            if not page.get("has_next_page"):
                return names
            params = {"per_page": 1000, "after": page["end_cursor"]}

    def create_tag(self, name: str) -> int:
        return self._call("POST", "tags", json={"name": name})["tag"]["id"]

    def delete_tag(self, tag_id: int) -> None:
        self._call("DELETE", f"tags/{tag_id}", ok_404=True)

    def tag_subscriber_by_email(self, tag_id: int, email: str) -> TagResult:
        data = self._call(
            "POST",
            f"tags/{tag_id}/subscribers",
            json={"email_address": email},
            ok_404=True,
        )
        if data is None:
            return TagResult(False, None, None)
        sub = data["subscriber"]
        return TagResult(True, sub["id"], sub.get("state"))

    def create_subscriber(self, email: str, first_name: str | None) -> TagResult:
        body = {"email_address": email}
        if first_name:
            body["first_name"] = first_name
        sub = self._call("POST", "subscribers", json=body)["subscriber"]
        return TagResult(True, sub["id"], sub.get("state"))

    def list_draft_broadcasts(self) -> list[dict]:
        drafts: list[dict] = []
        params = {"per_page": 1000}
        while True:
            data = self._call("GET", "broadcasts", params=params)
            drafts.extend(b for b in data["broadcasts"] if b.get("status") == "draft")
            page = data.get("pagination") or {}
            if not page.get("has_next_page"):
                return drafts
            params = {"per_page": 1000, "after": page["end_cursor"]}

    def create_broadcast(self, body: dict) -> dict:
        return self._call("POST", "broadcasts", json=body)["broadcast"]

    def get_broadcast(self, broadcast_id: int) -> dict:
        return self._call("GET", f"broadcasts/{broadcast_id}")["broadcast"]

    def update_broadcast(self, broadcast_id: int, body: dict) -> dict:
        return self._call("PUT", f"broadcasts/{broadcast_id}", json=body)["broadcast"]

    def delete_broadcast(self, broadcast_id: int) -> None:
        self._call("DELETE", f"broadcasts/{broadcast_id}", ok_404=True)

    def get_broadcast_stats(self, broadcast_id: int) -> dict:
        return self._call("GET", f"broadcasts/{broadcast_id}/stats")["broadcast"][
            "stats"
        ]
