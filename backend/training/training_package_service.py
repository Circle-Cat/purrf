"""Uploading a course package, and cleaning up the one it replaced."""

import io
import posixpath
import uuid
import zipfile
from datetime import datetime, timezone

from backend.dto.training_course_dto import TrainingPackageUploadResultDto
from backend.training.scorm_manifest import ManifestRejected
from backend.training.scorm_package import PackageRejected, read_package
from backend.training.training_storage import content_type_for


class TrainingPackageService:
    """Turning an uploaded zip into a course somebody could learn.

    Nothing is overwritten in place. Files go to a fresh prefix, and only once
    every one of them has landed does the course start pointing at it -- an
    upload that dies halfway leaves the live course untouched.
    """

    def __init__(
        self,
        logger,
        training_course_repository,
        training_progress_repository,
        training_storage,
    ):
        """
        Args:
            logger: Injected logger.
            training_course_repository (TrainingCourseRepository): The course
                being uploaded to.
            training_progress_repository: Clears resume data for learners who
                had not finished.
            training_storage (TrainingStorage): Object storage.
        """
        self.logger = logger
        self.training_course_repository = training_course_repository
        self.training_progress_repository = training_progress_repository
        self.training_storage = training_storage

    async def upload_package(
        self, session, course_id: int, archive_bytes: bytes, now: datetime | None = None
    ) -> TrainingPackageUploadResultDto:
        """Validate a zip, store it, and point the course at it.

        Replacing a package has two consequences the admin was shown before
        clicking, and both happen here: verification is cleared, because a new
        export is a new thing and the old proof does not carry over; and resume
        data is wiped for everyone who had not finished, because the previous
        package's suspend_data means nothing to the new one and can hang it.
        Finished records are left alone.

        The previous prefix's files are deleted only after the transaction
        that moves the course onto the new one commits. A content token never
        carries the prefix -- every asset request looks it up fresh -- so
        nobody can still be reading the old prefix once the course row has
        flipped, and deleting beforehand would risk leaving the course
        pointing at files that a rollback never restores. A delete that fails
        is logged, not raised: the upload has already succeeded, and the only
        cost is some storage left behind.

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
                        archive.read(name),
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
        previous_prefix = course.storage_prefix

        course.storage_prefix = new_prefix
        course.entry_path = contents.manifest.entry_path
        course.scorm_version = contents.manifest.scorm_version
        course.package_uploaded_at = moment
        if contents.driver_config is not None:
            course.package_version = contents.driver_config.course_package_version
            course.reporting_mode = contents.driver_config.reporting
        else:
            course.package_version = None
            course.reporting_mode = None
        course.verified_completable_at = None
        course.verified_by_user_id = None

        cleared = 0
        if previous_prefix:
            cleared = await self.training_progress_repository.clear_resume_state(
                session, course_id
            )

        await session.commit()

        self.logger.info(
            "[TrainingPackageService] course %s now serves %s "
            "(%s files, %s learners reset)",
            course_id,
            new_prefix,
            len(contents.file_names),
            cleared,
        )

        if previous_prefix:
            try:
                self.training_storage.delete_prefix(previous_prefix)
            except Exception:
                self.logger.exception(
                    "[TrainingPackageService] could not delete replaced prefix %s "
                    "for course %s",
                    previous_prefix,
                    course_id,
                )

        config = contents.driver_config
        return TrainingPackageUploadResultDto(
            course_id=course_id,
            storage_prefix=new_prefix,
            entry_path=contents.manifest.entry_path,
            scorm_version=contents.manifest.scorm_version,
            file_count=len(contents.file_names),
            total_bytes=contents.total_uncompressed_bytes,
            package_version=config.course_package_version if config else None,
            reporting_mode=config.reporting if config else None,
            completes_via_storyline=bool(config and config.storyline_id),
            completion_config_readable=config is not None,
            missing_declared_files=contents.missing_declared_files,
            learners_reset=cleared,
        )
