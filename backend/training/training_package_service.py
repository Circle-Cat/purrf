"""Uploading a course package as a staged, pending replacement."""

import io
import posixpath
import uuid
import zipfile
from datetime import datetime, timezone

from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import TrainingPackageState
from backend.dto.training_course_dto import (
    TrainingCompletionConfigDto,
    TrainingPackagePublishResultDto,
    TrainingPackageUploadResultDto,
)
from backend.entity.training_course_package_entity import (
    TrainingCoursePackageEntity,
)
from backend.training.scorm_manifest import ManifestRejected, parse_driver_config
from backend.training.scorm_package import PackageRejected, read_package
from backend.training.training_storage import content_type_for


class TrainingPackageService:
    """Turning an uploaded zip into a staged course package.

    Nothing is overwritten in place. Files go to a fresh prefix, and only once
    every one of them has landed does the new row take the course's PENDING
    slot -- an upload that dies halfway leaves both the live package and any
    previously staged one untouched. The PENDING package replaces nothing a
    learner can see; that is Publish's job, done deliberately and later.
    """

    def __init__(
        self,
        logger,
        training_course_repository,
        training_progress_repository,
        training_course_package_repository,
        training_storage,
    ):
        """
        Args:
            logger: Injected logger.
            training_course_repository (TrainingCourseRepository): The course
                being uploaded to.
            training_progress_repository: Clears resume data for learners who
                had not finished.
            training_course_package_repository (TrainingCoursePackageRepository):
                Records each upload as its own row.
            training_storage (TrainingStorage): Object storage.
        """
        self.logger = logger
        self.training_course_repository = training_course_repository
        self.training_progress_repository = training_progress_repository
        self.training_course_package_repository = training_course_package_repository
        self.training_storage = training_storage

    async def upload_package(
        self, session, course_id: int, archive_bytes: bytes, now: datetime | None = None
    ) -> TrainingPackageUploadResultDto:
        """Validate a zip, store it, and stage it as the course's pending package.

        An upload is not a publication. The new row is written as PENDING,
        and the course's LIVE package -- what learners are actually served --
        is not read, not replaced and not cleared against: nobody on the
        course sees anything change until somebody presses Publish.

        At most one PENDING row exists per course, so this upload retires
        whatever pending attempt came before it. That retired package's files
        are deleted only after the transaction that drops its row commits,
        for the same reason Publish deletes late: deleting beforehand would
        risk a rollback finding the files already gone under a row the
        transaction never actually removed. A delete that fails is logged,
        not raised -- the upload has already succeeded, and the only cost is
        some storage left behind.

        Args:
            session: The active async database session.
            course_id (int): Course to upload to.
            archive_bytes (bytes): The uploaded zip.
            now (datetime | None): For tests.

        Returns:
            TrainingPackageUploadResultDto: What was stored, and what the
            package says about how it completes.

        Raises:
            ValueError: No such course, or the package broke a rule.
        """
        course = await self.training_course_repository.get_course_by_id(
            session, course_id
        )
        if course is None:
            raise ValueError(f"No training course with id {course_id}.")

        try:
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
                contents = read_package(archive)
                new_prefix = f"training/{course_id}/{uuid.uuid4().hex}/"
                for name in contents.file_names:
                    self.training_storage.put(
                        posixpath.join(new_prefix, name),
                        # Served under the normalised name, read back under the
                        # one the zip actually stores.
                        archive.read(contents.archive_names[name]),
                        content_type_for(name),
                    )
        except zipfile.BadZipFile as error:
            raise PackageRejected(
                "Rejected: the file is not a readable zip archive."
            ) from error
        except ManifestRejected:
            raise
        except PackageRejected:
            raise

        moment = now or datetime.now(timezone.utc)
        package_version = (
            contents.driver_config.course_package_version
            if contents.driver_config is not None
            else None
        )
        reporting_mode = (
            contents.driver_config.reporting
            if contents.driver_config is not None
            else None
        )

        # Only our own un-published attempt is replaced. The live package is
        # not read, not deleted and not cleared against: an upload is not a
        # publication, and nobody on this course sees anything change until
        # somebody presses Publish.
        replaced = await self.training_course_package_repository.get_by_state(
            session, course_id, TrainingPackageState.PENDING
        )
        replaced_prefix = replaced.storage_prefix if replaced is not None else None
        if replaced is not None:
            await self.training_course_package_repository.delete(session, replaced)

        await self.training_course_package_repository.add(
            session,
            TrainingCoursePackageEntity(
                course_id=course_id,
                state=TrainingPackageState.PENDING,
                storage_prefix=new_prefix,
                entry_path=contents.manifest.entry_path,
                scorm_version=contents.manifest.scorm_version,
                package_version=package_version,
                reporting_mode=reporting_mode,
                uploaded_at=moment,
            ),
        )
        await session.commit()

        self.logger.info(
            "[TrainingPackageService] course %s staged %s (%s files)",
            course_id,
            new_prefix,
            len(contents.file_names),
        )

        if replaced_prefix:
            # After the commit, for the same reason publish deletes late: until
            # it lands, the row still names these files.
            self._delete_prefix_quietly(replaced_prefix, course_id)

        config = contents.driver_config
        return TrainingPackageUploadResultDto(
            course_id=course_id,
            storage_prefix=new_prefix,
            entry_path=contents.manifest.entry_path,
            scorm_version=contents.manifest.scorm_version,
            file_count=len(contents.file_names),
            total_bytes=contents.total_uncompressed_bytes,
            package_version=package_version,
            reporting_mode=reporting_mode,
            completion_percentage=config.completion_percentage if config else None,
            completes_via_storyline=bool(config and config.storyline_id),
            completion_config_readable=config is not None,
            missing_declared_files=contents.missing_declared_files,
        )

    async def publish_package(
        self, session, course_id: int
    ) -> TrainingPackagePublishResultDto:
        """Make the staged package the one this course serves.

        Everything destructive about a replacement happens here rather than at
        upload: resume state is cleared for everyone on the course, the
        outgoing row is deleted, and its files go with it. That is the point
        of the split -- an admin who has not pressed this has changed nothing
        for anybody.

        Verification is required, and it is required of the pending row
        itself. A stamp travels with the package it describes, so there is no
        way for one package's proof to let another through.

        The outgoing row is deleted before the incoming one turns live: one
        partial unique index covers `state = 'live'` per course, so the two
        cannot hold that slot at the same instant.

        Args:
            session: The active async database session.
            course_id (int): The course to publish on.

        Returns:
            TrainingPackagePublishResultDto: What is now live, and how many
            progress rows were reset. That count includes learners who had
            already finished -- it is not the number the publish dialog shows.

        Raises:
            ValueError: No such course.
            ConflictError: Nothing staged, or what is staged is unverified.
        """
        course = await self.training_course_repository.get_course_by_id(
            session, course_id
        )
        if course is None:
            raise ValueError(f"No training course with id {course_id}.")

        pending = await self.training_course_package_repository.get_by_state(
            session, course_id, TrainingPackageState.PENDING
        )
        if pending is None:
            raise ConflictError(
                "There is no staged package on this course to publish."
            )
        if pending.verified_completable_at is None:
            raise ConflictError(
                "This package has not been run to completion yet, so it "
                "cannot be published. Start a trial run and finish it first."
            )

        live = await self.training_course_package_repository.get_by_state(
            session, course_id, TrainingPackageState.LIVE
        )
        outgoing_prefix = live.storage_prefix if live is not None else None

        cleared = await self.training_progress_repository.clear_resume_state(
            session, course_id
        )
        if live is not None:
            await self.training_course_package_repository.delete(session, live)
        pending.state = TrainingPackageState.LIVE
        await session.flush()
        await session.commit()

        self.logger.info(
            "[TrainingPackageService] course %s now serves package %s (%s); "
            "%s progress rows reset",
            course_id,
            pending.package_id,
            pending.storage_prefix,
            cleared,
        )

        if outgoing_prefix:
            self._delete_prefix_quietly(outgoing_prefix, course_id)

        return TrainingPackagePublishResultDto(
            course_id=course_id,
            package_id=pending.package_id,
            package_version=pending.package_version,
            learners_reset=cleared,
        )

    def _delete_prefix_quietly(self, prefix: str, course_id: int) -> None:
        """Drop a prefix nothing points at any more.

        A failure is logged, never raised: the transaction that stopped
        anything pointing here has already committed, and the only cost of a
        failed delete is storage left behind.
        """
        try:
            self.training_storage.delete_prefix(prefix)
        except Exception:
            self.logger.exception(
                "[TrainingPackageService] could not delete prefix %s for course %s",
                prefix,
                course_id,
            )

    async def discard_package(self, session, course_id: int) -> None:
        """Throw away the staged package without publishing it.

        The way out of an upload that turned out to be the wrong file. It
        touches nothing a learner can see.

        Raises:
            ConflictError: There is nothing staged on this course.
        """
        pending = await self.training_course_package_repository.get_by_state(
            session, course_id, TrainingPackageState.PENDING
        )
        if pending is None:
            raise ConflictError(
                "There is no staged package on this course to discard."
            )

        prefix = pending.storage_prefix
        await self.training_course_package_repository.delete(session, pending)
        await session.commit()

        self.logger.info(
            "[TrainingPackageService] course %s discarded staged package %s",
            course_id,
            pending.package_id,
        )
        self._delete_prefix_quietly(prefix, course_id)

    async def read_completion_config(
        self, session, course_id: int
    ) -> TrainingCompletionConfigDto:
        """What the course's staged package says it takes to finish it.

        Reads PENDING, not LIVE: the trial page shows this right before
        running a trial, and what the trial is about to run is the staged
        package, not whatever is already live. The upload dialog shows this
        once and is then gone, so it is re-read from the package on request
        instead of copied onto the course row where an overwrite could leave
        it stale.

        Args:
            session: The active async database session.
            course_id (int): The course to read.

        Returns:
            TrainingCompletionConfigDto: What the package says, with
            ``completion_config_readable`` False when it says nothing we
            understand.

        Raises:
            ValueError: No such course, or it has nothing staged.
            FileNotFoundError: The stored entry page is gone.
        """
        course = await self.training_course_repository.get_course_by_id(
            session, course_id
        )
        if course is None:
            raise ValueError(f"No training course with id {course_id}.")

        package = await self.training_course_package_repository.get_by_state(
            session, course_id, TrainingPackageState.PENDING
        )
        if package is None:
            raise ValueError("This course has no staged package to read.")

        object_key = f"{package.storage_prefix}{package.entry_path}"
        stored = self.training_storage.get(object_key)
        if stored is None:
            self.logger.error(
                "[TrainingPackageService] course %s points at %s, which is gone",
                course_id,
                object_key,
            )
            raise FileNotFoundError(object_key)

        config = parse_driver_config(stored[0])
        return TrainingCompletionConfigDto(
            verified=package.verified_completable_at is not None,
            completion_percentage=config.completion_percentage if config else None,
            completes_via_storyline=bool(config and config.storyline_id),
            completion_config_readable=config is not None,
        )
