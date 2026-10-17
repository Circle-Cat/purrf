import copy
import threading
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable

PAST_RANGE_TTL = timedelta(hours=24)
CURRENT_RANGE_TTL = timedelta(hours=1)
DEFAULT_MAX_ENTRIES = 256


class ActivityQueryCache:
    """In-process LRU cache for internal activity query results.

    Every environment runs one backend replica, so a process-local cache sees
    every request. One instance is shared by all activity services, so the
    entry bound is the bound for the whole process.

    Values are deep-copied on the way in and out, so a caller mutating what it
    got back cannot change what the next caller sees.
    """

    def __init__(
        self,
        logger,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ):
        """
        Args:
            logger: Logger instance.
            clock: Returns the current tz-aware time; injected for tests.
            max_entries: Most entries kept before the least recently used goes.
        """
        self.logger = logger
        self.clock = clock
        self.max_entries = max_entries
        self._entries: OrderedDict[tuple, tuple[datetime, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._entries)

    @staticmethod
    def unordered(values: Iterable[str] | None) -> tuple[str, ...] | None:
        """Key part for a list whose order does not change the result.

        Duplicates are kept: some queries count a repeated value twice.
        """
        return tuple(sorted(values)) if values else None

    @staticmethod
    def ordered(values: Iterable[str] | None) -> tuple[str, ...] | None:
        """Key part for a list whose order shows up in the result."""
        return tuple(values) if values else None

    def _ttl(self, range_end: datetime | None, now: datetime) -> timedelta:
        # "Today" is the UTC date: DateTimeUtil turns request dates into UTC
        # day boundaries and caps ranges at the end of today in UTC.
        if range_end is not None and (
            range_end.astimezone(timezone.utc).date()
            < now.astimezone(timezone.utc).date()
        ):
            return PAST_RANGE_TTL
        return CURRENT_RANGE_TTL

    def get_or_compute(
        self,
        method: str,
        args: tuple,
        range_end: datetime | None,
        compute: Callable[[], Any],
    ) -> Any:
        """Return the cached result for ``method(args)``, computing it on a miss.

        Args:
            method: Identifies the query; two methods never share entries.
            args: Hashable, already-normalized arguments.
            range_end: End of the queried date range. A range ending before
                today is cached for 24 hours; one reaching today, or a query
                with no range, for 1 hour.
            compute: Produces the result. If it raises, nothing is stored.

        Returns:
            A private copy of the result.
        """
        key = (method, args)
        now = self.clock()
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                expires_at, value = entry
                if now < expires_at:
                    self._entries.move_to_end(key)
                    self.logger.debug("Activity query cache hit for %s", method)
                    return copy.deepcopy(value)
                del self._entries[key]

        value = compute()
        stored = copy.deepcopy(value)
        with self._lock:
            self._entries[key] = (now + self._ttl(range_end, now), stored)
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
        return copy.deepcopy(stored)

    def clear(self) -> None:
        """Drop every entry, e.g. after a sync has written new activity data."""
        with self._lock:
            self._entries.clear()
