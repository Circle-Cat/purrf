"""Opening a content session, and serving one asset out of a package."""

import asyncio
import datetime
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import TrainingPackageState, TrainingStatus
from backend.entity.training_entity import TrainingEntity
from backend.entity.training_progress_entity import TrainingProgressEntity
from backend.training.byte_range import RangeSpec, UnsatisfiableRange
import backend.training.training_content_service as content_service_module
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
_PACKAGE_ID = 31
_PENDING_PACKAGE_ID = 32
_OLD_PREFIX = "training/9/old-package/"
_NEW_PREFIX = "training/9/new-package/"

# Stands in for the 3.7 MB MP4 the real mentee package ships.
_VIDEO_PATH = "scormcontent/assets/Mentee_Onboarding_Program_.mp4"
_VIDEO = bytes(range(256)) * 4


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
        self.training_repository = MagicMock()
        self.training_repository.get_training_by_id = AsyncMock(
            return_value=self.training
        )

        self.package = MagicMock(
            package_id=_PACKAGE_ID,
            storage_prefix=_OLD_PREFIX,
            entry_path="scormcontent/index.html",
        )
        self.pending = MagicMock(
            package_id=_PENDING_PACKAGE_ID,
            storage_prefix="training/9/staged-package/",
            entry_path="scormcontent/index.html",
        )
        # Active unless a test says otherwise: the learner's door is the only
        # one that reads this, so every other case wants it out of the way.
        self.course = MagicMock(course_id=_COURSE_ID, is_active=True)
        self.course_repository = MagicMock()
        self.course_repository.get_course_by_id = AsyncMock(return_value=self.course)

        self.package_repository = MagicMock()
        # Opening a session resolves the course's live package; serving a file
        # resolves the package the token names, which is a different question
        # the moment a replacement lands. Plain return value by default -- a
        # test that cares which slot was asked for swaps in a state-dispatching
        # side_effect of its own.
        self.package_repository.get_by_state = AsyncMock(return_value=self.package)
        self.package_repository.get_by_id = AsyncMock(return_value=self.package)

        self.progress_repository = MagicMock()
        self.progress_repository.get_by_training_id = AsyncMock(return_value=None)

        self.storage = MagicMock()
        self.storage.get = MagicMock(return_value=(b"<html></html>", "text/html"))
        self.storage.stat = MagicMock(return_value=(len(_VIDEO), "video/mp4"))
        self.storage.get_range = MagicMock(
            side_effect=lambda key, start, end: _VIDEO[start : end + 1]
        )

        self.logger = MagicMock()
        self.service = TrainingContentService(
            logger=self.logger,
            signing_key=_KEY,
            content_host=_CONTENT_HOST,
            training_repository=self.training_repository,
            training_course_repository=self.course_repository,
            training_course_package_repository=self.package_repository,
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
        base_url = result.content_base_url
        head = f"https://{_CONTENT_HOST}/p/"
        self.assertTrue(base_url.startswith(head), msg=base_url)
        self.assertTrue(base_url.endswith("/"), msg=base_url)
        return base_url[len(head) : -1]

    def valid_token(self):
        token, _ = issue_content_token(
            _KEY, _TRAINING_ID, _USER_ID, package_id=_PACKAGE_ID
        )
        return token

    def expired_token(self):
        token, _ = issue_content_token(
            _KEY,
            _TRAINING_ID,
            _USER_ID,
            package_id=_PACKAGE_ID,
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
        self.assertEqual(_as_epoch(result.expires_at), claims.expires_at)

    async def test_a_deactivated_course_is_closed_to_the_people_assigned_it(self):
        # Deactivating used to stop new assignments only, so a course turned
        # off went on serving everybody already on it.
        self.course.is_active = False

        with self.assertRaises(ConflictError) as caught:
            await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        self.assertIn("deactivated", str(caught.exception).lower())

    async def test_a_course_that_has_gone_missing_cannot_be_opened(self):
        self.course_repository.get_course_by_id = AsyncMock(return_value=None)

        with self.assertRaises(ValueError):
            await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

    async def test_somebody_elses_assignment_cannot_be_opened(self):
        self.training.user_id = _OTHER_USER_ID

        with self.assertRaises(PermissionError):
            await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

    async def test_a_course_with_a_package_but_no_entry_page_cannot_be_opened(self):
        """The player has nowhere to point, and null is not an answer for it."""
        self.package.entry_path = None

        with self.assertRaises(ValueError):
            await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

    async def test_a_training_that_does_not_exist_cannot_be_opened(self):
        self.training_repository.get_training_by_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

    async def test_a_course_with_no_live_package_cannot_be_opened(self):
        self.package_repository.get_by_state.return_value = None

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

        self.assertEqual(result.progress.lesson_location, "Summary")
        self.assertEqual(result.progress.suspend_data, "blob")
        self.assertEqual(result.progress.session_time_seconds, 500)

    async def test_a_session_for_an_untouched_assignment_carries_no_progress(self):
        self.progress_repository.get_by_training_id.return_value = None

        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        self.assertIsNone(result.progress)

    async def test_the_session_carries_the_learners_stored_score(self):
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(
                training_id=_TRAINING_ID,
                score_raw=Decimal("82.50"),
                score_min=Decimal("0.00"),
                score_max=Decimal("100.00"),
                # NOT NULL with a default, so a row read back always has one.
                # An entity built in memory does not until it is flushed.
                session_time_seconds=0,
            )
        )

        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        self.assertEqual(result.progress.score_raw, "82.50")
        self.assertEqual(result.progress.score_min, "0.00")
        self.assertEqual(result.progress.score_max, "100.00")

    async def test_a_session_for_a_course_with_no_score_yet_carries_none(self):
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(training_id=_TRAINING_ID, session_time_seconds=0)
        )

        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        self.assertIsNone(result.progress.score_raw)


