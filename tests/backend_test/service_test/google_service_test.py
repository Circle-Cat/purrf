import unittest
from datetime import datetime, timezone
from http import HTTPStatus
from unittest import TestCase, main
from unittest.mock import AsyncMock, MagicMock

from googleapiclient.errors import HttpError

from backend.common.exceptions import MeetingGoneError
from backend.service.google_service import GoogleService
from backend.utils.retry_utils import RetryUtils


def make_http_error(status: int, reason: str = "error") -> HttpError:
    """Build an HttpError carrying a given HTTP status, as googleapiclient raises."""
    return HttpError(
        resp=MagicMock(status=status),
        content=f'{{"error": {{"message": "{reason}"}}}}'.encode(),
    )


class TestGoogleService(TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_google_chat_client = MagicMock()
        self.mock_google_people_client = MagicMock()
        self.mock_google_workspaceevents_client = MagicMock()
        self.mock_google_calendar_client = MagicMock()
        self.mock_meet_spaces_client = MagicMock()
        self.mock_retry_utils = MagicMock()
        self.mock_retry_utils.get_retry_on_transient.side_effect = lambda fn: fn()

        self.service = GoogleService(
            logger=self.mock_logger,
            google_chat_client=self.mock_google_chat_client,
            google_people_client=self.mock_google_people_client,
            google_workspaceevents_client=self.mock_google_workspaceevents_client,
            google_calendar_client=self.mock_google_calendar_client,
            retry_utils=self.mock_retry_utils,
            meet_spaces_client=self.mock_meet_spaces_client,
            meet_conference_records_client=MagicMock(),
        )

    def test_get_chat_spaces_success_single_page(self):
        """
        Tests successful retrieval of chat spaces from a single API page.
        """
        mock_response = {
            "spaces": [
                {"name": "spaces/space1", "displayName": "Space Name 1"},
                {"name": "spaces/space2", "displayName": "Space Name 2"},
            ],
            "nextPageToken": None,
        }
        self.mock_google_chat_client.spaces.return_value.list.return_value.execute.return_value = mock_response

        result = self.service.get_chat_spaces(space_type="SPACE")

        expected_result = {
            "space1": "Space Name 1",
            "space2": "Space Name 2",
        }
        self.assertEqual(result, expected_result)
        self.mock_google_chat_client.spaces.return_value.list.assert_called_once_with(
            filter='space_type = "SPACE"',
            pageToken=None,
        )
        self.mock_google_chat_client.spaces.return_value.list.return_value.execute.assert_called_once()
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()

    def test_get_chat_spaces_success_multiple_pages(self):
        """
        Tests successful retrieval of chat spaces spanning multiple API pages.
        """
        mock_response_page1 = {
            "spaces": [
                {"name": "spaces/space1", "displayName": "Space Name 1"},
            ],
            "nextPageToken": "next_page_token_123",
        }
        mock_response_page2 = {
            "spaces": [
                {"name": "spaces/space2", "displayName": "Space Name 2"},
            ],
            "nextPageToken": None,
        }

        execute_mock = MagicMock(side_effect=[mock_response_page1, mock_response_page2])
        self.mock_google_chat_client.spaces.return_value.list.return_value.execute = (
            execute_mock
        )

        result = self.service.get_chat_spaces(space_type="ROOM")

        expected_result = {
            "space1": "Space Name 1",
            "space2": "Space Name 2",
        }
        self.assertEqual(result, expected_result)

        list_mock = self.mock_google_chat_client.spaces.return_value.list
        self.assertEqual(list_mock.call_count, 2)
        self.assertEqual(execute_mock.call_count, 2)
        self.assertEqual(self.mock_retry_utils.get_retry_on_transient.call_count, 2)

    def test_get_chat_spaces_api_error_raises_runtime_error(self):
        """
        Tests that a RuntimeError is raised when the API call fails.
        """
        test_exception = Exception("API is down")
        self.mock_retry_utils.get_retry_on_transient.side_effect = test_exception

        with self.assertRaises(RuntimeError):
            self.service.get_chat_spaces(space_type="SPACE")

        self.mock_logger.error.assert_called_once()

    def test_get_chat_spaces_missing_spaces_field_raises_value_error(self):
        """
        Tests that a ValueError is raised if the 'spaces' field is missing from the API response.
        """
        mock_response = {"nextPageToken": None}
        self.mock_google_chat_client.spaces.return_value.list.return_value.execute.return_value = mock_response

        with self.assertRaises(ValueError):
            self.service.get_chat_spaces(space_type="SPACE")

    def test_list_directory_all_people_ldap_success_single_page(self):
        """
        Tests successful retrieval of directory people from a single API page.
        """
        mock_response = {
            "people": [
                {
                    "emailAddresses": [
                        {
                            "metadata": {"source": {"id": "123"}},
                            "value": "user1@example.com",
                        }
                    ]
                },
                {
                    "emailAddresses": [
                        {
                            "metadata": {"source": {"id": "456"}},
                            "value": "user2@example.com",
                        }
                    ]
                },
            ],
            "nextPageToken": None,
        }
        self.mock_google_people_client.people.return_value.listDirectoryPeople.return_value.execute.return_value = mock_response

        result = self.service.list_directory_all_people_ldap()

        expected_result = {
            "123": "user1",
            "456": "user2",
        }
        self.assertEqual(result, expected_result)
        self.mock_google_people_client.people.return_value.listDirectoryPeople.assert_called_once_with(
            readMask="emailAddresses",
            sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"],
            pageToken=None,
        )
        self.mock_google_people_client.people.return_value.listDirectoryPeople.return_value.execute.assert_called_once()
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()

    def test_list_directory_all_people_ldap_success_multiple_pages(self):
        """
        Tests successful retrieval of directory people spanning multiple API pages.
        """
        mock_response_page1 = {
            "people": [
                {
                    "emailAddresses": [
                        {
                            "metadata": {"source": {"id": "123"}},
                            "value": "user1@example.com",
                        }
                    ]
                }
            ],
            "nextPageToken": "next_page_token_abc",
        }
        mock_response_page2 = {
            "people": [
                {
                    "emailAddresses": [
                        {
                            "metadata": {"source": {"id": "456"}},
                            "value": "user2@example.com",
                        }
                    ]
                }
            ],
            "nextPageToken": None,
        }

        execute_mock = MagicMock(side_effect=[mock_response_page1, mock_response_page2])
        self.mock_google_people_client.people.return_value.listDirectoryPeople.return_value.execute = execute_mock

        result = self.service.list_directory_all_people_ldap()

        expected_result = {
            "123": "user1",
            "456": "user2",
        }
        self.assertEqual(result, expected_result)

        list_mock = (
            self.mock_google_people_client.people.return_value.listDirectoryPeople
        )
        self.assertEqual(list_mock.call_count, 2)
        self.assertEqual(execute_mock.call_count, 2)
        self.assertEqual(self.mock_retry_utils.get_retry_on_transient.call_count, 2)

    def test_list_directory_all_people_ldap_api_error_raises_runtime_error(self):
        """
        Tests that a RuntimeError is raised when the API call fails.
        """
        test_exception = Exception("API is down")
        self.mock_retry_utils.get_retry_on_transient.side_effect = test_exception

        with self.assertRaises(RuntimeError):
            self.service.list_directory_all_people_ldap()

        self.mock_logger.error.assert_called_once()

    def test_list_directory_all_people_ldap_missing_people_field(self):
        """
        Tests retrieval when API response contains an empty 'people' list.
        """
        mock_response = {"people": [], "nextPageToken": None}
        self.mock_google_people_client.people.return_value.listDirectoryPeople.return_value.execute.return_value = mock_response

        result = self.service.list_directory_all_people_ldap()

        self.assertEqual(result, {})

    def test_list_directory_all_people_ldap_handles_malformed_data(self):
        """
        Tests that malformed or incomplete person data in the response is handled gracefully.
        """
        mock_response = {
            "people": [
                # Valid person
                {
                    "emailAddresses": [
                        {
                            "metadata": {"source": {"id": "123"}},
                            "value": "user1@example.com",
                        }
                    ]
                },
                # Person with no emailAddresses
                {"resourceName": "people/c2"},
                # Person with empty emailAddresses list
                {"emailAddresses": []},
                # Person with email but no source id
                {
                    "emailAddresses": [
                        {"metadata": {"source": {}}, "value": "user2@example.com"}
                    ]
                },
                # Person with id but no email value
                {"emailAddresses": [{"metadata": {"source": {"id": "456"}}}]},
                # Person with invalid email value
                {
                    "emailAddresses": [
                        {
                            "metadata": {"source": {"id": "789"}},
                            "value": "user3_no_at_sign",
                        }
                    ]
                },
            ],
            "nextPageToken": None,
        }
        self.mock_google_people_client.people.return_value.listDirectoryPeople.return_value.execute.return_value = mock_response

        result = self.service.list_directory_all_people_ldap()

        # Only the valid person should be in the result
        expected_result = {"123": "user1"}
        self.assertEqual(result, expected_result)

    def test_fetch_messages_by_spaces_id_paginated_success_single_page(self):
        """
        Tests successful retrieval of messages from a single API page.
        """
        space_id = "test_space"
        mock_response = {
            "messages": [
                {"name": "messages/msg1", "text": "Hello"},
                {"name": "messages/msg2", "text": "World"},
            ],
            "nextPageToken": None,
        }
        (
            self.mock_google_chat_client.spaces.return_value.messages.return_value.list.return_value.execute.return_value
        ) = mock_response

        result_generator = self.service.fetch_messages_by_spaces_id_paginated(space_id)
        all_messages = list(result_generator)

        expected_messages = [
            [
                {"name": "messages/msg1", "text": "Hello"},
                {"name": "messages/msg2", "text": "World"},
            ]
        ]
        self.assertEqual(all_messages, expected_messages)

        list_mock = (
            self.mock_google_chat_client.spaces.return_value.messages.return_value.list
        )
        list_mock.assert_called_once_with(
            parent=f"spaces/{space_id}",
            pageSize=500,
            pageToken=None,
        )
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()

    def test_fetch_messages_by_spaces_id_paginated_success_multiple_pages(self):
        """
        Tests successful retrieval of messages spanning multiple API pages.
        """
        space_id = "test_space"
        mock_response_page1 = {
            "messages": [{"name": "messages/msg1", "text": "Page 1"}],
            "nextPageToken": "next_page_token_xyz",
        }
        mock_response_page2 = {
            "messages": [{"name": "messages/msg2", "text": "Page 2"}],
            "nextPageToken": None,
        }

        execute_mock = MagicMock(side_effect=[mock_response_page1, mock_response_page2])
        (
            self.mock_google_chat_client.spaces.return_value.messages.return_value.list.return_value.execute
        ) = execute_mock

        result_generator = self.service.fetch_messages_by_spaces_id_paginated(space_id)
        all_messages = list(result_generator)

        expected_messages = [
            [{"name": "messages/msg1", "text": "Page 1"}],
            [{"name": "messages/msg2", "text": "Page 2"}],
        ]
        self.assertEqual(all_messages, expected_messages)

        list_mock = (
            self.mock_google_chat_client.spaces.return_value.messages.return_value.list
        )
        self.assertEqual(list_mock.call_count, 2)
        self.assertEqual(execute_mock.call_count, 2)
        self.assertEqual(self.mock_retry_utils.get_retry_on_transient.call_count, 2)

    def test_fetch_messages_by_spaces_id_paginated_no_messages(self):
        """
        Tests retrieval when a space has no messages.
        """
        space_id = "empty_space"
        mock_response = {"messages": [], "nextPageToken": None}
        (
            self.mock_google_chat_client.spaces.return_value.messages.return_value.list.return_value.execute.return_value
        ) = mock_response

        result_generator = self.service.fetch_messages_by_spaces_id_paginated(space_id)
        all_messages = list(result_generator)

        self.assertEqual(all_messages, [[]])
        list_mock = (
            self.mock_google_chat_client.spaces.return_value.messages.return_value.list
        )
        list_mock.assert_called_once_with(
            parent=f"spaces/{space_id}", pageSize=500, pageToken=None
        )
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()

    def test_fetch_messages_by_spaces_id_paginated_api_error(self):
        """
        Tests that a RuntimeError is raised when the API call fails.
        """
        space_id = "error_space"
        test_exception = Exception("API is down")
        self.mock_retry_utils.get_retry_on_transient.side_effect = test_exception

        with self.assertRaises(RuntimeError):
            list(self.service.fetch_messages_by_spaces_id_paginated(space_id))

        self.mock_logger.error.assert_called_once()

    def test_get_ldap_by_id_success(self):
        """
        Tests successful retrieval of an LDAP for a given user ID.
        """
        user_id = "12345"
        mock_response = {"emailAddresses": [{"value": "test.user@example.com"}]}
        execute_mock = (
            self.mock_google_people_client.people.return_value.get.return_value.execute
        )
        execute_mock.return_value = mock_response

        result = self.service.get_ldap_by_id(user_id)

        self.assertEqual(result, "test.user")
        self.mock_google_people_client.people.return_value.get.assert_called_once_with(
            resourceName=f"people/{user_id}", personFields="emailAddresses"
        )
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()
        self.mock_logger.info.assert_called_once_with(
            f"Retrieved LDAP 'test.user' for ID '{user_id}'."
        )

    def test_get_ldap_by_id_no_email_found(self):
        """
        Tests the case where the user profile has no email addresses.
        """
        user_id = "67890"
        mock_response = {"emailAddresses": []}
        execute_mock = (
            self.mock_google_people_client.people.return_value.get.return_value.execute
        )
        execute_mock.return_value = mock_response

        result = self.service.get_ldap_by_id(user_id)

        self.assertIsNone(result)
        self.mock_logger.warning.assert_called_once_with(
            f"No email found for person ID: {user_id}."
        )

    def test_get_ldap_by_id_api_error(self):
        """
        Tests that a RuntimeError is raised when the API call fails.
        """
        user_id = "error_user"
        test_exception = Exception("API is down")
        self.mock_retry_utils.get_retry_on_transient.side_effect = test_exception

        with self.assertRaises(RuntimeError) as cm:
            self.service.get_ldap_by_id(user_id)

        self.assertIn(
            f"Unexpected error fetching profile for user {user_id}", str(cm.exception)
        )
        self.mock_logger.error.assert_called_once()

    def test_get_ldap_by_id_malformed_email(self):
        """
        Tests handling of a profile with a malformed email address (no '@').
        """
        user_id = "malformed_email_user"
        mock_response = {"emailAddresses": [{"value": "test.user.example.com"}]}
        execute_mock = (
            self.mock_google_people_client.people.return_value.get.return_value.execute
        )
        execute_mock.return_value = mock_response

        result = self.service.get_ldap_by_id(user_id)

        self.assertIsNone(result)
        self.mock_logger.warning.assert_called_once_with(
            f"No email found for person ID: {user_id}."
        )

    def test_get_ldap_by_id_empty_email_value(self):
        """
        Tests handling of a profile with an empty email value.
        """
        user_id = "empty_email_user"
        mock_response = {"emailAddresses": [{"value": ""}]}
        execute_mock = (
            self.mock_google_people_client.people.return_value.get.return_value.execute
        )
        execute_mock.return_value = mock_response

        result = self.service.get_ldap_by_id(user_id)

        self.assertIsNone(result)
        self.mock_logger.warning.assert_called_once_with(
            f"No email found for person ID: {user_id}."
        )

    def test_get_ldap_by_id_no_email_addresses_field(self):
        """
        Tests handling of a profile response missing the 'emailAddresses' field.
        """
        user_id = "no_email_field_user"
        mock_response = {"resourceName": f"people/{user_id}"}
        execute_mock = (
            self.mock_google_people_client.people.return_value.get.return_value.execute
        )
        execute_mock.return_value = mock_response

        result = self.service.get_ldap_by_id(user_id)

        self.assertIsNone(result)
        self.mock_logger.warning.assert_called_once_with(
            f"No email found for person ID: {user_id}."
        )

    def test_renew_subscription_success(self):
        """
        Tests successful renewal of a subscription.
        """
        subscription_name = "subscriptions/test-sub-123"
        mock_response = {"name": subscription_name, "state": "ACTIVE"}
        execute_mock = self.mock_google_workspaceevents_client.subscriptions.return_value.patch.return_value.execute
        execute_mock.return_value = mock_response

        response = self.service.renew_subscription(subscription_name)

        self.assertEqual(response, mock_response)
        self.mock_google_workspaceevents_client.subscriptions.return_value.patch.assert_called_once_with(
            name=subscription_name,
            updateMask="ttl",
            body={"ttl": {"seconds": 0}},
        )
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()
        self.mock_logger.info.assert_called_once_with(
            "Renew subscription response: %s", mock_response
        )

    def test_renew_subscription_api_error(self):
        """
        Tests that a RuntimeError is raised when the subscription renewal API call fails.
        """
        subscription_name = "subscriptions/test-sub-456"
        test_exception = Exception("API is down")
        self.mock_retry_utils.get_retry_on_transient.side_effect = test_exception

        with self.assertRaises(RuntimeError) as cm:
            self.service.renew_subscription(subscription_name)

        self.assertIn(
            f"Failed to renew subscription '{subscription_name}'", str(cm.exception)
        )
        self.mock_logger.error.assert_called_once()

    def test_batch_delete_google_meetings_success(self):
        """Test batch deletion returns succeeded event IDs when all requests succeed."""
        mock_batch = MagicMock()
        self.mock_google_calendar_client.new_batch_http_request.return_value = (
            mock_batch
        )

        result = self.service.batch_delete_google_meetings(
            ["event-1", "event-2"], calendar_id="cal-mentorship"
        )

        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            mock_batch.execute
        )
        self.assertEqual(result, (["event-1", "event-2"], []))

    def test_batch_delete_google_meetings_execute_error(self):
        """Test batch deletion returns all event IDs as failed when the batch request fails."""
        mock_batch = MagicMock()
        self.mock_google_calendar_client.new_batch_http_request.return_value = (
            mock_batch
        )
        self.mock_retry_utils.get_retry_on_transient.side_effect = Exception("fail")

        result = self.service.batch_delete_google_meetings(
            ["event-1"], calendar_id="cal-mentorship"
        )

        self.assertEqual(result, ([], ["event-1"]))

    def test_batch_delete_google_meetings_partial_failure(self):
        """Test batch deletion returns failed event IDs without raising."""
        mock_batch = MagicMock()

        def add(request, request_id):
            if request_id == "event-2":
                callback = self.mock_google_calendar_client.new_batch_http_request.call_args.kwargs[
                    "callback"
                ]
                callback(request_id, None, Exception("fail"))

        self.mock_google_calendar_client.new_batch_http_request.return_value = (
            mock_batch
        )
        mock_batch.add.side_effect = add

        result = self.service.batch_delete_google_meetings(
            ["event-1", "event-2"], calendar_id="cal-mentorship"
        )

        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            mock_batch.execute
        )
        self.assertEqual(result, (["event-1"], ["event-2"]))

    def _batch_with_callback(self, responses):
        """Wire a mocked batch whose ``add`` replays ``{event_id: exception}``.

        ``responses`` maps an event id to the exception googleapiclient would
        hand the callback for it (``None`` for a successful delete). Ids absent
        from the mapping get no callback at all.
        """
        mock_batch = MagicMock()
        self.mock_google_calendar_client.new_batch_http_request.return_value = (
            mock_batch
        )

        def add(request, request_id):
            if request_id not in responses:
                return
            callback = self.mock_google_calendar_client.new_batch_http_request.call_args.kwargs[
                "callback"
            ]
            callback(request_id, None, responses[request_id])

        mock_batch.add.side_effect = add
        return mock_batch

    def test_batch_delete_google_meetings_counts_already_gone_as_succeeded(self):
        """An event deleted outside Purrf is already in the desired end state.

        Calendar answers 404/410 for it. Reporting that as a failure would keep
        the row in ``meeting_log`` forever, since the caller only clears the
        ids it is told succeeded — leaving a meeting the UI can never remove.
        """
        for status in (HTTPStatus.NOT_FOUND, HTTPStatus.GONE):
            with self.subTest(status=status):
                self._batch_with_callback({"event-2": make_http_error(status)})

                result = self.service.batch_delete_google_meetings(
                    ["event-1", "event-2"], calendar_id="cal-mentorship"
                )

                self.assertEqual(result, (["event-1", "event-2"], []))

    def test_batch_delete_google_meetings_keeps_forbidden_as_failed(self):
        """Only 'already gone' is forgiven — a 403 is still a real failure."""
        self._batch_with_callback({
            "event-2": make_http_error(HTTPStatus.FORBIDDEN, "forbidden")
        })

        result = self.service.batch_delete_google_meetings(
            ["event-1", "event-2"], calendar_id="cal-mentorship"
        )

        self.assertEqual(result, (["event-1"], ["event-2"]))

    def test_batch_delete_google_meetings_execute_error_keeps_reported_results(self):
        """A batch-level error must not retract per-event verdicts already given.

        googleapiclient invokes the callback as each sub-response is parsed, so
        an error part-way through leaves some events already deleted. Marking
        the whole chunk failed would strand those deletions: gone from Calendar,
        still shown by Purrf.
        """
        self._batch_with_callback({"event-1": None})
        self.mock_retry_utils.get_retry_on_transient.side_effect = Exception("network")

        result = self.service.batch_delete_google_meetings(
            ["event-1", "event-2"], calendar_id="cal-mentorship"
        )

        self.assertEqual(result, (["event-1"], ["event-2"]))

    def test_batch_delete_google_meetings_uses_the_given_calendar(self):
        """Deletes must target the caller's calendar, never "primary".

        The ids come from this environment's own database; aiming them at the
        shared primary calendar is what let a non-prod delete remove a prod
        event. A wrong calendar answers 404, which this method (correctly)
        counts as deleted — so the mistake leaves no trace in the logs.
        """
        mock_batch = MagicMock()
        self.mock_google_calendar_client.new_batch_http_request.return_value = (
            mock_batch
        )

        self.service.batch_delete_google_meetings(
            ["event-1"], calendar_id="cal-mentorship"
        )

        kwargs = self._calendar_events().delete.call_args.kwargs
        self.assertEqual(kwargs["calendarId"], "cal-mentorship")
        self.assertEqual(kwargs["eventId"], "event-1")

    def test_batch_delete_google_meetings_requires_a_calendar_id(self):
        """Same no-default rule as insert, on the path automation drives."""
        with self.assertRaises(TypeError):
            self.service.batch_delete_google_meetings(["event-1"])

    def _calendar_events(self):
        """The mocked Calendar ``events()`` resource."""
        return self.mock_google_calendar_client.events.return_value

    def _insert_meeting(self, event_id="evt-1", calendar_id="cal-mentorship"):
        """Call insert_google_meeting with fixed, uninteresting meeting details."""
        return self.service.insert_google_meeting(
            summary="Mentorship: A / B",
            start_time=datetime(2026, 8, 1, 1, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 1, 1, 45, tzinfo=timezone.utc),
            attendees_emails=["a@example.com", "b@example.com"],
            request_id="req-1",
            calendar_id=calendar_id,
            event_id=event_id,
        )

    def test_insert_google_meeting_requires_a_calendar_id(self):
        """calendar_id has no default: omitting it must fail loudly.

        A default of "primary" would silently write to the impersonated
        account's own calendar, which is the cross-environment leak this
        parameter exists to close. A TypeError at the call site is the desired
        outcome.
        """
        with self.assertRaises(TypeError):
            self.service.insert_google_meeting(
                summary="Mentorship: A / B",
                start_time=datetime(2026, 8, 1, 1, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 8, 1, 1, 45, tzinfo=timezone.utc),
                attendees_emails=["a@example.com"],
                request_id="req-1",
            )

    def test_insert_google_meeting_success(self):
        """Test a created event is returned as-is and requests a Meet conference."""
        expected = {"id": "evt-1", "hangoutLink": "https://meet.google.com/a-b-c"}
        self._calendar_events().insert.return_value.execute.return_value = expected

        result = self._insert_meeting()

        self.assertEqual(result, expected)
        kwargs = self._calendar_events().insert.call_args.kwargs
        self.assertEqual(kwargs["calendarId"], "cal-mentorship")
        self.assertEqual(kwargs["conferenceDataVersion"], 1)
        self.assertEqual(kwargs["sendUpdates"], "all")
        self.assertEqual(kwargs["body"]["id"], "evt-1")
        self._calendar_events().get.assert_not_called()

    def test_insert_google_meeting_recovers_event_when_our_id_already_exists(self):
        """A 409 on an id we minted means an earlier attempt already created it.

        The insert is retried on transient errors, so a lost response leaves the
        event created (invitations already sent) while the client sees a failure.
        The re-send then collides with itself. Fetching the event back turns that
        into the success it actually was, instead of an orphan on the calendar
        that Purrf has no record of.
        """
        existing = {"id": "evt-1", "status": "confirmed", "hangoutLink": "link"}
        self._calendar_events().insert.return_value.execute.side_effect = (
            make_http_error(HTTPStatus.CONFLICT, "duplicate")
        )
        self._calendar_events().get.return_value.execute.return_value = existing

        result = self._insert_meeting()

        self.assertEqual(result, existing)
        self._calendar_events().get.assert_called_once_with(
            calendarId="cal-mentorship", eventId="evt-1"
        )

    def test_insert_google_meeting_raises_when_recovered_event_is_cancelled(self):
        """A 409 whose event is cancelled is not a meeting we can hand back."""
        self._calendar_events().insert.return_value.execute.side_effect = (
            make_http_error(HTTPStatus.CONFLICT, "duplicate")
        )
        self._calendar_events().get.return_value.execute.return_value = {
            "id": "evt-1",
            "status": "cancelled",
        }

        with self.assertRaises(RuntimeError):
            self._insert_meeting()

    def test_insert_google_meeting_raises_on_conflict_without_event_id(self):
        """Without an id of our own there is nothing to recover — stay a failure."""
        self._calendar_events().insert.return_value.execute.side_effect = (
            make_http_error(HTTPStatus.CONFLICT, "duplicate")
        )

        with self.assertRaises(RuntimeError):
            self._insert_meeting(event_id=None)

        self._calendar_events().get.assert_not_called()

    def test_insert_google_meeting_raises_on_non_conflict_http_error(self):
        """A 400 stays a failure and must not trigger a recovery fetch."""
        self._calendar_events().insert.return_value.execute.side_effect = (
            make_http_error(HTTPStatus.BAD_REQUEST, "invalid")
        )

        with self.assertRaises(RuntimeError):
            self._insert_meeting()

        self._calendar_events().get.assert_not_called()


