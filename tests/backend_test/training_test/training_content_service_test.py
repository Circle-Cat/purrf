"""Opening a content session, and serving one asset out of a package."""

import datetime
import time
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from backend.common.mentorship_enums import TrainingStatus
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_entity import TrainingEntity
from backend.entity.training_progress_entity import TrainingProgressEntity
from backend.training.training_content_service import (
    PLAYER_PATH,
    TrainingContentService,
)
from backend.training.training_content_token import (
    TOKEN_LIFETIME_SECONDS,
    InvalidContentToken,
    issue_content_token,
    verify_content_token,
)
from backend.training.training_storage import DEFAULT_CONTENT_TYPE, content_type_for

_KEY = "s3cret-signing-key"
_CONTENT_HOST = "training-content.example.org"
_TRAINING_ID = 4242
_USER_ID = 77
_OTHER_USER_ID = 999
_COURSE_ID = 9
_OLD_PREFIX = "training/9/old-package/"
_NEW_PREFIX = "training/9/new-package/"

# Spec 5.1 names the session response fields.
_CONTENT_BASE_URL_KEY = "contentBaseUrl"
_EXPIRES_AT_KEY = "expiresAt"


def _as_epoch(value):
    """The spec leaves the expiry's wire format open; accept epoch or ISO-8601."""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, datetime.datetime):
        return int(value.timestamp())
    return int(datetime.datetime.fromisoformat(str(value)).timestamp())


class TestContentTypeFor(unittest.TestCase):
    def test_web_asset_extensions_map_to_their_types(self):
        self.assertEqual(content_type_for("scormcontent/index.html"), "text/html")
        self.assertEqual(content_type_for("scormcontent/styles.css"), "text/css")
        self.assertEqual(content_type_for("scormcontent/data.json"), "application/json")
        self.assertEqual(content_type_for("assets/intro.mp4"), "video/mp4")
        self.assertEqual(content_type_for("assets/logo.svg"), "image/svg+xml")

    def test_javascript_gets_a_javascript_type(self):
        self.assertIn(
            content_type_for("scormcontent/lib/main.bundle.js"),
            {"text/javascript", "application/javascript"},
        )

    def test_web_fonts_get_a_font_type(self):
        self.assertIn(
            content_type_for("assets/fonts/inter.woff"),
            {"font/woff", "application/font-woff"},
        )
        self.assertIn(
            content_type_for("assets/fonts/inter.woff2"),
            {"font/woff2", "application/font-woff2"},
        )

    def test_a_name_with_a_space_still_gets_its_type(self):
        """Real packages ship names like this."""
        self.assertEqual(content_type_for("assets/cat mentor.jpg"), "image/jpeg")

    def test_an_unknown_extension_falls_back_to_octet_stream(self):
        self.assertEqual(content_type_for("assets/thing.xyzzy"), DEFAULT_CONTENT_TYPE)

    def test_no_extension_falls_back_to_octet_stream(self):
        self.assertEqual(content_type_for("scormcontent/LICENSE"), DEFAULT_CONTENT_TYPE)

    def test_a_bare_dot_falls_back_to_octet_stream(self):
        self.assertEqual(content_type_for("."), DEFAULT_CONTENT_TYPE)