class TestOpeningARunTakesOverTheAssignment(_ContentServiceCase):
    """The newest tab wins: every learner opening names a fresh run and makes
    it the one whose commits the assignment accepts."""

    async def test_the_token_names_the_run_that_now_owns_the_assignment(self):
        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        run_id = verify_content_token(_KEY, self.token_from(result)).run_id
        self.assertTrue(run_id)
        self.assertEqual(run_id, self.training.active_run_id)

    async def test_the_takeover_is_committed_after_it_is_written(self):
        owner_at_commit = []
        self.session.commit.side_effect = lambda: owner_at_commit.append(
            self.training.active_run_id
        )

        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        self.session.commit.assert_awaited_once()
        run_id = verify_content_token(_KEY, self.token_from(result)).run_id
        self.assertEqual([run_id], owner_at_commit)

    async def test_a_second_opening_takes_over_from_the_first(self):
        first = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)
        second = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        first_run = verify_content_token(_KEY, self.token_from(first)).run_id
        second_run = verify_content_token(_KEY, self.token_from(second)).run_id
        self.assertNotEqual(first_run, second_run)
        self.assertEqual(second_run, self.training.active_run_id)

    async def test_a_refused_opening_takes_nothing_over(self):
        self.training.active_run_id = "run-already-open"
        self.course.is_active = False

        with self.assertRaises(ConflictError):
            await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        self.assertEqual("run-already-open", self.training.active_run_id)
        self.session.commit.assert_not_awaited()

    async def test_an_opening_with_nothing_live_takes_nothing_over(self):
        self.training.active_run_id = "run-already-open"
        self.package_repository.get_by_state.return_value = None

        with self.assertRaises(ValueError):
            await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        self.assertEqual("run-already-open", self.training.active_run_id)
        self.session.commit.assert_not_awaited()

    async def test_a_trial_leaves_the_learners_run_in_charge(self):
        """A trial stores nothing on the row, so it has nothing to own -- and
        taking over would refuse the verifier's own learner tab for no gain."""
        self.training.active_run_id = "run-already-open"
        self.package_repository.get_by_state = AsyncMock(return_value=self.pending)

        result = await self.service.open_trial_session(
            self.session, _TRAINING_ID, _USER_ID
        )

        self.assertIsNone(verify_content_token(_KEY, self.token_from(result)).run_id)
        self.assertEqual("run-already-open", self.training.active_run_id)
        self.session.commit.assert_not_awaited()

    async def test_a_preview_names_no_run(self):
        result = await self.service.open_preview_session(
            self.session, course_id=_COURSE_ID, user_id=_USER_ID
        )

        self.assertIsNone(verify_content_token(_KEY, result.session_token).run_id)
        self.session.commit.assert_not_awaited()


