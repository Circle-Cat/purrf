"""Serving course files to a browser that has a signed token and no cookie."""

import asyncio
import pathlib
import posixpath
import time
from dataclasses import dataclass

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

# How long the assignment behind a token is reused for. Which course a token
# names cannot change, so this is bounded only to let a deleted assignment
# stop answering; the storage prefix is deliberately not cached with it.
ASSIGNMENT_CACHE_SECONDS = 60

# Entries are only evicted when they are read, so an assignment nobody comes
# back to would otherwise sit here for the life of the process.
_ASSIGNMENT_CACHE_LIMIT = 512


def _now() -> float:
    """The clock the assignment cache ages against.

    Its own function so a test can move it without patching time.monotonic,
    which the running event loop also reads.
    """
    return time.monotonic()


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
                is issued against.
            training_course_package_repository (TrainingCoursePackageRepository):
                Resolves the LIVE package a course serves content from.
            training_progress_repository (TrainingProgressRepository): The
                learner's stored progress, seeded back into the page.
            training_storage (TrainingStorage): Object storage.
        """
        self.logger = logger
        self.signing_key = signing_key
        self.content_host = content_host
        self.training_repository = training_repository
        self.training_course_package_repository = training_course_package_repository
        self.training_progress_repository = training_progress_repository
        self.training_storage = training_storage
        # training_id -> (course_id, monotonic deadline). Not keyed on the
        # token: the token is the credential, and two tokens naming the same
        # assignment resolve to the same course anyway.
        self._assignments: dict[int, tuple[int, float]] = {}

    async def open_session(
        self, session, training_id: int, user_id: int
    ) -> TrainingSessionDto:
        """Mint a content URL for one person's own assignment.

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

        package = await self.training_course_package_repository.get_by_state(
            session, assignment.course_id, TrainingPackageState.LIVE
        )
        if package is None:
            raise ValueError("This course has no package to open.")
        if not package.entry_path:
            raise ValueError("This course has no entry page to open.")

        progress = await self.training_progress_repository.get_by_training_id(
            session, training_id
        )

        token, expires_at = issue_content_token(self.signing_key, training_id, user_id)
        # One line per course opening, not per file: this is the only record
        # tying a burst of content requests back to a person and a package.
        self.logger.info(
            "[TrainingContentService] user %s opened training %s (course %s, "
            "prefix %s); token expires at %s",
            user_id,
            training_id,
            assignment.course_id,
            package.storage_prefix,
            expires_at,
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

        The prefix is looked up here, per request, never carried in the token:
        a token outlives an upload, and one holding a stale prefix would start
        404ing the moment the cleanup ran.

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
            FileNotFoundError: No such file, or the course has no package.
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
            self.logger.warning(
                "[TrainingContentService] training %s asked for %r, which "
                "escapes the package",
                claims.training_id,
                asset_path,
            )
            raise PermissionError("Asset path escapes the package.")

        # The reserved space is ours. Uploads refuse these names, so resolving
        # one against the package could only ever serve a file that arrived
        # some other way -- exactly the collision the reservation prevents.
        # Ahead of the course lookup: the player has to load even when the
        # course row has no package yet.
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

        course_id = await self._course_id_behind(session, claims.training_id)

        package = await self.training_course_package_repository.get_by_state(
            session, course_id, TrainingPackageState.LIVE
        )
        if package is None:
            self.logger.warning(
                "[TrainingContentService] course %s behind training %s has no "
                "package to serve",
                course_id,
                claims.training_id,
            )
            raise FileNotFoundError("This course has no package.")

        object_key = posixpath.join(package.storage_prefix, normalised)
        if byte_range is not None:
            return await self._read_range(claims.training_id, object_key, byte_range)

        found = await asyncio.to_thread(self.training_storage.get, object_key)
        if found is None:
            self._no_object(claims.training_id, object_key)

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

    async def _course_id_behind(self, session, training_id: int) -> int:
        """Which course a token's assignment names, read once and held.

        A course load asks for hundreds of files and every one of them used to
        re-read the assignment, whose answer cannot change: an assignment is
        never re-pointed at a different course. Only the storage prefix moves,
        and that is read fresh per request one caller up.

        A missing assignment is not remembered. Caching the refusal would keep
        refusing a learner whose row is created a moment later.

        Raises:
            FileNotFoundError: No assignment, or it has no course.
        """
        cached = self._assignments.get(training_id)
        if cached is not None:
            course_id, deadline = cached
            if _now() < deadline:
                return course_id
            del self._assignments[training_id]

        assignment = await self.training_repository.get_training_by_id(
            session, training_id
        )
        if assignment is None or assignment.course_id is None:
            self.logger.warning(
                "[TrainingContentService] token for training %s has no course "
                "behind it; the assignment is %s",
                training_id,
                "gone" if assignment is None else "not attached to a course",
            )
            raise FileNotFoundError("No course behind this token.")

        if len(self._assignments) >= _ASSIGNMENT_CACHE_LIMIT:
            self._evict_stale_assignments()
        self._assignments[training_id] = (
            assignment.course_id,
            _now() + ASSIGNMENT_CACHE_SECONDS,
        )
        return assignment.course_id

    def _evict_stale_assignments(self) -> None:
        """Drop what has expired, and everything if that was not enough.

        Clearing outright costs one extra read per learner still on a course,
        which is cheaper than tracking use order for a table this small.
        """
        now = _now()
        self._assignments = {
            training_id: entry
            for training_id, entry in self._assignments.items()
            if now < entry[1]
        }
        if len(self._assignments) >= _ASSIGNMENT_CACHE_LIMIT:
            self._assignments.clear()

    async def _read_range(
        self, training_id: int, object_key: str, byte_range: RangeSpec
    ) -> ContentAsset:
        """Fetch only the bytes asked for, never the whole object.

        Two calls to storage rather than one, because neither ``bytes=-500``
        nor ``bytes=100-`` means anything until the size comes back. That is
        still far cheaper than pulling a 3 MB video through this process for
        every seek a learner makes.

        Raises:
            FileNotFoundError: No such object.
            UnsatisfiableRange: The range names no byte of it.
        """
        described = await asyncio.to_thread(self.training_storage.stat, object_key)
        if described is None:
            self._no_object(training_id, object_key)
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
            self._no_object(training_id, object_key)

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

    def _no_object(self, training_id: int, object_key: str):
        """Report a missing object and refuse.

        A course that lost its files 404s on every asset it references, which
        is what a stale prefix, a half-finished upload and a cleanup that
        deleted the wrong prefix all look like from here. Noisy on purpose: a
        healthy package produces none of these.

        Raises:
            FileNotFoundError: Always.
        """
        self.logger.warning(
            "[TrainingContentService] training %s: no object at %r",
            training_id,
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
