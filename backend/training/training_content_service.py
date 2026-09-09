"""Serving course files to a browser that has a signed token and no cookie."""

import asyncio
import pathlib
import posixpath
from dataclasses import dataclass

from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import TrainingPackageState
from backend.dto.training_course_dto import TrainingProgressDto, TrainingSessionDto
from backend.training.byte_range import (
    RangeSpec,
    ResolvedRange,
    UnsatisfiableRange,
    resolve_range,
)
from backend.training.scorm_package import RESERVED_PREFIX
from backend.training.training_content_token import (
    InvalidContentToken,
    issue_content_token,
    verify_content_token,
)

# Served from the token path so the player is same-origin with the course --
# which is the whole reason the course can find window.API. Reserved, and
# package uploads reject any entry that could collide with it.
PLAYER_PATH = "__player.html"

_PLAYER_DIR = pathlib.Path(__file__).parent / "player"

# Ours to serve, by exact name. Everything else under the reserved prefix is
# refused: the reservation exists so a package can never answer for one of
# these, and a prefix match would hand that back.
PLAYER_ASSETS = {
    PLAYER_PATH: ("player.html", "text/html"),
    "__scorm12.min.js": ("scorm12.min.js", "text/javascript"),
    "__bridge.js": ("bridge.js", "text/javascript"),
}

# Static files, read once at import rather than on every request -- a course
# in progress commits roughly every 20 seconds (spec 6.4), and none of this
# ever changes without a redeploy.
_PLAYER_ASSET_BYTES = {
    path: (_PLAYER_DIR / name).read_bytes() for path, (name, _) in PLAYER_ASSETS.items()
}


def _score(value) -> str | None:
    """A stored score column as a string, or None if there is no score.

    Never a float: the jsonable_encoder turns a Decimal into one, and a score
    of 82.50 would come back as 82.5 or worse (see the leave module's DTOs
    for the same fix).
    """
    return None if value is None else f"{value:.2f}"


def _progress_payload(progress) -> TrainingProgressDto | None:
    """The learner's stored CMI state, or None if there is none yet."""
    if progress is None:
        return None
    return TrainingProgressDto(
        lesson_status=progress.lesson_status,
        lesson_location=progress.lesson_location,
        suspend_data=progress.suspend_data,
        session_time_seconds=progress.session_time_seconds,
        score_raw=_score(progress.score_raw),
        score_min=_score(progress.score_min),
        score_max=_score(progress.score_max),
    )


@dataclass(frozen=True)
class ContentAsset:
    """One file, or one stretch of one, on its way back to the browser."""

    data: bytes
    content_type: str
    # Set only when `data` is part of the file rather than all of it, which is
    # what tells the route to answer 206 instead of 200.
    partial: ResolvedRange | None = None


def _slice_in_memory(
    data: bytes, content_type: str, byte_range: RangeSpec | None
) -> ContentAsset:
    """Cut a file already held in memory down to the range asked for.

    Only the player's own files reach this: a few kilobytes each, read once at
    import, so slicing them costs nothing worth avoiding.

    Raises:
        UnsatisfiableRange: The range names no byte of the file.
    """
    if byte_range is None:
        return ContentAsset(data=data, content_type=content_type)
    resolved = resolve_range(byte_range, len(data))
    if resolved is None:
        raise UnsatisfiableRange(len(data))
    return ContentAsset(
        data=data[resolved.start : resolved.end + 1],
        content_type=content_type,
        partial=resolved,
    )