class TestOpenTrialSession(_ContentServiceCase):
    async def test_the_token_names_the_staged_package(self):
        self.package_repository.get_by_state = AsyncMock(
            side_effect=lambda session, course_id, state: (
                self.pending if state is TrainingPackageState.PENDING else self.package
            )
        )

        result = await self.service.open_trial_session(
            self.session, _TRAINING_ID, _USER_ID
        )

        claims = verify_content_token(_KEY, self.token_from(result))
        self.assertEqual(claims.package_id, _PENDING_PACKAGE_ID)

    async def test_a_deactivated_course_can_still_be_trialled(self):
        # The repair sequence the trial exists for: a broken course is
        # deactivated, re-exported, re-uploaded, trialled, then turned back
        # on. Gating the staged slot on `is_active` would strand it off.
        self.course.is_active = False

        result = await self.service.open_trial_session(
            self.session, _TRAINING_ID, _USER_ID
        )

        self.assertTrue(result.content_base_url)

    async def test_a_trial_carries_no_progress_to_resume_from(self):
        """A trial is always ab initio, whatever the assignment's row holds.

        The row is keyed per assignment, not per package, so what it holds was
        written by whichever package last ran on it -- never by the staged one
        a trial opens. The finishing lesson_status is the dangerous case:
        seeded into the CMI model, the player re-sends it on its first commit
        and the staged package is stamped verified with nobody having run it.
        """
        self.package_repository.get_by_state = AsyncMock(
            side_effect=lambda session, course_id, state: (
                self.pending if state is TrainingPackageState.PENDING else self.package
            )
        )
        self.progress_repository.get_by_training_id.return_value = (
            TrainingProgressEntity(
                training_id=_TRAINING_ID,
                lesson_status="completed",
                lesson_location="Summary",
                suspend_data="blob",
                session_time_seconds=500,
            )
        )

        result = await self.service.open_trial_session(
            self.session, _TRAINING_ID, _USER_ID
        )

        self.assertIsNone(result.progress)

    async def test_a_course_with_nothing_staged_cannot_open_a_trial(self):
        self.package_repository.get_by_state = AsyncMock(return_value=None)

        with self.assertRaises(ValueError):
            await self.service.open_trial_session(self.session, _TRAINING_ID, _USER_ID)

    async def test_the_learner_endpoint_still_signs_the_live_package(self):
        self.package_repository.get_by_state = AsyncMock(
            side_effect=lambda session, course_id, state: (
                self.pending if state is TrainingPackageState.PENDING else self.package
            )
        )

        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        claims = verify_content_token(_KEY, self.token_from(result))
        self.assertEqual(claims.package_id, _PACKAGE_ID)


class TestOpenPreviewSession(_ContentServiceCase):
    async def test_a_preview_opens_the_live_package_with_no_assignment(self):
        self.package_repository.get_by_state = AsyncMock(
            return_value=MagicMock(
                package_id=42, entry_path="story.html", storage_prefix="courses/9/live"
            )
        )

        result = await self.service.open_preview_session(
            self.session, course_id=_COURSE_ID, user_id=_USER_ID
        )

        self.package_repository.get_by_state.assert_awaited_once_with(
            self.session, _COURSE_ID, TrainingPackageState.LIVE
        )
        # No assignment is read at all: a preview is not a run of anybody's course.
        self.training_repository.get_training_by_id.assert_not_awaited()
        self.progress_repository.get_by_training_id.assert_not_awaited()
        self.assertIsNone(result.progress)
        claims = verify_content_token(_KEY, result.session_token)
        self.assertIsNone(claims.training_id)
        self.assertEqual(42, claims.package_id)

    async def test_a_preview_of_a_course_with_nothing_live_is_refused(self):
        self.package_repository.get_by_state.return_value = None

        with self.assertRaises(ValueError):
            await self.service.open_preview_session(
                self.session, course_id=_COURSE_ID, user_id=_USER_ID
            )


class TestReadAssetResolvesTheTokensOwnPackage(_ContentServiceCase):
    async def test_the_prefix_comes_from_the_package_the_token_names(self):
        token = self.valid_token()

        await self.service.read_asset(self.session, token, "scormcontent/index.html")

        self.package_repository.get_by_id.assert_awaited_with(self.session, _PACKAGE_ID)
        self.assertEqual(self.fetched_keys(), [_OLD_PREFIX + "scormcontent/index.html"])

    async def test_a_replacement_does_not_redirect_a_token_at_the_new_package(self):
        """The tab has to fail visibly rather than be handed a package it
        never started: its in-memory CMI model still belongs to the old one.
        """
        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)
        token = self.token_from(result)
        # The replacement deletes the row this token names and inserts its own.
        self.package_repository.get_by_id.return_value = None
        self.package_repository.get_by_state.return_value = MagicMock(
            package_id=_PACKAGE_ID + 1,
            storage_prefix=_NEW_PREFIX,
            entry_path="scormcontent/index.html",
        )

        with self.assertRaises(FileNotFoundError):
            await self.service.read_asset(
                self.session, token, "scormcontent/index.html"
            )

        self.storage.get.assert_not_called()

    async def test_the_package_is_read_once_for_the_files_of_one_course_load(self):
        token = self.valid_token()

        await self.service.read_asset(self.session, token, "scormcontent/index.html")
        await self.service.read_asset(self.session, token, "scormcontent/styles.css")

        self.assertEqual(self.package_repository.get_by_id.await_count, 1)
        self.assertEqual(
            self.fetched_keys(),
            [
                _OLD_PREFIX + "scormcontent/index.html",
                _OLD_PREFIX + "scormcontent/styles.css",
            ],
        )


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

    async def test_a_token_whose_package_is_gone_is_refused(self):
        self.package_repository.get_by_id.return_value = None

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


