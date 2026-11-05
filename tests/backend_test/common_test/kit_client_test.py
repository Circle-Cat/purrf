import unittest
from unittest.mock import MagicMock, patch

from backend.common.exceptions import RateLimitedError
from backend.common.kit_client import KitApiError, KitClient, TagResult


def _response(status, payload=None, text=""):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload if payload is not None else {}
    resp.text = text
    return resp


class KitClientTest(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()
        patcher = patch.dict("os.environ", {"KIT_API_KEY": "k"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = KitClient(logger=MagicMock(), session=self.session)

    def test_missing_key_fails_on_use_not_on_construction(self):
        with patch.dict("os.environ", {}, clear=True):
            client = KitClient(logger=MagicMock(), session=self.session)
            with self.assertRaises(KitApiError):
                client.list_draft_broadcasts()
        self.session.request.assert_not_called()

    def test_sends_api_key_header(self):
        self.session.request.return_value = _response(
            200, {"broadcasts": [], "pagination": {"has_next_page": False}}
        )
        self.client.list_draft_broadcasts()
        _, kwargs = self.session.request.call_args
        self.assertEqual(kwargs["headers"]["X-Kit-Api-Key"], "k")

    def test_tag_by_email_not_found(self):
        self.session.request.return_value = _response(404, {"errors": ["Not Found"]})
        self.assertEqual(
            self.client.tag_subscriber_by_email(7, "a@b.org"),
            TagResult(False, None, None),
        )

    def test_tag_by_email_found_returns_state(self):
        self.session.request.return_value = _response(
            201, {"subscriber": {"id": 9, "state": "cancelled"}}
        )
        self.assertEqual(
            self.client.tag_subscriber_by_email(7, "a@b.org"),
            TagResult(True, 9, "cancelled"),
        )

    def test_429_raises_rate_limited(self):
        self.session.request.return_value = _response(429, text="slow down")
        with self.assertRaises(RateLimitedError):
            self.client.get_broadcast(1)

    def test_422_raises_kit_api_error_with_body(self):
        self.session.request.return_value = _response(
            422, text='{"errors":["Broadcast has already been sent."]}'
        )
        with self.assertRaises(KitApiError) as ctx:
            self.client.update_broadcast(1, {})
        self.assertEqual(ctx.exception.status, 422)
        self.assertIn("already been sent", ctx.exception.body)

    def test_delete_broadcast_tolerates_404(self):
        self.session.request.return_value = _response(404)
        self.client.delete_broadcast(1)

    def test_list_tag_names_paginates(self):
        self.session.request.side_effect = [
            _response(
                200,
                {
                    "tags": [{"name": "a"}],
                    "pagination": {"has_next_page": True, "end_cursor": "c1"},
                },
            ),
            _response(
                200, {"tags": [{"name": "b"}], "pagination": {"has_next_page": False}}
            ),
        ]
        self.assertEqual(self.client.list_tag_names(), {"a", "b"})
        self.assertEqual(
            self.session.request.call_args_list[1].kwargs["params"],
            {"per_page": 1000, "after": "c1"},
        )

    def test_list_draft_broadcasts_pages_and_keeps_only_drafts(self):
        self.session.request.side_effect = [
            _response(
                200,
                {
                    "broadcasts": [
                        {"id": 1, "status": "draft"},
                        {"id": 2, "status": "completed"},
                    ],
                    "pagination": {"has_next_page": True, "end_cursor": "c1"},
                },
            ),
            _response(
                200,
                {
                    "broadcasts": [
                        {"id": 3, "status": "scheduled"},
                        {"id": 4, "status": "draft"},
                    ],
                    "pagination": {"has_next_page": False},
                },
            ),
        ]
        got = self.client.list_draft_broadcasts()
        self.assertEqual([b["id"] for b in got], [1, 4])
        calls = self.session.request.call_args_list
        self.assertEqual(calls[0].args[1], "https://api.kit.com/v4/broadcasts")
        self.assertEqual(calls[1].kwargs["params"], {"per_page": 1000, "after": "c1"})


if __name__ == "__main__":
    unittest.main()
