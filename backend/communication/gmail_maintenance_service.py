class GmailMaintenanceService:
    """The daily Gmail maintenance and the manual full resync."""

    def __init__(self, logger, gmail_sync_service, database):
        """
        Args:
            logger: Logger instance.
            gmail_sync_service (GmailSyncService): Renews the watch and syncs mailboxes.
            database: Async session provider, for the resync that runs after
                the response.
        """
        self.logger = logger
        self.gmail_sync_service = gmail_sync_service
        self.database = database

    async def maintain(self, session):
        """Renew the Gmail watch, then catch up from the cursor.

        A failed renewal still catches up first, since the current watch may
        have days left, and its error is the one raised. Errors propagate so
        the daily job fails and Kubernetes retries it; the alert was already
        sent.

        Args:
            session (AsyncSession): A session this call owns. Committed by the sync.

        Returns:
            dict: ``{"watch": <renew_watch result>, "catchUp": <catch_up result>}``.
        """
        try:
            watch = await self.gmail_sync_service.renew_watch(session)
        except Exception:
            await session.rollback()
            try:
                await self.gmail_sync_service.catch_up(session)
            except Exception:
                self.logger.exception(
                    "[GmailSync] catch-up after a failed watch renewal failed"
                )
            raise
        catch_up = await self.gmail_sync_service.catch_up(session)
        return {"watch": watch, "catchUp": catch_up}

    async def run_manual_full_resync(self):
        """Re-sync every tracked thread on a session of its own, without an alert first.

        Runs after the response, so a failure is logged rather than raised; the
        sync has already recorded and alerted on it.
        """
        try:
            async with self.database.session() as session:
                await self.gmail_sync_service.full_resync(session, alert=False)
        except Exception:
            self.logger.exception("[GmailSync] manual full resync failed")