class TestUnconfiguredContentHosting(_ContentServiceCase):
    """The message reaches a browser; the variable names stay in the log."""

    def unconfigured_service(self, **overrides):
        return TrainingContentService(
            logger=self.logger,
            signing_key=overrides.get("signing_key", _KEY),
            content_host=overrides.get("content_host", _CONTENT_HOST),
            training_repository=self.training_repository,
            training_course_repository=self.course_repository,
            training_course_package_repository=self.package_repository,
            training_progress_repository=self.progress_repository,
            training_storage=self.storage,
        )

    async def test_opening_a_session_names_no_environment_variable(self):
        service = self.unconfigured_service(content_host=None)

        with self.assertRaises(ValueError) as caught:
            await service.open_session(self.session, _TRAINING_ID, _USER_ID)

        self.assertNotIn("TRAINING_CONTENT_HOST", str(caught.exception))

    async def test_the_log_names_every_variable_that_is_missing(self):
        service = self.unconfigured_service(content_host=None, signing_key=None)

        with self.assertRaises(ValueError):
            await service.open_session(self.session, _TRAINING_ID, _USER_ID)

        template, *arguments = self.logger.error.call_args.args
        logged = template % tuple(arguments)
        self.assertIn("TRAINING_CONTENT_HOST", logged)
        self.assertIn("TRAINING_TOKEN_SIGNING_KEY", logged)

    async def test_reading_an_asset_without_a_signing_key_leaks_nothing(self):
        service = self.unconfigured_service(signing_key=None)

        with self.assertRaises(ValueError) as caught:
            await service.read_asset(self.session, "anything", "index.html")

        self.assertNotIn("TRAINING_TOKEN_SIGNING_KEY", str(caught.exception))


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

    async def test_a_token_whose_package_is_gone_says_which_package(self):
        """Info rather than warning: an open tab produces one of these for
        every file it still asks for after a replacement, and the answer is a
        reload rather than an investigation."""
        self.package_repository.get_by_id.return_value = None

        with self.assertRaises(FileNotFoundError):
            await self.service.read_asset(
                self.session, self.valid_token(), "scormcontent/index.html"
            )

        logged = self.rendered(self.logger.info)
        self.assertIn(str(_PACKAGE_ID), logged)

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
        result = await self.service.open_session(self.session, _TRAINING_ID, _USER_ID)

        template, *arguments = self.logger.info.call_args.args
        logged = template % tuple(arguments)
        self.assertIn(str(_USER_ID), logged)
        self.assertIn(_OLD_PREFIX, logged)
        # Pinned so a future extraction of the minting code cannot silently
        # drop the expiry off this line the way c1f6e6c7 once did: the DTO
        # and the log have to agree on the same value, not just both exist.
        self.assertIn(str(result.expires_at), logged)


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

    async def test_a_reserved_asset_needs_no_package(self):
        """The player has to load even when the package behind the token is
        gone -- it is what tells the learner to reload."""
        self.package_repository.get_by_id.return_value = None

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


