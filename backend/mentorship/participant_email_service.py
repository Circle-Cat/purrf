"""Email with one person about one mentorship round, from the participant page."""

from backend.common.communication_enums import ContextType, InboxService
from backend.common.exceptions import NotFoundError
from backend.common.permissions import Permission
from backend.communication.person_email_service import (
    BodyFormat,
    EmailPolicy,
    choose_default,
    recipient_options,
)
from backend.dto.email_dto import EmailRefreshDto


class MentorshipParticipantEmailPolicy:
    """What one viewer may do with a person's mail about one round."""

    def __init__(
        self, rounds_repository, users_repository, person_email_service, aliases
    ):
        """
        Args:
            rounds_repository (MentorshipRoundRepository): Finds the round.
            users_repository (UsersRepository): Finds the person.
            person_email_service (PersonEmailService): The person's addresses.
            aliases (InboxAliases): The mentorship sending address.
        """
        self._rounds = rounds_repository
        self._users = users_repository
        self._person_email = person_email_service
        self._aliases = aliases

    async def resolve(self, session, round_id, user_id, viewer) -> EmailPolicy:
        """The policy for (person, round) as ``viewer`` sees it.

        Args:
            session (AsyncSession): The active DB session.
            round_id (int): The round; the threads' ``context_id``.
            user_id (int): The person.
            viewer (UserContextDto): Who is looking; MENTORSHIP_ADMIN_WRITE sends.

        Returns:
            EmailPolicy: Plain text, from the mentorship alias, to the
                person's verified addresses, the primary preselected when it is
                one of them, else the first.

        Raises:
            NotFoundError: The round or the person does not exist.
        """
        if await self._rounds.get_by_round_id(session, round_id) is None:
            raise NotFoundError(f"Mentorship round {round_id} does not exist.")
        if await self._users.get_user_by_user_id(session, user_id) is None:
            raise NotFoundError(f"User {user_id} does not exist.")
        addresses = await self._person_email.person_email_addresses(session, user_id)
        primary = next((a.address for a in addresses if a.is_primary), None)
        default = choose_default(addresses, primary)
        return EmailPolicy(
            user_id=user_id,
            context_type=ContextType.ACTIVITY,
            context_id=round_id,
            sender_address=self._aliases.alias_of(InboxService.MENTORSHIP),
            may_send=viewer.has_permission(Permission.MENTORSHIP_ADMIN_WRITE),
            body_format=BodyFormat.TEXT,
            recipient_options=tuple(
                recipient_options([a.address for a in addresses], default)
            ),
            default_to=default,
        )


class ParticipantEmailService:
    """The participant page's email actions; write methods commit."""

    def __init__(self, policy, person_email_service):
        """
        Args:
            policy (MentorshipParticipantEmailPolicy): Resolves each request.
            person_email_service (PersonEmailService): Reads, sends, refreshes.
        """
        self._policy = policy
        self._person_email = person_email_service

    async def _write_then_read(self, session, round_id, user_id, viewer, write):
        """Resolve the policy, run ``write(policy)``, commit, read back."""
        policy = await self._policy.resolve(session, round_id, user_id, viewer)
        await write(policy)
        await session.commit()
        return await self._person_email.conversation(session, policy)

    async def get_emails(self, session, round_id, user_id, viewer):
        """The person's threads for the round. Pure DB read."""
        policy = await self._policy.resolve(session, round_id, user_id, viewer)
        return await self._person_email.conversation(session, policy)

    async def send_email(
        self, session, round_id, user_id, viewer, *, to, subject, body
    ):
        """Send a new plain-text email, which opens a new thread. Commits.

        Raises:
            NotFoundError: Unknown round or person.
            ValueError: No mentorship alias, or the content or recipients are refused.
        """
        return await self._write_then_read(
            session,
            round_id,
            user_id,
            viewer,
            lambda policy: self._person_email.send_new(
                session,
                policy,
                sender_user_id=viewer.user_id,
                to=to,
                subject=subject,
                body=body,
            ),
        )

    async def reply(
        self,
        session,
        round_id,
        user_id,
        viewer,
        *,
        thread_id,
        body,
        last_seen_message_id,
    ):
        """Reply in one of the person's round threads. Commits.

        Raises:
            NotFoundError: Unknown round, person, or thread of theirs.
            ConflictError: ``THREAD_CHANGED`` when a newer message arrived.
            ValueError: No mentorship alias, empty body, nobody to reply to.
        """
        return await self._write_then_read(
            session,
            round_id,
            user_id,
            viewer,
            lambda policy: self._person_email.reply(
                session,
                policy,
                sender_user_id=viewer.user_id,
                thread_id=thread_id,
                body=body,
                last_seen_message_id=last_seen_message_id,
            ),
        )

    async def refresh(self, session, round_id, user_id, viewer) -> EmailRefreshDto:
        """Pull the person's round threads from Gmail. Commits."""
        policy = await self._policy.resolve(session, round_id, user_id, viewer)
        new_replies = await self._person_email.refresh(session, policy)
        await session.commit()
        return EmailRefreshDto(
            conversation=await self._person_email.conversation(session, policy),
            new_replies=new_replies,
        )

    async def attachment(
        self, session, round_id, user_id, viewer, *, message_id, index
    ):
        """One attachment of a message in the person's round threads."""
        policy = await self._policy.resolve(session, round_id, user_id, viewer)
        return await self._person_email.read_attachment(
            session, policy, message_id, index
        )