class TrainingContentService:
    """Issues content sessions, and answers requests made with them."""

    def __init__(
        self,
        logger,
        signing_key,
        content_host,
        training_repository,
        training_course_repository,
        training_course_package_repository,
        training_progress_repository,
        training_storage,
    ):
        """
        Args:
            logger: Injected logger.
            signing_key (str | None): TRAINING_TOKEN_SIGNING_KEY.
            content_host (str | None): TRAINING_CONTENT_HOST.
            training_repository (TrainingRepository): The assignment a token
                is issued against. Read when a session opens and never again:
                a token names its package outright, so serving a file has no
                assignment to look up.
            training_course_repository (TrainingCourseRepository): The course
                behind the assignment, read to answer one question: whether
                it is still active. A learner's door closes with the course.
            training_course_package_repository (TrainingCoursePackageRepository):
                Resolves the course's LIVE package when a session opens, and
                the package a token names when a file is asked for.
            training_progress_repository (TrainingProgressRepository): The
                learner's stored progress, seeded back into the page.
            training_storage (TrainingStorage): Object storage.
        """
        self.logger = logger
        self.signing_key = signing_key
        self.content_host = content_host
        self.training_repository = training_repository
        self.training_course_repository = training_course_repository
        self.training_course_package_repository = training_course_package_repository
        self.training_progress_repository = training_progress_repository
        self.training_storage = training_storage

    async def open_session(
        self, session, training_id: int, user_id: int
    ) -> TrainingSessionDto:
        """Mint a content URL for one person's own assignment.

        Always the course's live package, whoever is calling. An admin opening
        their own assignment is a learner here; the staged package is reached
        through open_trial_session and nowhere else. The content origin has no
        cookie and no Access application, so the token is the whole credential
        -- which package it names has to be decided at signing time, never by
        a caller asking for one.

        Args:
            session: The active async database session.
            training_id (int): The assignment being opened.
            user_id (int): Who is opening it.

        Returns:
            TrainingSessionDto: Where the course loads from, the token that
                names this run when the page posts progress back, when that
                token expires, and the learner's stored progress to seed the
                CMI model with (None if this assignment has never been opened
                before).

        Raises:
            ValueError: Not configured, or no such assignment.
            PermissionError: The assignment belongs to somebody else.
        """
        return await self._open(
            session, training_id, user_id, TrainingPackageState.LIVE
        )

    async def open_trial_session(
        self, session, training_id: int, user_id: int
    ) -> TrainingSessionDto:
        """Mint a content URL for a verifier's run of the staged package.

        Everything but which package it names is the learner's own path, on
        purpose: a trial that ran through different code would prove less than
        one that runs through the code a learner will.

        Args:
            session: The active async database session.
            training_id (int): The trial assignment being opened.
            user_id (int): Who is opening it.

        Returns:
            TrainingSessionDto: Same shape as `open_session`, naming the
                course's pending package instead of its live one, and never
                carrying progress to resume from.

        Raises:
            ValueError: Not configured, no such assignment, or nothing is
                staged on this course to try.
            PermissionError: The assignment belongs to somebody else.
        """
        return await self._open(
            session, training_id, user_id, TrainingPackageState.PENDING
        )

    async def _open(
        self, session, training_id: int, user_id: int, state
    ) -> TrainingSessionDto:
        """The body both session endpoints share, minus which slot they read.

        Raises:
            ValueError: Not configured, no such assignment, no course, or the
                slot this session wanted is empty.
            PermissionError: The assignment belongs to somebody else.
            ConflictError: The course is deactivated, on the learner's path.
        """
        self._require_configuration()

        assignment = await self.training_repository.get_training_by_id(
            session, training_id
        )
        if assignment is None:
            raise ValueError(f"No training assignment with id {training_id}.")
        if assignment.user_id != user_id:
            raise PermissionError("This training belongs to somebody else.")
        if assignment.course_id is None:
            raise ValueError("This training has no course attached.")

        # A deactivated course is closed to the people already on it, not
        # only to new assignments -- somebody part-way through is locked out
        # the moment it is turned off, and their progress row is kept for if
        # it is turned back on. Only the learner's door: the staged slot is
        # the trial's, and the repair sequence a trial exists for runs
        # entirely on a course that is off.
        if state is TrainingPackageState.LIVE:
            course = await self.training_course_repository.get_course_by_id(
                session, assignment.course_id
            )
            if course is None:
                raise ValueError(f"No training course with id {assignment.course_id}.")
            if not course.is_active:
                raise ConflictError(
                    "This course has been deactivated and can no longer be "
                    "taken. Your progress is kept."
                )

        package = await self.training_course_package_repository.get_by_state(
            session, assignment.course_id, state
        )
        if package is None:
            raise ValueError("This course has no package to open.")
        if not package.entry_path:
            raise ValueError("This course has no entry page to open.")

        # A trial starts from nothing, whatever this assignment's row holds.
        # The progress row is keyed per assignment, not per package, so what
        # it holds was written by whichever package last ran on it -- never by
        # the staged one being tried. Seeded back in, that state resumes the
        # trial onto a bookmark from a different package, and a row carrying a
        # finishing lesson_status is worse: the player re-sends the whole
        # model on its first commit, and the staged package is stamped
        # verified with nobody having run it. This read leaves the row alone;
        # the trial's own commits still overwrite it afterwards.
        progress = None
        if state is TrainingPackageState.LIVE:
            progress = await self.training_progress_repository.get_by_training_id(
                session, training_id
            )

        opened = self._mint(package, training_id, user_id, progress)
        # One line per course opening, not per file: this is the only record
        # tying a burst of content requests back to a person and a package.
        self.logger.info(
            "[TrainingContentService] user %s opened training %s (course %s, "
            "%s package %s, prefix %s); token expires at %s",
            user_id,
            training_id,
            assignment.course_id,
            state.value,
            package.package_id,
            package.storage_prefix,
            opened.expires_at,
        )
        return opened

    async def open_preview_session(
        self, session, course_id: int, user_id: int
    ) -> TrainingSessionDto:
        """Open the live package of a course to look at, not to run.

        There is no assignment here and none is minted: a preview is an
        administrator asking what learners are being served right now, and an
        assignment would put a row in the progress table for a run nobody
        took. The token it signs names no assignment either, which is what
        every write path refuses on.

        The live slot is the only one this reads. The staged slot has its own
        door -- the trial run -- which exists precisely because running a
        staged package is a different act with different consequences.

        Args:
            session: The active async database session.
            course_id (int): The course whose live package to open.
            user_id (int): The administrator looking.

        Returns:
            TrainingSessionDto: Where the live package loads from, with no
            progress to resume.

        Raises:
            ValueError: Not configured, or the course has nothing live.
        """
        self._require_configuration()

        package = await self.training_course_package_repository.get_by_state(
            session, course_id, TrainingPackageState.LIVE
        )
        if package is None:
            raise ValueError("This course has no live package to preview.")
        if not package.entry_path:
            raise ValueError("This course has no entry page to open.")

        self.logger.info(
            "[TrainingContentService] user %s previewed course %s "
            "(live package %s, prefix %s)",
            user_id,
            course_id,
            package.package_id,
            package.storage_prefix,
        )
        return self._mint(package, None, user_id, None)

    def _mint(
        self, package, training_id: int | None, user_id: int, progress
    ) -> TrainingSessionDto:
        """Sign one run of one package and say where it loads from."""
        token, expires_at = issue_content_token(
            self.signing_key, training_id, user_id, package_id=package.package_id
        )
        return TrainingSessionDto(
            content_base_url=f"https://{self.content_host}/p/{token}/",
            session_token=token,
            entry_path=package.entry_path,
            player_path=PLAYER_PATH,
            expires_at=expires_at,
            progress=_progress_payload(progress),
        )

    def _require_configuration(self) -> None:
        """Refuse to work half-configured, saying which half in the log only.

        Raises:
            ValueError: Content hosting is not configured.
        """
        missing = [
            name
            for name, value in (
                ("TRAINING_CONTENT_HOST", self.content_host),
                ("TRAINING_TOKEN_SIGNING_KEY", self.signing_key),
            )
            if not value
        ]
        if not missing:
            return
        # The variable names are for whoever runs the environment. The message
        # goes to a browser, so it carries none of them.
        self.logger.error(
            "[TrainingContentService] training content is not configured; missing %s",
            ", ".join(missing),
        )
        raise ValueError("Training content is not available.")

    async def read_asset(
        self,
        session,
        token: str,
        asset_path: str,
        byte_range: RangeSpec | None = None,
    ) -> ContentAsset:
        """Resolve one file requested from the content origin.

        The token names a package by id; the prefix behind that id is looked
        up here, per request, and never carried in the token. A package's own
        prefix does not move, so this is not about staleness -- it is what
        keeps an object key out of a URL the course's own JavaScript can read.

        A replacement deletes the row the open tab's token names, so its next
        file 404s and the player says so. That is the point: the alternative,
        resolving the course's current live package instead, hands a tab a
        package it never started while its in-memory CMI model still belongs
        to the old one.

        A range changes only how much of the file comes back. Every check
        below runs first and unchanged: a range is not a way past the token,
        the package boundary or the reserved names.

        Args:
            session: The active async database session.
            token (str): The token from the URL path.
            asset_path (str): The rest of the path, relative to the package.
            byte_range (RangeSpec | None): The range the browser asked for, or
                None for the whole file.

        Returns:
            ContentAsset: Bytes and Content-Type, and the resolved range when
            only part of the file is coming back.

        Raises:
            InvalidContentToken: Bad or expired token.
            FileNotFoundError: No such file, or the token's package is gone.
            PermissionError: The path escapes the package.
            UnsatisfiableRange: The range names no byte of the file.
        """
        self._require_configuration()

        try:
            claims = verify_content_token(self.signing_key, token)
        except InvalidContentToken as error:
            # Info, not warning: a tab left open past the token's twelve hours
            # produces one of these for every file the page still tries to
            # load, and the fix is a refresh rather than an investigation. The
            # token itself is not logged -- it is the credential.
            self.logger.info(
                "[TrainingContentService] refused a content token: %s", error
            )
            raise

        normalised = posixpath.normpath(asset_path.lstrip("/"))
        if normalised.startswith("..") or posixpath.isabs(normalised):
            # Path is course-controlled, so %r: it is escaped, not pasted.
            # training_id is None for a preview, so package_id is what still
            # names the run when this fires during one.
            self.logger.warning(
                "[TrainingContentService] training %s package %s asked for "
                "%r, which escapes the package",
                claims.training_id,
                claims.package_id,
                asset_path,
            )
            raise PermissionError("Asset path escapes the package.")

        # The reserved space is ours. Uploads refuse these names, so resolving
        # one against the package could only ever serve a file that arrived
        # some other way -- exactly the collision the reservation prevents.
        # Ahead of the course lookup: the player has to load even when the
        # course has no package yet.
        if normalised.startswith(RESERVED_PREFIX):
            known = PLAYER_ASSETS.get(normalised)
            if known is None:
                self.logger.warning(
                    "[TrainingContentService] training %s asked for %r under "
                    "the reserved prefix, which is not a player asset",
                    claims.training_id,
                    normalised,
                )
                raise FileNotFoundError(normalised)
            _, content_type = known
            return _slice_in_memory(
                _PLAYER_ASSET_BYTES[normalised], content_type, byte_range
            )

        package = await self.training_course_package_repository.get_by_id(
            session, claims.package_id
        )
        if package is None:
            # Info, not warning: every file an open tab still asks for after a
            # replacement produces one of these, and the fix is a reload.
            self.logger.info(
                "[TrainingContentService] package %s behind training %s is "
                "gone; the tab holding this token needs to reload",
                claims.package_id,
                claims.training_id,
            )
            raise FileNotFoundError("This package is no longer served.")

        object_key = posixpath.join(package.storage_prefix, normalised)
        if byte_range is not None:
            return await self._read_range(
                claims.training_id, claims.package_id, object_key, byte_range
            )

        found = await asyncio.to_thread(self.training_storage.get, object_key)
        if found is None:
            self._no_object(claims.training_id, claims.package_id, object_key)

        data, content_type = found
        # Debug: a single course load asks for hundreds of files.
        self.logger.debug(
            "[TrainingContentService] training %s: served %r (%s bytes, %s)",
            claims.training_id,
            object_key,
            len(data),
            content_type,
        )
        return ContentAsset(data=data, content_type=content_type)

    async def _read_range(
        self,
        training_id: int | None,
        package_id: int,
        object_key: str,
        byte_range: RangeSpec,
    ) -> ContentAsset:
        """Fetch only the bytes asked for, never the whole object.

        Two calls to storage rather than one, because neither ``bytes=-500``
        nor ``bytes=100-`` means anything until the size comes back. That is
        still far cheaper than pulling a 3 MB video through this process for
        every seek a learner makes.

        Args:
            training_id (int | None): The run this read is on behalf of, for
                the log line only. None when the run is a preview.
            package_id (int): The package this read is on behalf of, for the
                log line only -- unlike training_id, never None, so it is
                what still names a preview's run.
            object_key (str): The storage key to read from.
            byte_range (RangeSpec): The range asked for.

        Raises:
            FileNotFoundError: No such object.
            UnsatisfiableRange: The range names no byte of it.
        """
        described = await asyncio.to_thread(self.training_storage.stat, object_key)
        if described is None:
            self._no_object(training_id, package_id, object_key)
        total_size, content_type = described

        resolved = resolve_range(byte_range, total_size)
        if resolved is None:
            raise UnsatisfiableRange(total_size)

        data = await asyncio.to_thread(
            self.training_storage.get_range, object_key, resolved.start, resolved.end
        )
        if data is None:
            # Gone between the two calls, which is what an upload replacing the
            # package underneath an open course looks like from here.
            self._no_object(training_id, package_id, object_key)

        self.logger.debug(
            "[TrainingContentService] training %s: served %r bytes %s-%s of %s (%s)",
            training_id,
            object_key,
            resolved.start,
            resolved.end,
            total_size,
            content_type,
        )
        return ContentAsset(data=data, content_type=content_type, partial=resolved)

    def _no_object(self, training_id: int | None, package_id: int, object_key: str):
        """Report a missing object and refuse.

        A course that lost its files 404s on every asset it references, which
        is what a stale prefix, a half-finished upload and a cleanup that
        deleted the wrong prefix all look like from here. Noisy on purpose: a
        healthy package produces none of these.

        Args:
            training_id (int | None): The run this read is on behalf of, for
                the log line only. None when the run is a preview.
            package_id (int): The package this read is on behalf of, for the
                log line only -- unlike training_id, never None, so it is
                what still names a preview's run.
            object_key (str): The storage key that was missing.

        Raises:
            FileNotFoundError: Always.
        """
        self.logger.warning(
            "[TrainingContentService] training %s package %s: no object at %r",
            training_id,
            package_id,
            object_key,
        )
        raise FileNotFoundError(object_key)


__all__ = [
    "ContentAsset",
    "InvalidContentToken",
    "PLAYER_ASSETS",
    "PLAYER_PATH",
    "TrainingContentService",
    "UnsatisfiableRange",
]