class TestReadAssetRanges(_ContentServiceCase):
    """A range must cost only the bytes it names, not the whole file."""

    async def test_the_whole_object_is_never_fetched_for_a_range(self):
        """The point of the exercise: a seek into a 3.7 MB video must not pull
        3.7 MB through this process."""
        asset = await self.service.read_asset(
            self.session, self.valid_token(), _VIDEO_PATH, RangeSpec(100, 199)
        )

        self.storage.get.assert_not_called()
        self.storage.get_range.assert_called_once_with(
            _OLD_PREFIX + _VIDEO_PATH, 100, 199
        )
        self.assertEqual(asset.data, _VIDEO[100:200])

    async def test_a_range_reports_where_it_sits_in_the_whole_file(self):
        asset = await self.service.read_asset(
            self.session, self.valid_token(), _VIDEO_PATH, RangeSpec(100, 199)
        )

        self.assertEqual(asset.partial.start, 100)
        self.assertEqual(asset.partial.end, 199)
        self.assertEqual(asset.partial.total, len(_VIDEO))
        self.assertEqual(asset.content_type, "video/mp4")

    async def test_no_range_still_fetches_the_object_in_one_call(self):
        asset = await self.service.read_asset(
            self.session, self.valid_token(), _VIDEO_PATH
        )

        self.storage.get.assert_called_once()
        self.storage.get_range.assert_not_called()
        self.assertIsNone(asset.partial)

    async def test_an_open_ended_range_asks_for_the_rest_of_the_file(self):
        await self.service.read_asset(
            self.session, self.valid_token(), _VIDEO_PATH, RangeSpec(first=1000)
        )

        self.storage.get_range.assert_called_once_with(
            _OLD_PREFIX + _VIDEO_PATH, 1000, len(_VIDEO) - 1
        )

    async def test_a_suffix_range_asks_for_the_tail(self):
        await self.service.read_asset(
            self.session, self.valid_token(), _VIDEO_PATH, RangeSpec(suffix_length=16)
        )

        self.storage.get_range.assert_called_once_with(
            _OLD_PREFIX + _VIDEO_PATH, len(_VIDEO) - 16, len(_VIDEO) - 1
        )

    async def test_an_end_past_the_file_is_clamped_before_storage_sees_it(self):
        await self.service.read_asset(
            self.session, self.valid_token(), _VIDEO_PATH, RangeSpec(0, 10_000_000)
        )

        self.storage.get_range.assert_called_once_with(
            _OLD_PREFIX + _VIDEO_PATH, 0, len(_VIDEO) - 1
        )

    async def test_a_start_past_the_file_reads_nothing_at_all(self):
        with self.assertRaises(UnsatisfiableRange) as caught:
            await self.service.read_asset(
                self.session,
                self.valid_token(),
                _VIDEO_PATH,
                RangeSpec(first=len(_VIDEO)),
            )

        self.assertEqual(caught.exception.total_size, len(_VIDEO))
        self.storage.get_range.assert_not_called()
        self.storage.get.assert_not_called()

    async def test_a_missing_object_is_not_found_rather_than_a_range_error(self):
        self.storage.stat.return_value = None

        with self.assertRaises(FileNotFoundError):
            await self.service.read_asset(
                self.session, self.valid_token(), _VIDEO_PATH, RangeSpec(0, 10)
            )

    async def test_an_object_deleted_mid_request_is_not_found(self):
        """An upload replacing the package between the two storage calls."""
        self.storage.get_range.side_effect = None
        self.storage.get_range.return_value = None

        with self.assertRaises(FileNotFoundError):
            await self.service.read_asset(
                self.session, self.valid_token(), _VIDEO_PATH, RangeSpec(0, 10)
            )

    async def test_a_range_over_a_player_file_is_served_from_memory(self):
        whole = await self.service.read_asset(
            self.session, self.valid_token(), PLAYER_PATH
        )

        part = await self.service.read_asset(
            self.session, self.valid_token(), PLAYER_PATH, RangeSpec(0, 9)
        )

        self.assertEqual(part.data, whole.data[:10])
        self.assertEqual(part.partial.total, len(whole.data))
        self.storage.get.assert_not_called()
        self.storage.get_range.assert_not_called()

    async def test_an_unsatisfiable_range_over_a_player_file_is_refused(self):
        whole = await self.service.read_asset(
            self.session, self.valid_token(), PLAYER_PATH
        )

        with self.assertRaises(UnsatisfiableRange) as caught:
            await self.service.read_asset(
                self.session,
                self.valid_token(),
                PLAYER_PATH,
                RangeSpec(first=len(whole.data)),
            )

        self.assertEqual(caught.exception.total_size, len(whole.data))

    async def test_a_range_does_not_get_past_the_package_boundary(self):
        with self.assertRaises(PermissionError):
            await self.service.read_asset(
                self.session, self.valid_token(), "../secrets", RangeSpec(0, 10)
            )

        self.storage.get_range.assert_not_called()
        self.storage.stat.assert_not_called()

    async def test_a_range_does_not_get_past_an_expired_token(self):
        with self.assertRaises(InvalidContentToken):
            await self.service.read_asset(
                self.session, self.expired_token(), _VIDEO_PATH, RangeSpec(0, 10)
            )

        self.storage.stat.assert_not_called()


class TestReadAssetLeavesTheEventLoopFree(_ContentServiceCase):
    """The storage SDK is synchronous, so it must not run on the loop.

    A single course load asks for hundreds of files. Serving one of them on
    the event loop stops the process answering anything else -- including the
    other files of that same page, which is what turned the first real course
    load into a wall of 502s.
    """

    async def test_a_whole_file_read_runs_off_the_event_loop(self):
        loop_thread = threading.get_ident()
        seen = []

        def get(object_key):
            seen.append(threading.get_ident())
            return b"x", "text/css"

        self.storage.get = MagicMock(side_effect=get)

        await self.service.read_asset(self.session, self.valid_token(), "a.css")

        self.assertEqual(len(seen), 1)
        self.assertNotEqual(seen[0], loop_thread)

    async def test_a_range_read_runs_off_the_event_loop(self):
        # Both halves of a range read, because they are two separate calls
        # into the SDK and either one alone would stall the loop.
        loop_thread = threading.get_ident()
        seen = []

        def stat(object_key):
            seen.append(threading.get_ident())
            return len(_VIDEO), "video/mp4"

        def get_range(object_key, start, end):
            seen.append(threading.get_ident())
            return _VIDEO[start : end + 1]

        self.storage.stat = MagicMock(side_effect=stat)
        self.storage.get_range = MagicMock(side_effect=get_range)

        await self.service.read_asset(
            self.session, self.valid_token(), _VIDEO_PATH, RangeSpec(0, 15)
        )

        self.assertEqual(len(seen), 2)
        self.assertNotIn(loop_thread, seen)

    async def test_two_asset_reads_are_actually_in_flight_together(self):
        # The behaviour the thread assertions above exist for. A barrier is
        # the only way to state it without a sleep: if the two reads are
        # serialised, neither can ever pass it and the wait raises.
        both_here = threading.Barrier(2, timeout=5)

        def blocking_get(key):
            both_here.wait()
            return b"x", "text/css"

        self.storage.get = MagicMock(side_effect=blocking_get)
        token = self.valid_token()

        await asyncio.gather(
            self.service.read_asset(self.session, token, "a.css"),
            self.service.read_asset(self.session, token, "b.css"),
        )

        self.assertEqual(self.storage.get.call_count, 2)


