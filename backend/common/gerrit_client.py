import requests
import json
import os
from backend.common.environment_constants import (
    GERRIT_URL,
    GERRIT_USER,
    GERRIT_HTTP_PASS,
)


class GerritClient:
    def __init__(self):
        """Initializes the GerritClient instance and sets up the requests session."""
        self.base_url = os.environ.get(GERRIT_URL)
        self._username = os.environ.get(GERRIT_USER)
        self._http_password = os.environ.get(GERRIT_HTTP_PASS)

        if not self.base_url:
            raise ValueError(
                "Gerrit base URL not found in environment variable: GERRIT_URL"
            )
        if not self._username:
            raise ValueError(
                "Gerrit username not found in environment variable: GERRIT_USER. Authentication is required."
            )
        if not self._http_password:
            raise ValueError(
                "Gerrit http password not found in environment variable: GERRIT_HTTP_PASS. Authentication is required."
            )

        self.session = requests.Session()
        self.session.auth = (self._username, self._http_password)

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

    def get_projects(self):
        """
        Query the /projects/ endpoint.

        Returns:
            dict: A dictionary where keys are project names and values are ProjectInfo objects.
        """
        resp = self.session.get(f"{self.base_url}/projects/")
        resp.raise_for_status()
        text = resp.text.lstrip(")]}'\n")
        return json.loads(text)

    def get_change_by_change_id(self, change_id):
        """
        Query the /changes/{change_id} endpoint to retrieve information about a specific change.

        Args:
            change_id (str): The ID of the change to query.

        Returns:
            dict: A ChangeInfo dictionary containing details of the change.
        """
        if not change_id:
            raise ValueError("change_id can not be None.")
        resp = self.session.get(f"{self.base_url}/changes/{change_id}")
        resp.raise_for_status()
        text = resp.text.lstrip(")]}'\n")
        return json.loads(text)
