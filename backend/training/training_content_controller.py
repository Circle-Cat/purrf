"""The one route that answers on the course content origin.

Everything here is shaped by a single fact: the JavaScript that makes these
requests is third-party course code we do not review, and it runs on whichever
origin serves it. Serving it from the app's origin would put it same-origin
with the API, where it could read the Access cookie and call any endpoint as
the learner. So this route refuses to answer anywhere but the content host --
not as defence in depth, but because a path-only exemption in the
authentication middleware would otherwise open the same URL on the API host.
"""

from http import HTTPStatus

from fastapi import APIRouter, Request, Response

from backend.common.api_endpoints import TRAINING_CONTENT_ENDPOINT
from backend.training.byte_range import UnsatisfiableRange, parse_range_header
from backend.training.training_content_service import InvalidContentToken

# Assets are immutable for as long as the token in their path is: a new upload
# mints new URLs. Private, because the response is one learner's course.
_CACHE_CONTROL = "private, max-age=3600"

# How much of a rejected Host header is worth keeping. It is whatever the
# client sent, so it is truncated as well as escaped before it is logged.
_LOGGED_HOST_LIMIT = 128

# Same treatment for a Range header, for the same reason.
_LOGGED_RANGE_LIMIT = 128


class TrainingContentController:
    """Serves package files against a signed token, with no cookie involved."""

    def __init__(self, training_content_service, content_host, database, logger):
        """
        Args:
            training_content_service (TrainingContentService): Token checking
                and object reads.
            content_host (str | None): TRAINING_CONTENT_HOST. When absent the
                route refuses everything, which is the right behaviour in an
                environment where content hosting is not configured.
            database: Async session provider.
            logger: Injected logger.
        """
        self.training_content_service = training_content_service
        self.content_host = content_host
        self.database = database
        self.logger = logger
        self.router = APIRouter(tags=["training-content"])

        # No authenticate(): the course cannot present an Access JWT, and the
        # signature in the path is what stands in for one.
        self.router.add_api_route(
            TRAINING_CONTENT_ENDPOINT,
            endpoint=self.get_asset,
            methods=["GET"],
            response_model=None,
        )

    def _wrong_host(self, request: Request) -> bool:
        """Whether this request arrived anywhere but the content origin."""
        return (
            not self.content_host
            or request.headers.get("host", "").split(":")[0] != self.content_host
        )

    async def get_asset(self, token: str, asset_path: str, request: Request):
        """Return one file, or one range of one, from the package behind this token.

        Answers 404 rather than 403 on the wrong host: that a course exists at
        this path on some other hostname is not information the API origin
        should confirm.

        Every answer that carries bytes advertises `Accept-Ranges: bytes`.
        Safari and iOS will not play a `<video>` or `<audio>` element served
        as a single 200, and nothing anywhere can seek without this.
        """
        if self._wrong_host(request):
            # %r, not %s: the Host header is whatever the client sent, and a
            # newline pasted into a log line forges a log line.
            self.logger.warning(
                "[TrainingContentController] refused a content request for "
                "host %r (content host is %r)",
                (request.headers.get("host") or "")[:_LOGGED_HOST_LIMIT],
                self.content_host,
            )
            return Response(status_code=HTTPStatus.NOT_FOUND)

        requested = request.headers.get("range")
        byte_range = parse_range_header(requested)
        if requested and byte_range is None:
            # A header we could not read is ignored rather than refused, so
            # the answer below is a 200. Worth a line: a media element getting
            # a whole file back where it asked for a range is silent from the
            # browser's side and looks like a course that will not play.
            self.logger.debug(
                "[TrainingContentController] ignored an unreadable Range header %r",
                requested[:_LOGGED_RANGE_LIMIT],
            )

        # Each of these is logged where it is decided, with the training id and
        # the object key the bare status code cannot carry.
        try:
            async with self.database.session() as session:
                asset = await self.training_content_service.read_asset(
                    session, token, asset_path, byte_range
                )
        except InvalidContentToken:
            # 401 so the app page can tell the learner to refresh, which mints
            # a new token. Silent renewal would not help: the assets already
            # loaded carry the old one in their URLs.
            return Response(status_code=HTTPStatus.UNAUTHORIZED)
        except UnsatisfiableRange as error:
            self.logger.info(
                "[TrainingContentController] refused Range %r against %s bytes",
                (requested or "")[:_LOGGED_RANGE_LIMIT],
                error.total_size,
            )
            # No Accept-Ranges on a 416: the status already says ranges are
            # understood, and the header belongs with a body. Content-Range
            # names the size so the client can ask for something that exists.
            return Response(
                status_code=HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{error.total_size}"},
            )
        except PermissionError:
            return Response(status_code=HTTPStatus.NOT_FOUND)
        except FileNotFoundError:
            return Response(status_code=HTTPStatus.NOT_FOUND)

        # A served asset gets no log line of its own: one course load is
        # hundreds of these, and a seek is hundreds more.
        headers = {"Cache-Control": _CACHE_CONTROL, "Accept-Ranges": "bytes"}
        if asset.partial is None:
            return Response(
                content=asset.data,
                media_type=asset.content_type,
                headers=headers,
            )

        headers["Content-Range"] = asset.partial.content_range()
        return Response(
            content=asset.data,
            status_code=HTTPStatus.PARTIAL_CONTENT,
            media_type=asset.content_type,
            headers=headers,
        )
