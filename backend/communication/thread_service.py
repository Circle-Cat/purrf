"""Which service an email thread belongs to, and so whose permission covers it."""

from backend.common.communication_enums import ContextType, InboxService
from backend.common.recruiting_enums import JobKind

_DIRECT = {
    ContextType.MENTORSHIP_INBOX: InboxService.MENTORSHIP,
    ContextType.RECRUITING_INBOX: InboxService.RECRUITING,
    ContextType.INQUIRIES_INBOX: InboxService.INQUIRIES,
    ContextType.ACTIVITY: InboxService.MENTORSHIP,
}


class ThreadServiceResolver:
    def __init__(self, job_repository):
        """
        Args:
            job_repository (JobRepository): Finds the job an application was made to.
        """
        self._jobs = job_repository

    async def service_of(self, session, thread):
        """The service a thread belongs to.

        An *_INBOX thread belongs to its own service and an ACTIVITY thread to
        Mentorship. An APPLICATION thread follows its job: an ACTIVITY job
        (mentee / mentor) is Mentorship, any other job is Recruiting.

        Args:
            session (AsyncSession): The active DB session.
            thread (EmailThreadEntity): The thread.

        Returns:
            InboxService: The owning service.

        Raises:
            ValueError: If the context belongs to no service, or the
                application's job does not exist.
        """
        service = _DIRECT.get(thread.context_type)
        if service is not None:
            return service
        if thread.context_type != ContextType.APPLICATION:
            raise ValueError(
                f"thread context {thread.context_type!r} belongs to no service"
            )
        job = await self._jobs.get_by_application_id(session, thread.context_id)
        if job is None:
            raise ValueError(f"application {thread.context_id} has no job")
        if job.kind == JobKind.ACTIVITY:
            return InboxService.MENTORSHIP
        return InboxService.RECRUITING
