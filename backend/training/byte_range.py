"""One HTTP byte range: reading the header, and pinning it to an object.

The two halves happen in different places and so are kept apart. The header is
parsed where the request arrives, before anything is known about the file it
names; it can only be resolved once the object's size is known, which for a
stored file costs a round trip.
"""

import re
from dataclasses import dataclass

# Only a single range. Multiple ranges in one header are legal to refuse: the
# answer would be a multipart/byteranges body, no course player asks for one,
# and most servers ignore the header and return the whole object instead. Such
# a header simply does not match here, so it takes the malformed path to a 200.
#
# [0-9] rather than \d: \d also matches digits Python's int() will not parse.
_SINGLE_RANGE = re.compile(
    r"bytes\s*=\s*(?:([0-9]+)-([0-9]*)|-([0-9]+))", re.IGNORECASE
)


@dataclass(frozen=True)
class RangeSpec:
    """A ``bytes=`` range as written, before any object size is known.

    One shape at a time: ``first`` and ``last`` for ``bytes=first-last``,
    ``first`` alone for ``bytes=first-``, and ``suffix_length`` for
    ``bytes=-N``, which asks for the *last* N bytes rather than the first N.
    """

    first: int | None = None
    last: int | None = None
    suffix_length: int | None = None


@dataclass(frozen=True)
class ResolvedRange:
    """A range pinned to a real object. Both ends inclusive, as HTTP has them."""

    start: int
    end: int
    total: int

    @property
    def length(self) -> int:
        """How many bytes the range covers."""
        return self.end - self.start + 1

    def content_range(self) -> str:
        """The Content-Range header value for a 206."""
        return f"bytes {self.start}-{self.end}/{self.total}"


class UnsatisfiableRange(Exception):
    """A range that names no byte of the object, which is a 416.

    Carries the size because the 416 has to: ``Content-Range: bytes */total``
    is how the client learns what it should have asked for.
    """

    def __init__(self, total_size: int):
        super().__init__(f"No such range in an object of {total_size} bytes.")
        self.total_size = total_size


def parse_range_header(value: str | None) -> RangeSpec | None:
    """One byte range out of a Range header, or None to serve the whole object.

    None covers every case a server may ignore: no header at all, a unit that
    is not ``bytes``, more than one range, and anything malformed. RFC 9110
    says an unparsable Range is ignored rather than rejected, so the caller
    answers 200 with the whole object -- never an error.

    Args:
        value (str | None): The raw Range header, if the request carried one.

    Returns:
        RangeSpec | None: The range asked for, or None to ignore the header.
    """
    if not value:
        return None
    match = _SINGLE_RANGE.fullmatch(value.strip())
    if match is None:
        return None
    first_text, last_text, suffix_text = match.groups()
    if suffix_text is not None:
        return RangeSpec(suffix_length=int(suffix_text))
    first = int(first_text)
    if not last_text:
        return RangeSpec(first=first)
    last = int(last_text)
    if last < first:
        # An invalid spec makes the whole header invalid, which is a 200 with
        # everything -- not a 416. RFC 9110 4.2 is explicit about the
        # difference: unsatisfiable is about the object, invalid is about the
        # header, and only the former is an error.
        return None
    return RangeSpec(first=first, last=last)


def resolve_range(spec: RangeSpec, total: int) -> ResolvedRange | None:
    """Pin a range to an object of ``total`` bytes.

    An end past the last byte is clamped rather than refused: reading ahead
    past the end of a file is exactly what a media element does when it does
    not yet know how long the file is.

    Args:
        spec (RangeSpec): The range as the client wrote it.
        total (int): The object's full size in bytes.

    Returns:
        ResolvedRange | None: The bytes to serve, or None if the range names
        none of them -- a suffix of nothing, or a first byte at or past the
        end -- which the caller answers with a 416.
    """
    if spec.suffix_length is not None:
        if spec.suffix_length == 0 or total == 0:
            return None
        # A suffix longer than the object is the whole object, not an error.
        return ResolvedRange(
            start=max(0, total - spec.suffix_length), end=total - 1, total=total
        )
    if spec.first >= total:
        return None
    end = total - 1 if spec.last is None else min(spec.last, total - 1)
    return ResolvedRange(start=spec.first, end=end, total=total)


__all__ = [
    "RangeSpec",
    "ResolvedRange",
    "UnsatisfiableRange",
    "parse_range_header",
    "resolve_range",
]