class TestReadAssetUsesTheStorageExecutor(_ContentServiceCase):
    """Reads go to the executor sized for a course load, not the default one."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="storage-under-test"
        )
        self.addCleanup(self.executor.shutdown)
        self.service.storage_executor = self.executor

    async def test_a_whole_file_read_runs_on_the_storage_executor(self):
        seen = []

        def get(object_key):
            seen.append(threading.current_thread().name)
            return b"x", "text/css"

        self.storage.get = MagicMock(side_effect=get)

        await self.service.read_asset(self.session, self.valid_token(), "a.css")

        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0].startswith("storage-under-test"), msg=seen)

    async def test_both_halves_of_a_range_read_run_on_the_storage_executor(self):
        seen = []

        def stat(object_key):
            seen.append(threading.current_thread().name)
            return len(_VIDEO), "video/mp4"

        def get_range(object_key, start, end):
            seen.append(threading.current_thread().name)
            return _VIDEO[start : end + 1]

        self.storage.stat = MagicMock(side_effect=stat)
        self.storage.get_range = MagicMock(side_effect=get_range)

        await self.service.read_asset(
            self.session, self.valid_token(), _VIDEO_PATH, RangeSpec(0, 15)
        )

        self.assertEqual(len(seen), 2)
        for name in seen:
            self.assertTrue(name.startswith("storage-under-test"), msg=seen)


class TestReadAssetRemembersThePackagePrefix(_ContentServiceCase):
    """A course load is fifty files from one package; the database is asked
    for its prefix once, so serving them holds no pooled connection.
    """

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.now = 1000.0
        self.service._clock = lambda: self.now
        self.token = self.valid_token()

    async def test_the_prefix_is_looked_up_again_once_it_is_a_minute_old(self):
        await self.service.read_asset(self.session, self.token, "a.css")
        self.now += 59
        await self.service.read_asset(self.session, self.token, "b.css")
        self.assertEqual(self.package_repository.get_by_id.await_count, 1)

        self.now += 1
        await self.service.read_asset(self.session, self.token, "c.css")

        self.assertEqual(self.package_repository.get_by_id.await_count, 2)

    async def test_a_package_that_is_gone_is_not_remembered(self):
        self.package_repository.get_by_id.return_value = None

        for name in ("a.css", "b.css"):
            with self.assertRaises(FileNotFoundError):
                await self.service.read_asset(self.session, self.token, name)

        self.assertEqual(self.package_repository.get_by_id.await_count, 2)
        self.storage.get.assert_not_called()

    async def test_each_package_has_its_own_prefix(self):
        other = MagicMock(
            package_id=_PENDING_PACKAGE_ID, storage_prefix="training/9/other/"
        )
        self.package_repository.get_by_id.side_effect = lambda session, package_id: (
            self.package if package_id == _PACKAGE_ID else other
        )
        other_token, _ = issue_content_token(
            _KEY, _TRAINING_ID, _USER_ID, package_id=_PENDING_PACKAGE_ID
        )

        await self.service.read_asset(self.session, self.token, "a.css")
        await self.service.read_asset(self.session, other_token, "a.css")

        self.assertEqual(
            self.fetched_keys(), [_OLD_PREFIX + "a.css", "training/9/other/a.css"]
        )

    async def test_a_replaced_package_reads_as_gone_not_as_a_missing_file(self):
        """Publishing deletes the old row and then its files; a tab still on
        the old token must get the reload message, not a storage warning.
        """
        await self.service.read_asset(self.session, self.token, "a.css")
        self.package_repository.get_by_id.return_value = None
        self.storage.get = MagicMock(return_value=None)

        with self.assertRaises(FileNotFoundError) as caught:
            await self.service.read_asset(self.session, self.token, "b.css")

        self.assertEqual(str(caught.exception), "This package is no longer served.")
        self.assertEqual(self.package_repository.get_by_id.await_count, 2)
        self.logger.warning.assert_not_called()

    async def test_a_missing_file_in_a_live_package_still_warns(self):
        await self.service.read_asset(self.session, self.token, "a.css")
        self.storage.get = MagicMock(return_value=None)

        with self.assertRaises(FileNotFoundError):
            await self.service.read_asset(self.session, self.token, "missing.css")

        self.logger.warning.assert_called_once()
        self.assertIn("no object", self.logger.warning.call_args.args[0])

    async def test_two_reads_that_find_a_replaced_package_together_both_say_gone(self):
        # Both find their file missing before either asks the database, so
        # the second goes to forget a prefix the first already forgot.
        await self.service.read_asset(self.session, self.token, "a.css")
        self.package_repository.get_by_id.return_value = None
        both_missed = asyncio.Barrier(2)

        async def missing(*args):
            await both_missed.wait()
            return None

        self.service._off_loop = missing

        results = await asyncio.gather(
            self.service.read_asset(self.session, self.token, "b.css"),
            self.service.read_asset(self.session, self.token, "c.css"),
            return_exceptions=True,
        )

        for result in results:
            self.assertIsInstance(result, FileNotFoundError)
            self.assertEqual(str(result), "This package is no longer served.")

    async def test_a_range_read_from_a_replaced_package_reads_as_gone(self):
        await self.service.read_asset(self.session, self.token, "a.css")
        self.package_repository.get_by_id.return_value = None
        self.storage.stat = MagicMock(return_value=None)

        with self.assertRaises(FileNotFoundError) as caught:
            await self.service.read_asset(
                self.session, self.token, _VIDEO_PATH, RangeSpec(0, 15)
            )

        self.assertEqual(str(caught.exception), "This package is no longer served.")
        self.logger.warning.assert_not_called()

    async def test_the_player_files_never_ask_for_the_package(self):
        await self.service.read_asset(self.session, self.token, PLAYER_PATH)

        self.package_repository.get_by_id.assert_not_awaited()


class TestSlowCourseFilesSayWhereTheTimeWent(_ContentServiceCase):
    """One line per slow file, split by stage, so a queueing course load can
    be pinned on the database, the thread pool, storage or the event loop.
    """

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.now = 1000.0
        self.service._clock = lambda: self.now
        self.token = self.valid_token()

    def advance(self, seconds, result):
        def step(*args):
            self.now += seconds
            return result

        return step

    def slow_lines(self):
        return [
            call
            for call in self.logger.info.call_args_list
            if "slow course file" in call.args[0]
        ]

    async def test_a_slow_file_logs_each_stage(self):
        self.package_repository.get_by_id = AsyncMock(
            side_effect=self.advance(0.1, self.package)
        )
        self.storage.get = MagicMock(
            side_effect=self.advance(0.7, (b"x" * 5, "text/css"))
        )

        await self.service.read_asset(self.session, self.token, "a.css")

        (line,) = self.slow_lines()
        _, package_id, path, size, total, lookup, queued, storage, resumed = line.args
        self.assertEqual((package_id, path, size), (_PACKAGE_ID, "a.css", 5))
        self.assertAlmostEqual(total, 800)
        self.assertAlmostEqual(lookup, 100)
        self.assertAlmostEqual(storage, 700)
        self.assertAlmostEqual(queued, 0)
        self.assertAlmostEqual(resumed, 0)

    async def test_a_fast_file_logs_nothing(self):
        self.storage.get = MagicMock(side_effect=self.advance(0.4, (b"x", "text/css")))

        await self.service.read_asset(self.session, self.token, "a.css")

        self.assertEqual(self.slow_lines(), [])

    async def test_waiting_for_a_busy_thread_counts_as_queued(self):
        executor = ThreadPoolExecutor(max_workers=1)
        self.addCleanup(executor.shutdown)
        self.service.storage_executor = executor
        # The first read holds the only thread until both have been handed to
        # the executor; otherwise it can finish before the second is queued.
        both_submitted = threading.Event()

        def get(object_key):
            both_submitted.wait(timeout=5)
            self.now += 0.6
            return b"x", "text/css"

        self.storage.get = MagicMock(side_effect=get)

        reads = [
            asyncio.create_task(self.service.read_asset(self.session, self.token, name))
            for name in ("a.css", "b.css")
        ]
        for _ in range(5):
            await asyncio.sleep(0)
        both_submitted.set()
        await asyncio.gather(*reads)

        queued = sorted(line.args[6] for line in self.slow_lines())
        self.assertEqual(len(queued), 2)
        self.assertAlmostEqual(queued[0], 0)
        self.assertAlmostEqual(queued[1], 600)

    async def test_both_storage_calls_of_a_range_read_count(self):
        self.storage.stat = MagicMock(
            side_effect=self.advance(0.3, (len(_VIDEO), "video/mp4"))
        )
        self.storage.get_range = MagicMock(
            side_effect=lambda key, start, end: self.advance(
                0.4, _VIDEO[start : end + 1]
            )()
        )

        await self.service.read_asset(
            self.session, self.token, _VIDEO_PATH, RangeSpec(0, 15)
        )

        (line,) = self.slow_lines()
        self.assertAlmostEqual(line.args[7], 700)


class TestReadAssetKeepsCourseFilesInMemory(_ContentServiceCase):
    """A cohort opening one course asks for the same files over and over;
    after the first read they come from memory, not storage.
    """

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.now = 1000.0
        self.service._clock = lambda: self.now
        self.token = self.valid_token()

    async def test_a_file_read_twice_comes_from_storage_once(self):
        first = await self.service.read_asset(self.session, self.token, "a.css")
        second = await self.service.read_asset(self.session, self.token, "a.css")

        self.assertEqual(self.storage.get.call_count, 1)
        self.assertEqual(second.data, first.data)
        self.assertEqual(second.content_type, first.content_type)

    async def test_a_large_file_is_read_from_storage_every_time(self):
        self.storage.get = MagicMock(return_value=(b"x" * 11, "video/mp4"))

        with patch.object(content_service_module, "_FILE_CACHE_LARGEST", 10):
            for _ in range(2):
                await self.service.read_asset(self.session, self.token, "big.mp4")

        self.assertEqual(self.storage.get.call_count, 2)

    async def test_the_least_recently_served_file_goes_first(self):
        self.storage.get = MagicMock(return_value=(b"x" * 4, "text/css"))

        with patch.object(content_service_module, "_FILE_CACHE_BYTES", 8):
            for name in ("a.css", "b.css", "a.css", "c.css"):
                await self.service.read_asset(self.session, self.token, name)
            self.storage.get.reset_mock()
            for name in ("a.css", "c.css", "b.css"):
                await self.service.read_asset(self.session, self.token, name)

        # a was served again before c arrived, so b was the one dropped.
        self.assertEqual(self.fetched_keys(), [_OLD_PREFIX + "b.css"])

    async def test_requests_for_a_file_being_read_share_that_read(self):
        both_asked = threading.Event()

        def get(object_key):
            both_asked.wait(timeout=5)
            return b"x", "text/css"

        self.storage.get = MagicMock(side_effect=get)

        reads = [
            asyncio.create_task(
                self.service.read_asset(self.session, self.token, "a.css")
            )
            for _ in range(2)
        ]
        for _ in range(5):
            await asyncio.sleep(0)
        both_asked.set()
        first, second = await asyncio.gather(*reads)

        self.assertEqual(self.storage.get.call_count, 1)
        self.assertEqual(first.data, second.data)

    async def test_a_missing_file_is_not_remembered(self):
        self.storage.get = MagicMock(return_value=None)

        for _ in range(2):
            with self.assertRaises(FileNotFoundError):
                await self.service.read_asset(self.session, self.token, "gone.css")

        self.assertEqual(self.storage.get.call_count, 2)

    async def test_a_gone_package_stops_being_served_once_its_prefix_expires(self):
        await self.service.read_asset(self.session, self.token, "a.css")
        self.package_repository.get_by_id.return_value = None
        self.now += 60

        with self.assertRaises(FileNotFoundError) as caught:
            await self.service.read_asset(self.session, self.token, "a.css")

        self.assertEqual(str(caught.exception), "This package is no longer served.")
        self.assertEqual(self.storage.get.call_count, 1)

    async def test_a_range_read_still_goes_to_storage(self):
        for _ in range(2):
            await self.service.read_asset(
                self.session, self.token, _VIDEO_PATH, RangeSpec(0, 15)
            )

        self.assertEqual(self.storage.get_range.call_count, 2)


class TestReadAssetNeverReadsTheAssignment(_ContentServiceCase):
    """The token names the package outright, so serving a file asks the
    database one question instead of two -- and a course load asks for
    hundreds of files.
    """

    async def test_no_assignment_lookup_for_a_package_file(self):
        token = self.valid_token()

        for name in ("a.css", "b.css", "c.js"):
            await self.service.read_asset(self.session, token, name)

        self.training_repository.get_training_by_id.assert_not_awaited()

    async def test_one_package_read_for_the_whole_load_and_nothing_else(self):
        token = self.valid_token()

        for name in ("a.css", "b.css", "c.js"):
            await self.service.read_asset(self.session, token, name)

        self.assertEqual(self.package_repository.get_by_id.await_count, 1)


if __name__ == "__main__":
    unittest.main()