class _ContentServiceCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()

        self.training = TrainingEntity(
            training_id=_TRAINING_ID,
            user_id=_USER_ID,
            course_id=_COURSE_ID,
            status=TrainingStatus.IN_PROGRESS,
        )
        self.course = TrainingCourseEntity(
            course_id=_COURSE_ID,
            name="Mentee Onboarding",
            storage_prefix=_OLD_PREFIX,
            entry_path="scormcontent/index.html",
            is_active=True,
        )

        self.training_repository = MagicMock()
        self.training_repository.get_training_by_id = AsyncMock(
            return_value=self.training
        )
        self.course_repository = MagicMock()
        self.course_repository.get_course_by_id = AsyncMock(return_value=self.course)

        self.progress_repository = MagicMock()
        self.progress_repository.get_by_training_id = AsyncMock(return_value=None)

        self.storage = MagicMock()
        self.storage.get = MagicMock(return_value=(b"<html></html>", "text/html"))

        self.logger = MagicMock()
        self.service = TrainingContentService(
            logger=self.logger,
            signing_key=_KEY,
            content_host=_CONTENT_HOST,
            training_repository=self.training_repository,
            training_course_repository=self.course_repository,
            training_progress_repository=self.progress_repository,
            training_storage=self.storage,
        )

    def fetched_keys(self):
        keys = []
        for call in self.storage.get.call_args_list:
            if call.args:
                keys.append(call.args[0])
            else:
                keys.append(call.kwargs.get("object_key"))
        return keys

    def token_from(self, result):
        base_url = result[_CONTENT_BASE_URL_KEY]
        head = f"https://{_CONTENT_HOST}/p/"
        self.assertTrue(base_url.startswith(head), msg=base_url)
        self.assertTrue(base_url.endswith("/"), msg=base_url)
        return base_url[len(head) : -1]

    def valid_token(self):
        token, _ = issue_content_token(_KEY, _TRAINING_ID, _USER_ID)
        return token

    def expired_token(self):
        token, _ = issue_content_token(
            _KEY,
            _TRAINING_ID,
            _USER_ID,
            now=int(time.time()) - 2 * TOKEN_LIFETIME_SECONDS,
        )
        return token


class TestOpenSession(_ContentServiceCase):
    async def test_the_session_hands_back_a_content_url_carrying_the_token(self):
        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        token = self.token_from(result)
        self.assertNotIn("/", token)
        claims = verify_content_token(_KEY, token)
        self.assertEqual(claims.training_id, _TRAINING_ID)
        self.assertEqual(claims.user_id, _USER_ID)

    async def test_the_session_reports_the_tokens_own_expiry(self):
        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        claims = verify_content_token(_KEY, self.token_from(result))
        self.assertEqual(_as_epoch(result[_EXPIRES_AT_KEY]), claims.expires_at)

    async def test_somebody_elses_assignment_cannot_be_opened(self):
        self.training.user_id = _OTHER_USER_ID

        with self.assertRaises(PermissionError):
            await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

    async def test_a_training_that_does_not_exist_cannot_be_opened(self):
        self.training_repository.get_training_by_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

    async def test_the_session_carries_the_learners_stored_progress(self):
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(
                training_id=_TRAINING_ID,
                lesson_location="Summary",
                suspend_data="blob",
                session_time_seconds=500,
            )
        )

        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        self.assertEqual(result["progress"]["lessonLocation"], "Summary")
        self.assertEqual(result["progress"]["suspendData"], "blob")
        self.assertEqual(result["progress"]["sessionTimeSeconds"], 500)

    async def test_a_session_for_an_untouched_assignment_carries_no_progress(self):
        self.progress_repository.get_by_training_id.return_value = None

        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        self.assertEqual(result["progress"], {})

    async def test_the_session_carries_the_learners_stored_score(self):
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(
                training_id=_TRAINING_ID,
                score_raw=Decimal("82.50"),
                score_min=Decimal("0.00"),
                score_max=Decimal("100.00"),
            )
        )

        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        self.assertEqual(result["progress"]["scoreRaw"], "82.50")
        self.assertEqual(result["progress"]["scoreMin"], "0.00")
        self.assertEqual(result["progress"]["scoreMax"], "100.00")

    async def test_a_session_for_a_course_with_no_score_yet_carries_none(self):
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(training_id=_TRAINING_ID)
        )

        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        self.assertIsNone(result["progress"]["scoreRaw"])


class TestReadAssetLooksThePrefixUpFresh(_ContentServiceCase):
    async def test_a_re_upload_after_minting_redirects_the_same_token(self):
        """The whole reason the prefix stays out of the token (spec 5.1)."""
        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)
        token = self.token_from(result)

        self.course.storage_prefix = _NEW_PREFIX
        await self.service.read_asset(self.session, token, "scormcontent/index.html")

        self.assertEqual(self.fetched_keys(), [_NEW_PREFIX + "scormcontent/index.html"])

    async def test_the_course_is_re_read_on_every_asset_request(self):
        token = self.valid_token()

        await self.service.read_asset(self.session, token, "scormcontent/index.html")
        await self.service.read_asset(self.session, token, "scormcontent/styles.css")

        self.assertEqual(self.course_repository.get_course_by_id.await_count, 2)


