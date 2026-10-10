"""What the recruiting Emails tab allows for one application."""

from backend.common.communication_enums import ContextType
from backend.communication.person_email_service import (
    BodyFormat,
    EmailPolicy,
    recipient_options,
)


class RecruitingApplicationEmailPolicy:
    """Builds an application's EmailPolicy for a caller BoardService has admitted."""

    def __init__(self, person_email_service, user_emails_repository):
        """
        Args:
            person_email_service (PersonEmailService): The applicant's
                addresses and the recruiting sending address.
            user_emails_repository (UserEmailsRepository): The contact address.
        """
        self._person_email = person_email_service
        self._user_emails = user_emails_repository

    async def resolve(self, session, application, *, may_send: bool) -> EmailPolicy:
        """The policy for one application.

        A sender may write to the applicant's addresses, the contact address
        first and preselected; a reader gets no compose choices.

        Args:
            session (AsyncSession): The active DB session.
            application (ApplicationEntity): The application; its user is the applicant.
            may_send (bool): Whether the caller may send here.

        Returns:
            EmailPolicy: Rich HTML from the recruiting address.
        """
        contact = None
        options = []
        if may_send:
            contact = await self._user_emails.get_contact_email(
                session, application.user_id
            )
            addresses = await self._person_email.person_email_addresses(
                session, application.user_id
            )
            options = recipient_options([a.address for a in addresses], contact)
        return EmailPolicy(
            user_id=application.user_id,
            context_type=ContextType.APPLICATION,
            context_id=application.application_id,
            sender_address=self._person_email.default_sender_address,
            may_send=may_send,
            body_format=BodyFormat.RICH,
            recipient_options=tuple(options),
            default_to=contact,
        )
