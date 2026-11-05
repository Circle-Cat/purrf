class EmailContextRegistry:
    """Maps an email thread's ``context_type`` to the domain that owns it.

    Sync entry points that know nothing about any domain (the Gmail push, the
    daily catch-up) hand a changed thread to the handler registered here. A
    handler implements ``async sync_tracked_thread(session, thread) -> int``
    and ``async resync_all(session) -> dict`` (the full resync run when the
    history cursor has expired; it may commit). The handler is where that
    domain's consequences of new mail are written, so no entry point can
    persist messages while skipping them. The Inbox contexts' handler also
    takes ``messages=``, the messages the Inbox router read to create the
    thread, so its first sync does not read them again.
    """

    def __init__(self):
        self._handlers = {}

    def register(self, context_type, handler):
        """Register the handler that owns threads of one context type.

        Args:
            context_type (str): The ``ContextType`` value the handler owns.
            handler: Object with ``async sync_tracked_thread(session, thread)``.

        Raises:
            ValueError: If a handler is already registered for this type.
        """
        if context_type in self._handlers:
            raise ValueError(f"Duplicate email context handler for {context_type!r}")
        self._handlers[context_type] = handler

    def get(self, context_type):
        """Return the handler for a context type, or None if none is registered.

        Args:
            context_type (str): The ``ContextType`` value to look up.
        """
        return self._handlers.get(context_type)

    def handlers(self):
        """Return every registered handler, in registration order."""
        return list(self._handlers.values())