class TestReadAssetRejections(_ContentServiceCase):
    async def test_path_traversal_is_refused_without_touching_storage(self):
        for asset_path in ("../secrets", "a/../../b", "..%2f..%2fetc%2fpasswd"):
            with self.subTest(asset_path=asset_path):
                self.storage.get.reset_mock()
                with self.assertRaises(PermissionError):
                    await self.service.read_asset(
                        self.session, self.valid_token(), asset_path
                    )
                self.storage.get.assert_not_called()

    async def test_a_root_relative_path_stays_inside_the_package(self):
        """A leading slash is read against the package, not the filesystem."""
        await self.service.read_asset(self.session, self.valid_token(), "/etc/passwd")

        for key in self.fetched_keys():
            self.assertTrue(str(key).startswith(_OLD_PREFIX))

    async def test_a_course_without_a_package_is_refused(self):
        self.course.storage_prefix = None

        with self.assertRaises(FileNotFoundError):
            await self.service.read_asset(
                self.session, self.valid_token(), "scormcontent/index.html"
            )

        self.storage.get.assert_not_called()

    async def test_an_expired_token_reads_nothing(self):
        with self.assertRaises(InvalidContentToken):
            await self.service.read_asset(
                self.session, self.expired_token(), "scormcontent/index.html"
            )

        self.storage.get.assert_not_called()

    async def test_a_tampered_token_reads_nothing(self):
        token = self.valid_token()
        payload, _, signature = token.rpartition(".")
        forged = payload + "." + ("B" if signature[0] != "B" else "C") + signature[1:]

        with self.assertRaises(InvalidContentToken):
            await self.service.read_asset(
                self.session, forged, "scormcontent/index.html"
            )

        self.storage.get.assert_not_called()

    async def test_a_missing_object_is_a_clean_not_found(self):
        self.storage.get.return_value = None

        with self.assertRaises(Exception) as caught:
            await self.service.read_asset(
                self.session, self.valid_token(), "scormcontent/gone.png"
            )

        self.assertNotIsInstance(caught.exception, (TypeError, AttributeError))


class TestReadAssetLogging(_ContentServiceCase):
    """This route serves every file of every course; a course that 404s on all
    of them must leave a server-side trail, and a healthy one must not."""

    def rendered(self, mock_method):
        self.assertTrue(mock_method.called, msg="nothing was logged")
        template, *arguments = mock_method.call_args.args
        return template % tuple(arguments)

    async def test_a_missing_object_names_the_key_it_looked_for(self):
        self.storage.get.return_value = None

        with self.assertRaises(FileNotFoundError):
            await self.service.read_asset(
                self.session, self.valid_token(), "scormcontent/gone.png"
            )

        logged = self.rendered(self.logger.warning)
        self.assertIn(_OLD_PREFIX + "scormcontent/gone.png", logged)
        self.assertIn(str(_TRAINING_ID), logged)

    async def test_a_course_with_no_package_says_which_course(self):
        self.course.storage_prefix = None

        with self.assertRaises(FileNotFoundError):
            await self.service.read_asset(
                self.session, self.valid_token(), "scormcontent/index.html"
            )

        logged = self.rendered(self.logger.warning)
        self.assertIn(str(_COURSE_ID), logged)

    async def test_a_path_that_escapes_the_package_is_logged(self):
        with self.assertRaises(PermissionError):
            await self.service.read_asset(
                self.session, self.valid_token(), "../../etc/passwd"
            )

        self.assertIn("../../etc/passwd", self.rendered(self.logger.warning))

    async def test_a_course_controlled_path_cannot_forge_a_log_line(self):
        with self.assertRaises(FileNotFoundError):
            await self.service.read_asset(
                self.session,
                self.valid_token(),
                "__reserved\nWARNING forged line",
            )

        self.assertNotIn("\n", self.rendered(self.logger.warning))

    async def test_a_refused_token_is_logged_without_the_token_itself(self):
        with self.assertRaises(InvalidContentToken):
            await self.service.read_asset(
                self.session, self.expired_token(), "scormcontent/index.html"
            )

        logged = self.rendered(self.logger.info)
        self.assertNotIn(self.expired_token().split(".")[1], logged)

    async def test_a_served_asset_is_not_an_info_line_per_file(self):
        """Hundreds of files load per course; only debug may fire per file."""
        await self.service.read_asset(
            self.session, self.valid_token(), "scormcontent/index.html"
        )

        self.logger.info.assert_not_called()
        self.logger.warning.assert_not_called()
        self.assertIn("scormcontent/index.html", self.rendered(self.logger.debug))


