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
from backend.training.training_content_service import InvalidContentToken

# Assets are immutable for as long as the token in their path is: a new upload
# mints new URLs. Private, because the response is one learner's course.
_CACHE_CONTROL = "private, max-age=3600"

# How much of a rejected Host header is worth keeping. It is whatever the
# client sent, so it is truncated as well as escaped before it is logged.
_LOGGED_HOST_LIMIT = 128


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
        """Return one file from the package behind this token.

        Answers 404 rather than 403 on the wrong host: that a course exists at
        this path on some other hostname is not information the API origin
        should confirm.
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

        # Each of these is logged where it is decided, with the training id and
        # the object key the bare status code cannot carry.
        try:
            async with self.database.session() as session:
                asset = await self.training_content_service.read_asset(
                    session, token, asset_path
                )
        except InvalidContentToken:
            # 401 so the app page can tell the learner to refresh, which mints
            # a new token. Silent renewal would not help: the assets already
            # loaded carry the old one in their URLs.
            return Response(status_code=HTTPStatus.UNAUTHORIZED)
        except PermissionError:
            return Response(status_code=HTTPStatus.NOT_FOUND)
        except FileNotFoundError:
            return Response(status_code=HTTPStatus.NOT_FOUND)

        return Response(
            content=asset.data,
            media_type=asset.content_type,
            headers={"Cache-Control": _CACHE_CONTROL},
        )
