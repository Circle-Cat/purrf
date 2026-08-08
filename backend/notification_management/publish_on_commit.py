import functools
import json

from sqlalchemy import event as sqlalchemy_event
from sqlalchemy.orm import Session

from backend.common.logger import get_logger

logger = get_logger()

# The pair of listener functions currently registered with SQLAlchemy, kept
# so a repeat call to install_publish_listener() can remove them before
# adding a new pair instead of stacking a second pair on top of the first.
# Without this, calling it twice (e.g. an accidental double import at
# startup, or a test suite that installs a fresh publisher per test) would
# leave two listeners on the same Session class: the first one to run on any
# given commit would pop "pending_notification_ids" and publish, and every
# listener registered after it would see an empty list and silently do
# nothing -- so the *original* publisher would keep winning forever, and a
# newer one passed to a later install call would never be used.
_active_listeners: tuple | None = None


def _log_publish_failure(notification_id, topic_path: str, future) -> None:
    """Log a failure that only surfaced on the publish Future, not the call.

    ``PublisherClient.publish()`` batches messages and returns a
    ``concurrent.futures.Future`` immediately -- it does not wait for
    Pub/Sub to accept the message. The dominant real-world failures
    (missing topic, IAM permission denied, network trouble) resolve on
    that Future well after ``publish()`` itself has already returned
    normally, so the synchronous ``try``/``except`` around the call only
    ever catches the rare error raised before batching starts. Without
    this callback, every one of those real failures would be swallowed
    with no signal at all that publishing is broken.

    This callback's only job is observability: it must never raise, retry,
    or touch the notification row. The row is already committed as
    ``pending``; the ride-along sweep is what actually gets it published.

    Args:
        notification_id: The notification the failed message was for.
        topic_path (str): The topic the message was published to.
        future: The ``Future`` returned by ``publisher.publish()``.
    """
    exception = future.exception()
    if exception is not None:
        logger.error(
            "[Notifications] publish failed for %s on topic %s; leaving it "
            "pending for the ride-along sweep",
            notification_id,
            topic_path,
            exc_info=exception,
        )


def install_publish_listener(publisher, topic_path: str) -> None:
    """Publish one Pub/Sub message per notification once its transaction commits.

    Publishing cannot join the database transaction, so it happens after the
    commit succeeds. Doing it here rather than at each call site means the
    twenty-odd places that record events cannot forget it -- a forgotten
    publish is a notification that silently never sends.

    A publish that fails is logged and swallowed: the notification row is
    already committed as ``pending``, and the ride-along sweep in the
    delivery route will republish it. Raising here would fail a request
    whose business change already succeeded.

    Calling this more than once (e.g. accidental repeated startup wiring)
    replaces the previously installed listeners rather than stacking a
    second pair alongside them, so a notification is never published twice
    and a later publisher/topic never loses out to a stale earlier one.

    Args:
        publisher: Pub/Sub publisher client exposing ``publish(topic, data)``.
        topic_path (str): Fully qualified topic, ``projects/<p>/topics/<t>``.
    """
    global _active_listeners
    if _active_listeners is not None:
        previous_publish, previous_discard = _active_listeners
        sqlalchemy_event.remove(Session, "after_commit", previous_publish)
        sqlalchemy_event.remove(Session, "after_rollback", previous_discard)

    def _publish(session: Session) -> None:
        notification_ids = session.info.pop("pending_notification_ids", [])
        for notification_id in notification_ids:
            payload = json.dumps({"notification_id": notification_id}).encode()
            try:
                future = publisher.publish(topic_path, payload)
                future.add_done_callback(
                    functools.partial(_log_publish_failure, notification_id, topic_path)
                )
            except Exception:
                logger.exception(
                    "[Notifications] publish failed for %s; leaving it pending "
                    "for the ride-along sweep",
                    notification_id,
                )

    def _discard(session: Session) -> None:
        session.info.pop("pending_notification_ids", None)

    sqlalchemy_event.listens_for(Session, "after_commit")(_publish)
    sqlalchemy_event.listens_for(Session, "after_rollback")(_discard)
    _active_listeners = (_publish, _discard)
