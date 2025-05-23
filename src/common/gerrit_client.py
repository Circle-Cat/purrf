import os
import requests
import json
from tenacity import retry, stop_after_attempt, wait_exponential
from src.common.logger import get_logger
from src.common.environment_constants import (
    GERRIT_URL,
    GERRIT_USER,
    GERRIT_HTTP_PASS,
)

logger = get_logger()


class GerritClientFactory:
    _instance = None
    _client: "GerritClient | None" = None
    _credentials: dict[str, str] | None = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_credentials(self):
        """
        Load and cache Gerrit URL, user and HTTP password.
        """
        if self._credentials is None:
            url = os.getenv(GERRIT_URL)
            user = os.getenv(GERRIT_USER)
            pw = os.getenv(GERRIT_HTTP_PASS)

            if not all([url, user, pw]):
                missing = [
                    name
                    for name, val in [
                        (GERRIT_URL, url),
                        (GERRIT_USER, user),
                        (GERRIT_HTTP_PASS, pw),
                    ]
                    if not val
                ]
                raise ValueError(
                    f"Missing Gerrit credentials: {', '.join(missing)} must be set"
                )

            self._credentials = {
                "base_url": url.rstrip("/"),
                "username": user,
                "password": pw,
            }
            logger.info("Gerrit credentials loaded")
        return self._credentials

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=3),
    )
    def create_gerrit_client(self) -> "GerritClient":
        """
        Return a singleton GerritClient, creating it on first call.
        """
        if self._client is None:
            creds = self._get_credentials()
            logger.info("Creating GerritClient instance")
            self._client = GerritClient(
                creds["base_url"], creds["username"], creds["password"]
            )
        return self._client


class GerritClient:
    def __init__(self, base_url: str, username: str, http_password: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.auth = (username, http_password)

    @retry(
        reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=3)
    )
    def query_changes(
        self,
        queries: str | list[str],
        limit: int | None = None,
        start: int | None = None,
        no_limit: bool = False,
        options: list[str] | None = None,
        allow_incomplete: bool = False,
    ) -> list[dict]:
        """
        Query the /changes/ endpoint.

        Args:
            queries: single query string or list of Gerrit query clauses (e.g. "status:open", "project:foo")
            limit: max number of changes to return (maps to `n`); ignored if no_limit=True
            start: offset to start (maps to `S`)
            no_limit: if True, sends `no-limit=true` and ignores `limit`
            options: list of `o=` options, e.g. ["CURRENT_REVISION","DETAILED_LABELS"]
            allow_incomplete: if True, sends `allow-incomplete-results=true`

        Returns:
            A list of ChangeInfo dicts (or list-of-lists if you supplied multiple queries).
        """
        url = f"{self.base_url}/changes/"

        params = []

        if isinstance(queries, str):
            params.append(("q", queries))
        else:
            for q in queries:
                params.append(("q", q))

        if no_limit:
            params.append(("no-limit", "true"))
        elif limit is not None:
            params.append(("n", str(limit)))

        if start is not None:
            params.append(("S", str(start)))

        if allow_incomplete:
            params.append(("allow-incomplete-results", "true"))

        if options:
            for o in options:
                params.append(("o", o))

        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        text = resp.text
        if text.startswith(")]}'"):
            text = text.split("\n", 1)[1]
        return json.loads(text)