class TestOpenSessionLogging(_ContentServiceCase):
    async def test_opening_a_course_logs_the_learner_and_the_package(self):
        """One line per opening, which is what the per-file bursts hang off."""
        await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        template, *arguments = self.logger.info.call_args.args
        logged = template % tuple(arguments)
        self.assertIn(str(_USER_ID), logged)
        self.assertIn(_OLD_PREFIX, logged)


class TestReservedPlayerPath(_ContentServiceCase):
    async def test_the_player_page_is_served_from_our_own_files(self):
        asset = await self.service.read_asset(
            self.session, self.valid_token(), PLAYER_PATH
        )

        self.assertIn(b"<html", asset.data.lower())
        self.assertEqual(asset.content_type, "text/html")
        for key in self.fetched_keys():
            self.assertFalse(str(key).startswith(_OLD_PREFIX))

    async def test_the_shim_and_the_bridge_are_served_too(self):
        for path, content_type in (
            ("__scorm12.min.js", "text/javascript"),
            ("__bridge.js", "text/javascript"),
        ):
            with self.subTest(path=path):
                asset = await self.service.read_asset(
                    self.session, self.valid_token(), path
                )
                self.assertTrue(asset.data)
                self.assertEqual(asset.content_type, content_type)

    async def test_an_unknown_reserved_name_is_still_refused(self):
        with self.assertRaises(FileNotFoundError):
            await self.service.read_asset(
                self.session, self.valid_token(), "__internal/shim.js"
            )

    async def test_a_reserved_asset_needs_no_course_package(self):
        """The player has to load even when the course row is half set up."""
        self.course.storage_prefix = None

        asset = await self.service.read_asset(
            self.session, self.valid_token(), PLAYER_PATH
        )

        self.assertTrue(asset.data)

    async def test_a_reserved_asset_is_read_from_disk_once_not_per_request(self):
        """The FORCED_COMMIT_TIME cadence (spec 6.4) means this route answers
        every ~20 seconds per learner; re-reading the same static file off
        disk on each request is pure waste."""
        first = await self.service.read_asset(
            self.session, self.valid_token(), PLAYER_PATH
        )
        second = await self.service.read_asset(
            self.session, self.valid_token(), PLAYER_PATH
        )

        self.assertIs(first.data, second.data)


class TestReadAssetResult(_ContentServiceCase):
    async def test_the_stored_bytes_and_content_type_come_back(self):
        self.storage.get.return_value = (b"body { }", "text/css")

        asset = await self.service.read_asset(
            self.session, self.valid_token(), "scormcontent/styles.css"
        )

        self.assertEqual(asset.data, b"body { }")
        self.assertEqual(asset.content_type, "text/css")

    async def test_an_unknown_extension_is_served_as_octet_stream(self):
        self.storage.get.return_value = (b"\x00\x01", DEFAULT_CONTENT_TYPE)

        asset = await self.service.read_asset(
            self.session, self.valid_token(), "scormcontent/thing.xyzzy"
        )

        self.assertEqual(asset.content_type, DEFAULT_CONTENT_TYPE)

    async def test_a_nested_asset_resolves_under_the_courses_prefix(self):
        await self.service.read_asset(
            self.session,
            self.valid_token(),
            "scormcontent/assets/abc/html5/data/js/data.js",
        )

        self.assertEqual(
            self.fetched_keys(),
            [_OLD_PREFIX + "scormcontent/assets/abc/html5/data/js/data.js"],
        )


if __name__ == "__main__":
    unittest.main()