class UpdateGoogleMeetingTest(TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_google_calendar_client = MagicMock()
        self.mock_retry_utils = MagicMock()
        self.mock_retry_utils.get_retry_on_transient.side_effect = lambda fn: fn()

        self.service = GoogleService(
            logger=self.mock_logger,
            google_chat_client=MagicMock(),
            google_people_client=MagicMock(),
            google_workspaceevents_client=MagicMock(),
            google_calendar_client=self.mock_google_calendar_client,
            retry_utils=self.mock_retry_utils,
            meet_spaces_client=MagicMock(),
            meet_conference_records_client=MagicMock(),
        )

    def test_patches_only_start_end_and_attendees(self):
        patch_call = self.mock_google_calendar_client.events.return_value.patch
        patch_call.return_value.execute.return_value = {
            "id": "evt-1",
            "hangoutLink": "https://meet.google.com/abc-defg-hij",
            "created": "2026-08-01T00:00:00Z",
            "conferenceData": {"conferenceId": "abc-defg-hij", "entryPoints": []},
        }
        start = datetime(2026, 8, 7, 21, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 7, 21, 45, tzinfo=timezone.utc)

        self.service.update_google_meeting(
            "evt-1", start, end, ["ana@example.com"], calendar_id="cal-interview"
        )

        _, kwargs = patch_call.call_args
        self.assertEqual(kwargs["calendarId"], "cal-interview")
        self.assertEqual(kwargs["eventId"], "evt-1")
        self.assertEqual(kwargs["sendUpdates"], "all")
        # conferenceData must be absent — touching it would replace the Meet
        # link, invalidating the one already mailed to the candidate.
        self.assertNotIn("conferenceData", kwargs["body"])
        self.assertEqual(set(kwargs["body"]), {"start", "end", "attendees"})
        self.assertEqual(kwargs["body"]["attendees"], [{"email": "ana@example.com"}])

    def test_requires_a_calendar_id(self):
        """No default here either, and this path is the dangerous one.

        Unlike a delete, a patch aimed at the wrong calendar does not quietly
        404: if the id exists there it moves that event and mails everyone the
        change. Silent corruption, not a silent no-op.
        """
        with self.assertRaises(TypeError):
            self.service.update_google_meeting(
                "evt-1",
                datetime(2026, 8, 7, tzinfo=timezone.utc),
                datetime(2026, 8, 7, tzinfo=timezone.utc),
                [],
            )

    def test_a_missing_event_raises_meeting_gone(self):
        patch_call = self.mock_google_calendar_client.events.return_value.patch
        patch_call.return_value.execute.side_effect = make_http_error(
            HTTPStatus.NOT_FOUND
        )
        with self.assertRaises(MeetingGoneError):
            self.service.update_google_meeting(
                "evt-1",
                datetime(2026, 8, 7, tzinfo=timezone.utc),
                datetime(2026, 8, 7, tzinfo=timezone.utc),
                [],
                calendar_id="cal-interview",
            )

    def test_a_deleted_event_raises_meeting_gone(self):
        patch_call = self.mock_google_calendar_client.events.return_value.patch
        patch_call.return_value.execute.side_effect = make_http_error(HTTPStatus.GONE)
        with self.assertRaises(MeetingGoneError):
            self.service.update_google_meeting(
                "evt-1",
                datetime(2026, 8, 7, tzinfo=timezone.utc),
                datetime(2026, 8, 7, tzinfo=timezone.utc),
                [],
                calendar_id="cal-interview",
            )

    def test_any_other_failure_raises_runtime_error(self):
        patch_call = self.mock_google_calendar_client.events.return_value.patch
        patch_call.return_value.execute.side_effect = RuntimeError("boom")
        with self.assertRaises(RuntimeError):
            self.service.update_google_meeting(
                "evt-1",
                datetime(2026, 8, 7, tzinfo=timezone.utc),
                datetime(2026, 8, 7, tzinfo=timezone.utc),
                [],
                calendar_id="cal-interview",
            )


class TestGoogleServiceMeet(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_logger = MagicMock()
        self.mock_meet_spaces_client = AsyncMock()
        self.retry_utils = RetryUtils()

        self.service = GoogleService(
            logger=self.mock_logger,
            google_chat_client=MagicMock(),
            google_people_client=MagicMock(),
            google_workspaceevents_client=MagicMock(),
            google_calendar_client=MagicMock(),
            retry_utils=self.retry_utils,
            meet_spaces_client=self.mock_meet_spaces_client,
            meet_conference_records_client=MagicMock(),
        )

    async def test_get_meet_space_name_success(self):
        """Returns the internal space resource name resolved from a meeting code."""
        mock_space = MagicMock()
        mock_space.name = "spaces/INTERNALID123"
        self.mock_meet_spaces_client.get_space.return_value = mock_space

        result = await self.service.get_meet_space_name("abc-def-ghi")

        self.assertEqual(result, "spaces/INTERNALID123")
        self.mock_meet_spaces_client.get_space.assert_called_once_with(
            name="spaces/abc-def-ghi"
        )

    async def test_get_meet_space_name_api_error_raises_runtime_error(self):
        """Raises RuntimeError and logs error when get_space fails."""
        self.mock_meet_spaces_client.get_space.side_effect = Exception("API error")

        with self.assertRaises(RuntimeError) as cm:
            await self.service.get_meet_space_name("abc-def-ghi")

        self.assertIn("abc-def-ghi", str(cm.exception))
        self.mock_logger.error.assert_called_once()

    async def test_update_meet_space_type_to_open_success(self):
        """Calls update_space with OPEN access type and correct space name."""
        from google.apps import meet_v2

        self.mock_meet_spaces_client.update_space.return_value = None

        await self.service.update_meet_space_type_to_open("spaces/INTERNALID123")

        self.mock_meet_spaces_client.update_space.assert_called_once()
        call_kwargs = self.mock_meet_spaces_client.update_space.call_args.kwargs
        request = call_kwargs["request"]
        self.assertEqual(request.space.name, "spaces/INTERNALID123")
        self.assertEqual(
            request.space.config.access_type,
            meet_v2.SpaceConfig.AccessType.OPEN,
        )
        self.assertEqual(list(request.update_mask.paths), ["config.access_type"])
        self.mock_logger.info.assert_called_once()

    async def test_update_meet_space_type_to_open_api_error_raises_runtime_error(self):
        """Raises RuntimeError and logs error when update_space fails."""
        self.mock_meet_spaces_client.update_space.side_effect = Exception("403 denied")

        with self.assertRaises(RuntimeError) as cm:
            await self.service.update_meet_space_type_to_open("spaces/INTERNALID123")

        self.assertIn("spaces/INTERNALID123", str(cm.exception))
        self.mock_logger.error.assert_called_once()


class TestGoogleServiceMeetConferenceRecords(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_logger = MagicMock()
        self.mock_meet_spaces_client = AsyncMock()
        self.mock_meet_conference_records_client = AsyncMock()

        self.service = GoogleService(
            logger=self.mock_logger,
            google_chat_client=MagicMock(),
            google_people_client=MagicMock(),
            google_workspaceevents_client=MagicMock(),
            google_calendar_client=MagicMock(),
            retry_utils=MagicMock(),
            meet_spaces_client=self.mock_meet_spaces_client,
            meet_conference_records_client=self.mock_meet_conference_records_client,
        )

    async def test_list_conferences_by_meeting_code_filters_on_code_and_window(self):
        """The code and both window bounds all reach the Meet filter string."""
        mock_record = MagicMock()
        mock_record.name = "conferenceRecords/rec1"
        mock_record.space = "spaces/abc-defg-hij"
        mock_record.start_time.isoformat.return_value = "2026-04-07T10:05:00+00:00"
        mock_record.end_time.isoformat.return_value = "2026-04-07T11:00:00+00:00"

        async def _pager():
            yield mock_record

        self.mock_meet_conference_records_client.list_conference_records.return_value = _pager()

        result = await self.service.list_conferences_by_meeting_code(
            "abc-defg-hij",
            "2026-04-07T07:00:00+00:00",
            "2026-04-07T14:00:00+00:00",
        )

        request = (
            self.mock_meet_conference_records_client.list_conference_records.call_args
        ).kwargs["request"]
        self.assertIn('space.meeting_code="abc-defg-hij"', request.filter)
        self.assertIn('start_time>="2026-04-07T07:00:00+00:00"', request.filter)
        self.assertIn('start_time<="2026-04-07T14:00:00+00:00"', request.filter)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "conferenceRecords/rec1")
        self.assertEqual(result[0]["space"], "spaces/abc-defg-hij")

    async def test_list_conferences_by_meeting_code_empty_pager_returns_empty_list(self):
        async def _pager():
            return
            yield

        self.mock_meet_conference_records_client.list_conference_records.return_value = _pager()

        result = await self.service.list_conferences_by_meeting_code(
            "abc-defg-hij", "2026-04-07T07:00:00+00:00", "2026-04-07T14:00:00+00:00"
        )

        self.assertEqual(result, [])

    async def test_list_conferences_by_meeting_code_drops_still_running_records(self):
        """A conference in progress has no endTime. This method filters on
        start_time, so it CAN be handed one -- and the attendance sweep,
        which selects meetings up to three hours ahead of now, meets them
        routinely. Emitting it as end_time="" would
        blow up the first isoparse downstream, so it is dropped here. The ended
        record sitting alongside it must still come through."""
        ended = MagicMock()
        ended.name = "conferenceRecords/ended"
        ended.space = "spaces/abc-defg-hij"
        ended.start_time.isoformat.return_value = "2026-04-07T10:05:00+00:00"
        ended.end_time.isoformat.return_value = "2026-04-07T11:00:00+00:00"

        running = MagicMock()
        running.name = "conferenceRecords/running"
        running.space = "spaces/abc-defg-hij"
        running.start_time.isoformat.return_value = "2026-04-07T13:00:00+00:00"
        running.end_time = None

        async def _pager():
            yield ended
            yield running

        self.mock_meet_conference_records_client.list_conference_records.return_value = _pager()

        result = await self.service.list_conferences_by_meeting_code(
            "abc-defg-hij", "2026-04-07T07:00:00+00:00", "2026-04-07T14:00:00+00:00"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "conferenceRecords/ended")
        self.assertEqual(result[0]["end_time"], "2026-04-07T11:00:00+00:00")
        # Never emitted with a blank end_time -- excluded outright.
        self.assertNotIn("", [c["end_time"] for c in result])

    async def test_list_conferences_by_meeting_code_null_start_time_falls_back_to_empty_string(
        self,
    ):
        """end_time is what gates inclusion; a missing start_time still falls
        back to "" so the returned shape keeps all four keys."""
        mock_record = MagicMock()
        mock_record.name = "conferenceRecords/no-start"
        mock_record.space = "spaces/abc-defg-hij"
        mock_record.start_time = None
        mock_record.end_time.isoformat.return_value = "2026-04-07T11:00:00+00:00"

        async def _pager():
            yield mock_record

        self.mock_meet_conference_records_client.list_conference_records.return_value = _pager()

        result = await self.service.list_conferences_by_meeting_code(
            "abc-defg-hij", "2026-04-07T07:00:00+00:00", "2026-04-07T14:00:00+00:00"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["start_time"], "")
        self.assertEqual(result[0]["end_time"], "2026-04-07T11:00:00+00:00")

    async def test_fetch_participants_signed_in_user(self):
        """Returns signedin_user_id and display_name from a signed-in participant."""
        mock_p = MagicMock()
        mock_p.earliest_start_time.isoformat.return_value = "2024-01-01T10:00:00+00:00"
        mock_p.latest_end_time.isoformat.return_value = "2024-01-01T11:00:00+00:00"
        mock_p.signedin_user.user = "users/12345"
        mock_p.signedin_user.display_name = "Alice"
        mock_p.anonymous_user = None

        async def _pager():
            yield mock_p

        self.mock_meet_conference_records_client.list_participants.return_value = (
            _pager()
        )

        result = await self.service.fetch_participants_for_record(
            "conferenceRecords/abc"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["signedin_user_id"], "12345")
        self.assertEqual(result[0]["display_name"], "Alice")
        self.assertEqual(result[0]["start_time"], "2024-01-01T10:00:00+00:00")
        self.assertEqual(result[0]["end_time"], "2024-01-01T11:00:00+00:00")

    async def test_fetch_participants_anonymous_user(self):
        """Returns display_name from an anonymous participant; no signedin_user_id key."""
        mock_p = MagicMock()
        mock_p.earliest_start_time = None
        mock_p.latest_end_time = None
        mock_p.signedin_user = None
        mock_p.anonymous_user.display_name = "Anonymous Guest"

        async def _pager():
            yield mock_p

        self.mock_meet_conference_records_client.list_participants.return_value = (
            _pager()
        )

        result = await self.service.fetch_participants_for_record(
            "conferenceRecords/abc"
        )

        self.assertEqual(len(result), 1)
        self.assertNotIn("signedin_user_id", result[0])
        self.assertEqual(result[0]["display_name"], "Anonymous Guest")
        self.assertIsNone(result[0]["start_time"])
        self.assertIsNone(result[0]["end_time"])

    async def test_fetch_participants_empty_record(self):
        """Returns empty list when the conference has no participants."""

        async def _pager():
            return
            yield

        self.mock_meet_conference_records_client.list_participants.return_value = (
            _pager()
        )

        result = await self.service.fetch_participants_for_record(
            "conferenceRecords/empty"
        )

        self.assertEqual(result, [])

    async def test_fetch_participants_multiple(self):
        """Returns all participants from a mixed signed-in and anonymous conference."""
        mock_signed = MagicMock()
        mock_signed.earliest_start_time.isoformat.return_value = (
            "2024-01-01T10:00:00+00:00"
        )
        mock_signed.latest_end_time.isoformat.return_value = "2024-01-01T11:00:00+00:00"
        mock_signed.signedin_user.user = "users/99"
        mock_signed.signedin_user.display_name = "Bob"
        mock_signed.anonymous_user = None

        mock_anon = MagicMock()
        mock_anon.earliest_start_time = None
        mock_anon.latest_end_time = None
        mock_anon.signedin_user = None
        mock_anon.anonymous_user.display_name = "Unknown"

        async def _pager():
            yield mock_signed
            yield mock_anon

        self.mock_meet_conference_records_client.list_participants.return_value = (
            _pager()
        )

        result = await self.service.fetch_participants_for_record(
            "conferenceRecords/abc"
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["signedin_user_id"], "99")
        self.assertNotIn("signedin_user_id", result[1])
        self.assertEqual(result[1]["display_name"], "Unknown")


if __name__ == "__main__":
    main()
