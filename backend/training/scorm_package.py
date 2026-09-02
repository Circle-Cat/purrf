"""Validating and reading an uploaded SCORM zip.

A zip from a course author is untrusted input that we then serve back to
browsers, so every check here is a refusal rather than a repair, and each one
names the rule it enforces: the admin who uploaded the file is usually not the
person who can fix it, so the message has to be forwardable.
"""

import posixpath
import zipfile
from dataclasses import dataclass
from urllib.parse import unquote

from backend.common.mentorship_enums import ScormVersion
from backend.training.scorm_manifest import (
    MANIFEST_NAME,
    DriverConfig,
    ManifestInfo,
    parse_driver_config,
    parse_manifest,
)

# Room for packages several times the size of the ones we hold (the larger real
# package is 219 files and 32 MB) without letting a decompression bomb through.
MAX_TOTAL_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
MAX_ENTRY_COUNT = 5000
MAX_FILE_BYTES = 200 * 1024 * 1024
# Video and audio barely compress; text and JSON reach 10-20x. A single entry
# beyond this is not a course asset.
MAX_COMPRESSION_RATIO = 200

# Paths we serve ourselves from inside the package's own URL space. A package
# containing one of these could otherwise replace the player that hosts the
# SCORM API.
RESERVED_PREFIX = "__"


class PackageRejected(ValueError):
    """An uploaded package broke one of the rules below.

    A ValueError so the API answers 400; the message names the rule and, where
    there is one, the fix.
    """


@dataclass(frozen=True)
class PackageContents:
    """What a validated package holds."""

    manifest: ManifestInfo
    driver_config: DriverConfig | None
    # Entry names in archive order, already checked to be safe to write.
    file_names: list[str]
    # Served name -> the name the entry actually has inside the zip. The two
    # differ whenever an entry is written "./a/b.js" or "a//b.js", and reading
    # such an entry back by its served name raises KeyError.
    archive_names: dict[str, str]
    total_uncompressed_bytes: int
    # Files the manifest declares that are not in the archive. A warning, not a
    # rejection: the comparison is only as good as our href handling, and a
    # course missing a decorative image should not be unpublishable.
    missing_declared_files: list[str]


def _reject_unsafe_paths(entries: list[zipfile.ZipInfo]) -> None:
    """Refuse traversal, absolute paths, symlinks and reserved names."""
    for entry in entries:
        name = entry.filename
        if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
            raise PackageRejected(
                f"Rejected: the entry {name!r} is an absolute path. "
                "Re-export the package so every file is relative to its root."
            )
        normalised = posixpath.normpath(name)
        if normalised.startswith("..") or normalised == "..":
            raise PackageRejected(
                f"Rejected: the entry {name!r} points outside the package. "
                "Re-export the package so every file is relative to its root."
            )
        # The high 16 bits of external_attr are the Unix mode; 0xA000 is a
        # symlink. A link can point anywhere on the machine that unpacks it.
        if (entry.external_attr >> 16) & 0xF000 == 0xA000:
            raise PackageRejected(
                f"Rejected: the entry {name!r} is a symbolic link. "
                "Symbolic links are not allowed in a course package."
            )
        # The reserved names sit at the root of the package's own URL space,
        # so the first segment is what can collide -- a basename test both
        # misses "__MACOSX/thumbs.db", which a Mac-zipped package carries, and
        # refuses "assets/__chunk.js", which collides with nothing.
        if normalised.startswith(RESERVED_PREFIX):
            raise PackageRejected(
                f"Rejected: the entry {name!r} starts with {RESERVED_PREFIX!r}, "
                "which is reserved for files purrf serves itself. "
                "Rename it in the source course and re-export."
            )


