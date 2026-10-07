"""What each kind of approval declares to the shared approval service.

The service runs the flow every approval has in common: a named reviewer,
only that reviewer decides, an optional reason from the raiser and a
required one on every rejection, the raiser may withdraw, and approving re-checks and acts in one transaction. A handler
supplies what differs between kinds: what the request is about, who may
review it, what has to hold to raise and to approve it, and what approving
it does.
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from backend.common.permissions import Permission
from backend.entity.approval_request_entity import ApprovalRequestEntity


class ApprovalHandler(ABC):
    """One kind of approval. Subclasses set the class attributes and
    implement the abstract methods; the hooks with a body are optional.

    No hook commits. Each runs inside the service's transaction, so a
    failure anywhere rolls back everything the request did.
    """

    # The registry key and the kind of thing a request of this action is
    # about, as stored on the row.
    action: ClassVar[str]
    target_type: ClassVar[str]

    # The subject and the three event types recorded for this action. Who
    # is told about each event is up to the resolvers registered for them.
    subject_type: ClassVar[str]
    raised_event: ClassVar[str]
    reassigned_event: ClassVar[str]
    decided_event: ClassVar[str]

    # Who may be named as the reviewer. None means the raiser does not
    # choose: assign_reviewer picks the reviewer instead.
    review_permission: ClassVar[Permission | None]

    # Whether the raiser may hand a pending request to another reviewer.
    # Off where the raiser never chose the reviewer in the first place.
    raiser_may_reassign: ClassVar[bool] = True

    @abstractmethod
    def subject_id(self, request: ApprovalRequestEntity) -> int:
        """The subject id the events of this request are recorded against.

        Args:
            request (ApprovalRequestEntity): The request.

        Returns:
            int: The subject id.
        """

    async def event_details(self, session, request: ApprovalRequestEntity) -> dict:
        """Extra fields to snapshot onto every event of this request, such as
        the name of what it is about. A notification can be rendered long
        after the event, and has to say what was true when it happened.

        Args:
            session (AsyncSession): Active database async session.
            request (ApprovalRequestEntity): The request.

        Returns:
            dict: Fields merged into the event's details. The service's own
                fields (requestId, action, decision, previousReviewerId) win
                over any of the same name.
        """
        return {}

    async def assign_reviewer(
        self, session, *, raised_by: int, target_id: str, payload: dict
    ) -> int:
        """Pick the reviewer for a handler with no review_permission.

        Args:
            session (AsyncSession): Active database async session.
            raised_by (int): Who is raising the request.
            target_id (str): What it is about.
            payload (dict): The request's payload.

        Returns:
            int: The user who will review it.

        Raises:
            ValueError: When nobody can be assigned.
        """
        raise NotImplementedError(
            f"{self.action} names no review permission and assigns no reviewer"
        )

    @abstractmethod
    async def check_raise(
        self, session, *, raised_by: int, target_id: str, payload: dict
    ) -> None:
        """Refuse a request that cannot be raised: its target is missing or
        is not in a state this action applies to. Called after the reviewer
        has been checked.

        Args:
            session (AsyncSession): Active database async session.
            raised_by (int): Who is raising the request.
            target_id (str): What it is about.
            payload (dict): The request's payload.

        Raises:
            ValueError, PermissionError or ConflictError: Whatever the
                refusal is, mapped to its HTTP status by the error handler.
        """

    async def problems_at_approval(
        self, session, request: ApprovalRequestEntity
    ) -> list[str]:
        """What no longer holds now that the reviewer approves. An empty list
        lets the approval go ahead; anything in it refuses the approval and
        leaves the request pending, so the reviewer can only reject it.

        Args:
            session (AsyncSession): Active database async session.
            request (ApprovalRequestEntity): The request, locked.

        Returns:
            list[str]: One sentence per problem, shown to the reviewer.
        """
        return []

    @abstractmethod
    async def execute(
        self, session, request: ApprovalRequestEntity, *, actor_id: int
    ) -> None:
        """Do what the request asked for. Runs after problems_at_approval
        found nothing, in the same transaction as closing the request.

        Args:
            session (AsyncSession): Active database async session.
            request (ApprovalRequestEntity): The request, locked.
            actor_id (int): The reviewer approving it.
        """

    async def revert(self, session, request: ApprovalRequestEntity) -> None:
        """Put the target back the way it was before the request was raised.
        Called when the request is rejected or withdrawn.

        Args:
            session (AsyncSession): Active database async session.
            request (ApprovalRequestEntity): The request, locked.
        """

    async def after_commit(self, request: ApprovalRequestEntity) -> None:
        """Work that may only happen once the approval is committed, such as
        clearing something outside the database. A failure here is logged,
        not raised: the approval has already happened.

        Args:
            request (ApprovalRequestEntity): The approved request.
        """
