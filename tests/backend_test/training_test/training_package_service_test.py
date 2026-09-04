"""Uploading a package over a live course, and clearing up after it."""

import datetime
import io
import json
import unittest
import zipfile
from unittest.mock import AsyncMock, MagicMock

from backend.common.mentorship_enums import ScormVersion, TrainingPackageState
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.training.scorm_package import PackageRejected
from backend.training.training_package_service import TrainingPackageService

_COURSE_ID = 7
_ENTRY_PATH = "index.html"
_LIVE_PREFIX = "training/7/9cf1e0d2/"
_NOW = datetime.datetime(2026, 9, 2, 9, 0, tzinfo=datetime.timezone.utc)
_VERIFIED_AT = datetime.datetime(2026, 8, 30, 12, 0, tzinfo=datetime.timezone.utc)

# The keys the real packages under scorm/ write, and only those.
_DRIVER_CONFIG = {
    "coursePackageVersion": "qPpo9zHD",
    "lmsTarget": "scorm12",
    "resetLearnerData": False,
    "quizId": None,
    "storylineId": None,
    "completionPercentage": 100,
    "reporting": "passed-incomplete",
}


def _manifest(*, schemaversion: str = "1.2", declared_files: tuple = ()) -> bytes:
    """A manifest shaped like the ones the real packages ship."""
    files = "".join(
        f'\n      <file href="{href}"/>' for href in (_ENTRY_PATH, *declared_files)
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="cat_course" version="1.2">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>{schemaversion}</schemaversion>
  </metadata>
  <organizations default="org_1">
    <organization identifier="org_1">
      <title>Cat Care Fundamentals</title>
      <item identifier="item_1" identifierref="res_1">
        <title>Module One</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="res_1" type="webcontent" href="{_ENTRY_PATH}">{files}
    </resource>
  </resources>
</manifest>"""
    return xml.encode("utf-8")


def _entry_page(driver_config: dict | None) -> bytes:
    script = ""
    if driver_config is not None:
        script = (
            '<script id="__DRIVER_CONFIG__" type="application/json">'
            f"{json.dumps(driver_config)}</script>"
        )
    html = f"""<!DOCTYPE html>
<html>
<head><title>Cat Care Fundamentals</title>{script}</head>
<body><div id="course"></div></body>
</html>"""
    return html.encode("utf-8")


def _members(
    *,
    schemaversion: str = "1.2",
    driver_config: dict | None = _DRIVER_CONFIG,
    declared_files: tuple = (),
    extra_members: dict | None = None,
) -> dict:
    """The archive members of a minimal but valid SCORM 1.2 package.

    Separate from the zip so a test can assert on file count and byte total
    without opening the archive again.
    """
    members = {
        "imsmanifest.xml": _manifest(
            schemaversion=schemaversion, declared_files=declared_files
        ),
        _ENTRY_PATH: _entry_page(driver_config),
    }
    members.update(extra_members or {})
    return members


def _zip(members: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _package(**kwargs) -> bytes:
    return _zip(_members(**kwargs))


def _named_arguments(mock, names: tuple) -> dict:
    """One call's arguments by name, however they were passed."""
    args, kwargs = mock.call_args
    bound = dict(zip(names, args))
    bound.update(kwargs)
    return bound


class _RecordingCourse:
    """A course row that notes the moment its columns are written.

    A real entity cannot interleave its attribute writes with the storage
    calls in one list, and that order is the whole point of one test below.
    """

    def __init__(self, events: list, **fields):
        object.__setattr__(self, "_events", events)
        for name, value in fields.items():
            object.__setattr__(self, name, value)

    def __getattr__(self, name):
        # Any column not set here is NULL on a real row.
        return None

    def __setattr__(self, name, value):
        self._events.append((f"course.{name}", value))
        object.__setattr__(self, name, value)


class _PackageServiceTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.logger = MagicMock()
        self.course_repository = AsyncMock()
        self.course_repository.get_course_by_id.return_value = None
        self.progress_repository = AsyncMock()
        self.progress_repository.clear_resume_state.return_value = 0
        self.storage = MagicMock()
        self.storage.put.return_value = None
        self.storage.delete_prefix.return_value = 0
        self.package_repository = AsyncMock()
        self.package_repository.get_by_state.return_value = None
        self.service = TrainingPackageService(
            logger=self.logger,
            training_course_repository=self.course_repository,
            training_progress_repository=self.progress_repository,
            training_course_package_repository=self.package_repository,
            training_storage=self.storage,
        )

    def _course(self, **overrides) -> TrainingCourseEntity:
        fields = {
            "course_id": _COURSE_ID,
            "name": "Cat Care Fundamentals",
            "is_active": True,
        }
        fields.update(overrides)
        course = TrainingCourseEntity(**fields)
        self.course_repository.get_course_by_id.return_value = course
        return course

    def _put_keys(self) -> list:
        return [
            call.args[0] if call.args else call.kwargs["object_key"]
            for call in self.storage.put.call_args_list
        ]

    def _deleted_prefixes(self) -> list:
        return [
            call.args[0] if call.args else call.kwargs["prefix"]
            for call in self.storage.delete_prefix.call_args_list
        ]


class TestUploadPackage(_PackageServiceTestCase):
    async def test_a_first_upload_stores_every_file_under_a_fresh_prefix(self):
        course = self._course(storage_prefix=None)
        members = _members()

        result = await self.service.upload_package(
            self.session, _COURSE_ID, _zip(members), now=_NOW
        )

        self.assertIsNotNone(course.storage_prefix)
        self.assertTrue(course.storage_prefix.startswith(f"training/{_COURSE_ID}/"))
        self.assertEqual(course.storage_prefix, result.storage_prefix)
        self.assertEqual(
            sorted(self._put_keys()),
            sorted(course.storage_prefix + name for name in members),
        )

    async def test_a_zip_written_with_dot_slash_entries_uploads(self):
        """Legal, and some zip tools write every entry this way. Reading such an
        entry back by its normalised name used to raise KeyError, which reached
        the admin as "Internal Server Error" rather than as a rule."""
        course = self._course(storage_prefix=None)
        members = {
            f"./{name}": data
            for name, data in _members(
                extra_members={"assets/cat.jpg": b"meow"}
            ).items()
        }

        result = await self.service.upload_package(
            self.session, _COURSE_ID, _zip(members), now=_NOW
        )

        self.assertEqual(result.entry_path, _ENTRY_PATH)
        self.assertEqual(
            sorted(self._put_keys()),
            sorted(
                course.storage_prefix + name
                for name in ("assets/cat.jpg", "imsmanifest.xml", _ENTRY_PATH)
            ),
        )

    async def test_an_overwrite_mints_a_prefix_the_live_one_does_not_share(self):
        """Nothing is ever written in place."""
        course = self._course(storage_prefix=_LIVE_PREFIX)

        result = await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        self.assertNotEqual(result.storage_prefix, _LIVE_PREFIX)
        self.assertEqual(course.storage_prefix, result.storage_prefix)
        for key in self._put_keys():
            self.assertFalse(key.startswith(_LIVE_PREFIX))

    async def test_every_file_is_stored_before_the_prefix_moves(self):
        """A half-finished upload has to leave the live course intact."""
        events = []
        course = _RecordingCourse(
            events,
            course_id=_COURSE_ID,
            storage_prefix=_LIVE_PREFIX,
            verified_completable_at=_VERIFIED_AT,
        )
        self.course_repository.get_course_by_id.return_value = course

        def _note_the_put(object_key, *args, **kwargs):
            events.append(("put", object_key))

        self.storage.put.side_effect = _note_the_put

        await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        names = [name for name, _ in events]
        self.assertIn("put", names)
        self.assertIn("course.storage_prefix", names)
        last_put = max(index for index, name in enumerate(names) if name == "put")
        self.assertGreater(names.index("course.storage_prefix"), last_put)

    async def test_an_upload_that_dies_partway_leaves_the_live_course_alone(self):
        course = self._course(
            storage_prefix=_LIVE_PREFIX,
            entry_path="old_index.html",
            verified_completable_at=_VERIFIED_AT,
            verified_by_user_id=3,
        )
        stored = []

        def _die_on_the_second_file(object_key, *args, **kwargs):
            stored.append(object_key)
            if len(stored) == 2:
                raise RuntimeError("the bucket went away mid-upload")

        self.storage.put.side_effect = _die_on_the_second_file
        archive = _package(extra_members={"assets/cat.png": b"not really a png"})

        with self.assertRaises(RuntimeError):
            await self.service.upload_package(
                self.session, _COURSE_ID, archive, now=_NOW
            )

        self.assertEqual(course.storage_prefix, _LIVE_PREFIX)
        self.assertEqual(course.entry_path, "old_index.html")
        self.assertEqual(course.verified_completable_at, _VERIFIED_AT)
        self.assertEqual(course.verified_by_user_id, 3)
        self.progress_repository.clear_resume_state.assert_not_awaited()
        self.storage.delete_prefix.assert_not_called()

    async def test_an_overwrite_clears_resume_state_and_reports_the_count(self):
        self._course(storage_prefix=_LIVE_PREFIX)
        self.progress_repository.clear_resume_state.return_value = 3

        result = await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        self.assertEqual(result.learners_reset, 3)

    async def test_a_first_upload_resets_nobody(self):
        self._course(storage_prefix=None)

        result = await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        self.assertEqual(result.learners_reset, 0)

    async def test_the_clearing_is_asked_for_by_course(self):
        """Whether DONE rows are spared is the repository's contract, tested there."""
        self._course(storage_prefix=_LIVE_PREFIX)
        self.progress_repository.clear_resume_state.return_value = 3

        await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        self.progress_repository.clear_resume_state.assert_awaited_once()
        recorded = _named_arguments(
            self.progress_repository.clear_resume_state, ("session", "course_id")
        )
        self.assertEqual(recorded["course_id"], _COURSE_ID)

    async def test_the_service_never_clears_a_progress_row_itself(self):
        """One statement over the course, not a row-by-row walk it can half-finish."""
        self._course(storage_prefix=_LIVE_PREFIX)

        await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        self.assertEqual(
            [recorded[0] for recorded in self.progress_repository.mock_calls],
            ["clear_resume_state"],
        )
        self.session.add.assert_not_called()
        self.session.execute.assert_not_called()

    async def test_an_overwrite_drops_the_course_back_to_needs_trial_run(self):
        """The proof belonged to the old package."""
        course = self._course(
            storage_prefix=_LIVE_PREFIX,
            verified_completable_at=_VERIFIED_AT,
            verified_by_user_id=3,
        )

        await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        self.assertIsNone(course.verified_completable_at)
        self.assertIsNone(course.verified_by_user_id)

    async def test_a_first_upload_is_unverified_too(self):
        course = self._course(storage_prefix=None)

        await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        self.assertIsNone(course.verified_completable_at)
        self.assertIsNone(course.verified_by_user_id)

    async def test_a_scorm_2004_package_is_refused_and_nothing_is_written(self):
        """Refused at upload, not left to fail under a learner months later."""
        course = self._course(storage_prefix=_LIVE_PREFIX)

        with self.assertRaises(PackageRejected):
            await self.service.upload_package(
                self.session,
                _COURSE_ID,
                _package(schemaversion="2004 4th Edition"),
                now=_NOW,
            )

        self.storage.put.assert_not_called()
        self.assertEqual(course.storage_prefix, _LIVE_PREFIX)
        self.progress_repository.clear_resume_state.assert_not_awaited()
        self.storage.delete_prefix.assert_not_called()

    async def test_an_archive_that_climbs_out_of_its_prefix_is_refused(self):
        course = self._course(storage_prefix=_LIVE_PREFIX)
        archive = _package(extra_members={"../escape.txt": b"nope"})

        with self.assertRaises(PackageRejected):
            await self.service.upload_package(
                self.session, _COURSE_ID, archive, now=_NOW
            )

        self.storage.put.assert_not_called()
        self.assertEqual(course.storage_prefix, _LIVE_PREFIX)
        self.progress_repository.clear_resume_state.assert_not_awaited()

    async def test_uploading_to_a_course_that_does_not_exist_is_refused(self):
        self.course_repository.get_course_by_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.upload_package(self.session, 404, _package(), now=_NOW)

        self.storage.put.assert_not_called()
        self.progress_repository.clear_resume_state.assert_not_awaited()

    async def test_the_result_describes_what_was_stored(self):
        course = self._course(storage_prefix=None)
        members = _members()

        result = await self.service.upload_package(
            self.session, _COURSE_ID, _zip(members), now=_NOW
        )

        self.assertEqual(result.course_id, _COURSE_ID)
        self.assertEqual(result.entry_path, _ENTRY_PATH)
        self.assertEqual(result.scorm_version, ScormVersion.SCORM_12)
        self.assertEqual(result.file_count, len(members))
        self.assertEqual(result.total_bytes, sum(len(d) for d in members.values()))
        self.assertEqual(result.storage_prefix, course.storage_prefix)

    async def test_the_completion_settings_are_read_off_the_entry_page_and_kept(self):
        """The overwrite criterion and the per-course DONE rule both read them."""
        course = self._course(storage_prefix=None)

        result = await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        self.assertEqual(result.package_version, "qPpo9zHD")
        self.assertEqual(result.reporting_mode, "passed-incomplete")
        self.assertEqual(result.completion_percentage, 100.0)
        self.assertTrue(result.completion_config_readable)
        self.assertEqual(course.package_version, "qPpo9zHD")
        self.assertEqual(course.reporting_mode, "passed-incomplete")
        self.assertEqual(course.entry_path, _ENTRY_PATH)
        self.assertEqual(course.scorm_version, ScormVersion.SCORM_12)

    async def test_a_package_we_cannot_read_uploads_and_says_so(self):
        """Silence here would be read as 'nothing wrong'."""
        course = self._course(storage_prefix=None)

        result = await self.service.upload_package(
            self.session, _COURSE_ID, _package(driver_config=None), now=_NOW
        )

        self.assertFalse(result.completion_config_readable)
        self.assertIsNone(result.package_version)
        self.assertIsNone(result.reporting_mode)
        self.assertIsNone(result.completion_percentage)
        self.assertIsNotNone(course.storage_prefix)

    async def test_files_the_manifest_declares_but_the_archive_lacks_are_surfaced(self):
        """A warning, not a rejection, and not something to swallow either."""
        self._course(storage_prefix=None)
        archive = _package(
            declared_files=("assets/cute%20cat.jpg", "assets/gone.png"),
            extra_members={"assets/cute cat.jpg": b"meow"},
        )

        result = await self.service.upload_package(
            self.session, _COURSE_ID, archive, now=_NOW
        )

        self.assertEqual(result.missing_declared_files, ["assets/gone.png"])

    async def test_an_overwrite_commits_once_after_every_write(self):
        """The recorded writes commit last; the old prefix's deletion is checked
        separately, since it happens after this commit rather than as part of it.
        """
        events = []
        course = _RecordingCourse(
            events, course_id=_COURSE_ID, storage_prefix=_LIVE_PREFIX
        )
        self.course_repository.get_course_by_id.return_value = course
        self.storage.put.side_effect = lambda key, *a, **k: events.append(("put", key))
        self.progress_repository.clear_resume_state.side_effect = (
            lambda *a, **k: events.append(("progress.clear", None)) or 0
        )
        self.session.commit.side_effect = lambda: events.append(("commit", None))

        await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        names = [name for name, _ in events]
        self.assertIn("commit", names)
        self.assertEqual(names.index("commit"), len(names) - 1)
        self.session.commit.assert_awaited_once()

    async def test_a_first_upload_still_commits(self):
        self._course(storage_prefix=None)

        await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        self.session.commit.assert_awaited_once()

    async def test_a_rejected_scorm_2004_package_awaits_no_commit(self):
        self._course(storage_prefix=_LIVE_PREFIX)

        with self.assertRaises(PackageRejected):
            await self.service.upload_package(
                self.session,
                _COURSE_ID,
                _package(schemaversion="2004 4th Edition"),
                now=_NOW,
            )

        self.session.commit.assert_not_awaited()

    async def test_an_archive_that_climbs_out_of_its_prefix_awaits_no_commit(self):
        self._course(storage_prefix=_LIVE_PREFIX)
        archive = _package(extra_members={"../escape.txt": b"nope"})

        with self.assertRaises(PackageRejected):
            await self.service.upload_package(
                self.session, _COURSE_ID, archive, now=_NOW
            )

        self.session.commit.assert_not_awaited()

    async def test_a_mid_upload_storage_failure_awaits_no_commit(self):
        self._course(storage_prefix=_LIVE_PREFIX)
        stored = []

        def _die_on_the_second_file(object_key, *args, **kwargs):
            stored.append(object_key)
            if len(stored) == 2:
                raise RuntimeError("the bucket went away mid-upload")

        self.storage.put.side_effect = _die_on_the_second_file
        archive = _package(extra_members={"assets/cat.png": b"not really a png"})

        with self.assertRaises(RuntimeError):
            await self.service.upload_package(
                self.session, _COURSE_ID, archive, now=_NOW
            )

        self.session.commit.assert_not_awaited()

    async def test_upload_stores_the_package_as_a_row(self):
        course = self._course(storage_prefix=None)

        await self.service.upload_package(
            self.session, _COURSE_ID, _zip(_members()), now=_NOW
        )

        stored = self.package_repository.add.await_args.args[1]
        self.assertEqual(stored.course_id, _COURSE_ID)
        self.assertEqual(stored.state, TrainingPackageState.LIVE)
        self.assertEqual(stored.storage_prefix, course.storage_prefix)
        self.assertEqual(stored.entry_path, _ENTRY_PATH)
        self.assertEqual(stored.scorm_version, ScormVersion.SCORM_12)
        self.assertEqual(stored.package_version, "qPpo9zHD")
        self.assertEqual(stored.reporting_mode, "passed-incomplete")
        self.assertEqual(stored.uploaded_at, _NOW)
        self.assertIsNone(stored.verified_completable_at)

    async def test_upload_drops_the_row_it_replaces(self):
        # Two live rows for one course is refused by the database, so the
        # service has to free the slot before it fills it again.
        self._course(storage_prefix=_LIVE_PREFIX, entry_path=_ENTRY_PATH)
        previous = MagicMock()
        self.package_repository.get_by_state.return_value = previous

        await self.service.upload_package(
            self.session, _COURSE_ID, _zip(_members()), now=_NOW
        )

        self.package_repository.delete.assert_awaited_once_with(self.session, previous)
        self.assertEqual(self.package_repository.add.await_count, 1)

    async def test_a_rejected_upload_stores_no_row(self):
        # The rejection happens before anything is written, and a row for a
        # package that was refused would make the course unopenable.
        self._course(storage_prefix=None)

        with self.assertRaises(PackageRejected):
            await self.service.upload_package(
                self.session, _COURSE_ID, b"not a zip", now=_NOW
            )

        self.package_repository.add.assert_not_awaited()


class TestReplacedPrefixDeletion(_PackageServiceTestCase):
    """The prefix an overwrite replaces is deleted once, after the commit."""

    async def test_an_overwrite_deletes_the_previous_prefix(self):
        self._course(storage_prefix=_LIVE_PREFIX)

        await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        self.assertEqual(self._deleted_prefixes(), [_LIVE_PREFIX])

    async def test_a_first_upload_deletes_nothing(self):
        """There is no previous prefix to clean up."""
        self._course(storage_prefix=None)

        await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        self.storage.delete_prefix.assert_not_called()

    async def test_the_previous_prefix_is_deleted_only_after_the_commit(self):
        """Deleting ahead of the commit risks a rollback finding the files gone."""
        events = []
        self._course(storage_prefix=_LIVE_PREFIX)
        self.session.commit.side_effect = lambda: events.append("commit")
        self.storage.delete_prefix.side_effect = (
            lambda prefix, *a, **k: events.append("delete") or 0
        )

        await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        self.assertEqual(events, ["commit", "delete"])

    async def test_a_failed_commit_never_deletes_the_previous_prefix(self):
        """The delete is irreversible and the commit is not, so the delete must
        never run unless the commit that it depends on actually succeeded.
        """
        self._course(storage_prefix=_LIVE_PREFIX)
        self.session.commit.side_effect = RuntimeError("connection lost")

        with self.assertRaises(RuntimeError):
            await self.service.upload_package(
                self.session, _COURSE_ID, _package(), now=_NOW
            )

        self.storage.delete_prefix.assert_not_called()

    async def test_a_failed_delete_of_the_previous_prefix_does_not_fail_the_upload(
        self,
    ):
        """The upload already succeeded; a leftover prefix is the accepted cost."""
        self._course(storage_prefix=_LIVE_PREFIX)
        self.storage.delete_prefix.side_effect = RuntimeError("bucket said no")

        result = await self.service.upload_package(
            self.session, _COURSE_ID, _package(), now=_NOW
        )

        self.assertIsNotNone(result)
        self.logger.exception.assert_called_once()


class TestReadCompletionConfig(_PackageServiceTestCase):
    """What the stored package says about finishing, re-read on demand.

    The three answers here are shown once in the upload dialog and then never
    again, so the trial page asks for them rather than the course row storing
    a copy that a re-upload could leave stale.
    """

    def _stored(self, driver_config=_DRIVER_CONFIG):
        self.storage.get.return_value = (_entry_page(driver_config), "text/html")

    async def test_it_reads_the_entry_page_under_the_courses_own_prefix(self):
        self._course(storage_prefix=_LIVE_PREFIX, entry_path=_ENTRY_PATH)
        self._stored()

        await self.service.read_completion_config(self.session, _COURSE_ID)

        self.storage.get.assert_called_once()
        key = self.storage.get.call_args.args[0]
        self.assertEqual(key, f"{_LIVE_PREFIX}{_ENTRY_PATH}")

    async def test_it_reports_what_the_package_requires_before_completion(self):
        self._course(storage_prefix=_LIVE_PREFIX, entry_path=_ENTRY_PATH)
        self._stored()

        result = await self.service.read_completion_config(self.session, _COURSE_ID)

        self.assertTrue(result.completion_config_readable)
        self.assertEqual(result.completion_percentage, 100)
        self.assertFalse(result.completes_via_storyline)

    async def test_a_course_that_only_completes_via_storyline_says_so(self):
        """Finishing the surrounding lessons will not complete such a course."""
        self._course(storage_prefix=_LIVE_PREFIX, entry_path=_ENTRY_PATH)
        self._stored({**_DRIVER_CONFIG, "storylineId": "5xKq"})

        result = await self.service.read_completion_config(self.session, _COURSE_ID)

        self.assertTrue(result.completes_via_storyline)

    async def test_a_package_we_cannot_read_says_so_rather_than_failing(self):
        """Silence here reads as "nothing wrong", which is the whole mistake."""
        self._course(storage_prefix=_LIVE_PREFIX, entry_path=_ENTRY_PATH)
        self._stored(None)

        result = await self.service.read_completion_config(self.session, _COURSE_ID)

        self.assertFalse(result.completion_config_readable)
        self.assertIsNone(result.completion_percentage)
        self.assertFalse(result.completes_via_storyline)

    async def test_it_reports_whether_the_course_is_already_verified(self):
        """The trial page shows this; the assignment's own status cannot.

        A verifier re-running a replaced package is still DONE on their row,
        so a page reading that would claim the new package was unlocked
        before anybody had finished it.
        """
        self._course(
            storage_prefix=_LIVE_PREFIX,
            entry_path=_ENTRY_PATH,
            verified_completable_at=_VERIFIED_AT,
        )
        self._stored()

        result = await self.service.read_completion_config(self.session, _COURSE_ID)

        self.assertTrue(result.verified)

    async def test_a_course_awaiting_its_trial_run_is_not_verified(self):
        self._course(storage_prefix=_LIVE_PREFIX, entry_path=_ENTRY_PATH)
        self._stored()

        result = await self.service.read_completion_config(self.session, _COURSE_ID)

        self.assertFalse(result.verified)

    async def test_a_course_with_no_package_is_refused(self):
        self._course(storage_prefix=None)

        with self.assertRaises(ValueError):
            await self.service.read_completion_config(self.session, _COURSE_ID)

        self.storage.get.assert_not_called()

    async def test_a_course_that_does_not_exist_is_refused(self):
        self.course_repository.get_course_by_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.read_completion_config(self.session, _COURSE_ID)

    async def test_an_entry_page_gone_from_storage_is_a_clean_not_found(self):
        """A missing object is a fault to fix, not a package we cannot read."""
        self._course(storage_prefix=_LIVE_PREFIX, entry_path=_ENTRY_PATH)
        self.storage.get.return_value = None

        with self.assertRaises(FileNotFoundError):
            await self.service.read_completion_config(self.session, _COURSE_ID)


if __name__ == "__main__":
    unittest.main()