def _reject_oversized(entries: list[zipfile.ZipInfo]) -> int:
    """Refuse an archive that is too large, too numerous, or a bomb.

    Returns:
        int: Total uncompressed size, once it is known to be within bounds.
    """
    if len(entries) > MAX_ENTRY_COUNT:
        raise PackageRejected(
            f"Rejected: the package has {len(entries)} files, more than the "
            f"{MAX_ENTRY_COUNT} allowed."
        )

    total = 0
    for entry in entries:
        if entry.file_size > MAX_FILE_BYTES:
            raise PackageRejected(
                f"Rejected: {entry.filename!r} unpacks to "
                f"{entry.file_size} bytes, more than the "
                f"{MAX_FILE_BYTES} allowed for one file."
            )
        if (
            entry.compress_size > 0
            and entry.file_size / entry.compress_size > MAX_COMPRESSION_RATIO
        ):
            raise PackageRejected(
                f"Rejected: {entry.filename!r} expands more than "
                f"{MAX_COMPRESSION_RATIO} times, which no course asset does."
            )
        total += entry.file_size
        if total > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise PackageRejected(
                "Rejected: the package unpacks to more than "
                f"{MAX_TOTAL_UNCOMPRESSED_BYTES} bytes."
            )
    return total


def _find_missing_declared_files(declared: list[str], present: set[str]) -> list[str]:
    """Which manifest-declared hrefs have no entry in the archive.

    Manifest hrefs are URL-encoded and zip entry names are not, so a literal
    comparison reports healthy files as missing the moment a filename contains
    a space. Unquote first, and drop any query string.
    """
    missing = []
    for href in declared:
        path = unquote(href.split("?", 1)[0].split("#", 1)[0])
        if posixpath.normpath(path) not in present:
            missing.append(href)
    return missing


def _served_names(entries: list[zipfile.ZipInfo]) -> dict[str, str]:
    """Map each entry's served path to the name it has inside the zip.

    Zip entry names are stored as written, and "./a/b.js" and "a//b.js" are
    both legal; we serve and store the normalised path, but every read back out
    of the archive has to use the original name or it raises KeyError.

    Raises:
        PackageRejected: Two entries normalise to the same served path, so
            which of them a learner would be given is undecidable.
    """
    mapping: dict[str, str] = {}
    for entry in entries:
        name = posixpath.normpath(entry.filename)
        if name in mapping and mapping[name] != entry.filename:
            raise PackageRejected(
                f"Rejected: the entries {mapping[name]!r} and "
                f"{entry.filename!r} both name the file {name!r}, so there is "
                "no telling which one a learner would be served. Re-export the "
                "package with one file per path."
            )
        mapping[name] = entry.filename
    return mapping


def read_package(archive: zipfile.ZipFile) -> PackageContents:
    """Validate an uploaded package and read what we need out of it.

    Checks run in order of how cheap they are to answer and how badly they
    would hurt if skipped: unsafe paths first, then size, then whether this is
    a SCORM package at all, then whether it is a version we run.

    Args:
        archive (zipfile.ZipFile): The uploaded archive, already open.

    Returns:
        PackageContents: The manifest, the completion configuration if we can
        read it, and the entry names.

    Raises:
        PackageRejected: Any rule above was broken.
    """
    entries = [entry for entry in archive.infolist() if not entry.is_dir()]
    if not entries:
        raise PackageRejected("Rejected: the archive is empty.")

    _reject_unsafe_paths(entries)
    total = _reject_oversized(entries)

    archive_names = _served_names(entries)
    names = list(archive_names)
    if MANIFEST_NAME not in archive_names:
        raise PackageRejected(
            f"Rejected: there is no {MANIFEST_NAME} at the root of the "
            "archive, so this is not a SCORM package. Zip the contents of the "
            "published folder rather than the folder itself."
        )

    manifest = parse_manifest(archive.read(archive_names[MANIFEST_NAME]))

    if manifest.scorm_version is ScormVersion.SCORM_2004:
        raise PackageRejected(
            "Rejected: this is a SCORM 2004 package. Only SCORM 1.2 is "
            "supported. Ask whoever exported it to publish for SCORM 1.2 "
            "instead."
        )

    if manifest.entry_path not in archive_names:
        raise PackageRejected(
            f"Rejected: the manifest names {manifest.entry_path!r} as the "
            "entry point, but there is no such file in the archive."
        )

    driver_config = parse_driver_config(
        archive.read(archive_names[manifest.entry_path])
    )

    return PackageContents(
        manifest=manifest,
        driver_config=driver_config,
        file_names=names,
        archive_names=archive_names,
        total_uncompressed_bytes=total,
        missing_declared_files=_find_missing_declared_files(
            manifest.declared_hrefs, set(names)
        ),
    )
