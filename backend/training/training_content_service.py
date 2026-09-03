"""Serving course files to a browser that has a signed token and no cookie."""

import pathlib
import posixpath
from dataclasses import dataclass

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


def _progress_payload(progress) -> dict:
    """The learner's stored CMI state, or ``{}`` if there is none yet."""
    if progress is None:
        return {}
    return {
        "lessonStatus": progress.lesson_status,
        "lessonLocation": progress.lesson_location,
        "suspendData": progress.suspend_data,
        "sessionTimeSeconds": progress.session_time_seconds,
        "scoreRaw": _score(progress.score_raw),
        "scoreMin": _score(progress.score_min),
        "scoreMax": _score(progress.score_max),
    }


@dataclass(frozen=True)
class ContentAsset:
    """One file on its way back to the browser."""

    data: bytes
    content_type: str


class TrainingContentService:
    """Issues content sessions, and answers requests made with them."""

    def __init__(
        self,
        logger,
        signing_key,
        content_host,
        training_repository,
        training_course_repository,
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
            training_course_repository (TrainingCourseRepository): Resolves the
                live storage prefix.
            training_progress_repository (TrainingProgressRepository): The
                learner's stored progress, seeded back into the page.
            training_storage (TrainingStorage): Object storage.
        """
        self.logger = logger
        self.signing_key = signing_key
        self.content_host = content_host
        self.training_repository = training_repository
        self.training_course_repository = training_course_repository
        self.training_progress_repository = training_progress_repository
        self.training_storage = training_storage

    async def open_session(self, session, training_id: int, user_id: int) -> dict:
        """Mint a content URL for one person's own assignment.

        Args:
            session: The active async database session.
            training_id (int): The assignment being opened.
            user_id (int): Who is opening it.

        Returns:
            dict: ``contentBaseUrl``, ``expiresAt``, and the learner's stored
                ``progress`` to seed the CMI model with (``{}`` if this
                assignment has never been opened before).

        Raises:
            ValueError: Not configured, or no such assignment.
            PermissionError: The assignment belongs to somebody else.
        """
        if not self.content_host:
            raise ValueError(
                "Training content is not configured; set TRAINING_CONTENT_HOST."
            )

        assignment = await self.training_repository.get_training_by_id(
            session, training_id
        )
        if assignment is None:
            raise ValueError(f"No training assignment with id {training_id}.")
        if assignment.user_id != user_id:
            raise PermissionError("This training belongs to somebody else.")
        if assignment.course_id is None:
            raise ValueError("This training has no course attached.")

        course = await self.training_course_repository.get_course_by_id(
            session, assignment.course_id
        )
        if course is None or not course.storage_prefix:
            raise ValueError("This course has no package to open.")

        progress = await self.training_progress_repository.get_by_training_id(
            session, training_id
        )

        token, expires_at = issue_content_token(self.signing_key, training_id, user_id)
        return {
            "contentBaseUrl": f"https://{self.content_host}/p/{token}/",
            "entryPath": course.entry_path,
            "playerPath": PLAYER_PATH,
            "expiresAt": expires_at,
            "progress": _progress_payload(progress),
        }

    async def read_asset(self, session, token: str, asset_path: str) -> ContentAsset:
        """Resolve one file requested from the content origin.

        The prefix is looked up here, per request, never carried in the token:
        a token outlives an upload, and one holding a stale prefix would start
        404ing the moment the cleanup ran.

        Args:
            session: The active async database session.
            token (str): The token from the URL path.
            asset_path (str): The rest of the path, relative to the package.

        Returns:
            ContentAsset: Bytes and Content-Type.

        Raises:
            InvalidContentToken: Bad or expired token.
            FileNotFoundError: No such file, or the course has no package.
            PermissionError: The path escapes the package.
        """
        claims = verify_content_token(self.signing_key, token)

        normalised = posixpath.normpath(asset_path.lstrip("/"))
        if normalised.startswith("..") or posixpath.isabs(normalised):
            raise PermissionError("Asset path escapes the package.")

        # The reserved space is ours. Uploads refuse these names, so resolving
        # one against the package could only ever serve a file that arrived
        # some other way -- exactly the collision the reservation prevents.
        # Ahead of the course lookup: the player has to load even when the
        # course row has no package yet.
        if normalised.startswith(RESERVED_PREFIX):
            known = PLAYER_ASSETS.get(normalised)
            if known is None:
                raise FileNotFoundError(normalised)
            _, content_type = known
            return ContentAsset(
                data=_PLAYER_ASSET_BYTES[normalised], content_type=content_type
            )

        assignment = await self.training_repository.get_training_by_id(
            session, claims.training_id
        )
        if assignment is None or assignment.course_id is None:
            raise FileNotFoundError("No course behind this token.")

        course = await self.training_course_repository.get_course_by_id(
            session, assignment.course_id
        )
        if course is None or not course.storage_prefix:
            raise FileNotFoundError("This course has no package.")

        found = self.training_storage.get(
            posixpath.join(course.storage_prefix, normalised)
        )
        if found is None:
            raise FileNotFoundError(normalised)

        data, content_type = found
        return ContentAsset(data=data, content_type=content_type)


__all__ = [
    "ContentAsset",
    "InvalidContentToken",
    "PLAYER_ASSETS",
    "PLAYER_PATH",
    "TrainingContentService",
]
