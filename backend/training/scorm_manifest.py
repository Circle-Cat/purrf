"""Reading imsmanifest.xml, and the completion configuration beside it."""

import json
import posixpath
import re
from dataclasses import dataclass, field

from defusedxml import ElementTree

from backend.common.mentorship_enums import ScormVersion

MANIFEST_NAME = "imsmanifest.xml"

# The manifest sits at the archive root with no wrapping directory, and its
# elements are namespaced by an IMS schema whose URI varies by version, so
# elements are matched on local name rather than by a fixed namespace.
_LOCAL_NAME = re.compile(r"\{.*\}")

# Rustici's scormdriver writes its settings into the entry page as a JSON
# script block. Nothing in the SCORM specification requires this -- it is how
# one authoring toolchain happens to build, and packages from Captivate or
# iSpring have no equivalent.
_DRIVER_CONFIG = re.compile(
    rb"""<script[^>]*id=['"]__DRIVER_CONFIG__['"][^>]*>(.*?)</script>""",
    re.DOTALL | re.IGNORECASE,
)


class ManifestRejected(ValueError):
    """The manifest is missing, malformed, or does not name an entry point."""


@dataclass(frozen=True)
class ManifestInfo:
    """What the manifest tells us about a package."""

    scorm_version: ScormVersion
    # Entry page relative to the archive root, e.g.
    # "scormdriver/indexAPI.html".
    entry_path: str
    # Every href the manifest declares, still URL-encoded as written.
    declared_hrefs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DriverConfig:
    """How a Rustici-built course decides it is finished.

    This is the single most useful thing we can tell an admin at upload time.
    In August a course reported nothing and could not be completed; the cause
    was here, and reading the slides would never have found it.
    """

    # Present when completion is delegated to an embedded Storyline block, in
    # which case finishing the surrounding lessons does not complete the course.
    storyline_id: str | None
    quiz_id: str | None
    # e.g. "passed-incomplete" or "completed-incomplete". Which lesson_status
    # counts as finished differs per course; never hard-code it.
    reporting: str | None
    course_package_version: str | None
    # Percentage of the course the driver requires before it reports
    # completion. 100 in every package we hold.
    completion_percentage: float | None


def _tag(element) -> str:
    return _LOCAL_NAME.sub("", element.tag)


def _find_all(root, name: str):
    return [e for e in root.iter() if _tag(e) == name]


def parse_manifest(manifest_bytes: bytes) -> ManifestInfo:
    """Read the version and entry point out of imsmanifest.xml.

    Parsed with defusedxml: a manifest is attacker-supplied, and the stdlib
    parser resolves external entities and expands nested ones.

    The entry point is the href of the resource referenced by the first item of
    the default organization, which is where it lives in both real packages.
    A package that does not say it that way is refused rather than guessed at:
    picking a resource ourselves would launch whatever happened to be listed
    first, and being wrong about that looks like a broken course.

    Args:
        manifest_bytes (bytes): Raw imsmanifest.xml.

    Returns:
        ManifestInfo: Version, entry path and declared hrefs.

    Raises:
        ManifestRejected: Unparseable, or no entry point can be determined.
    """
    try:
        root = ElementTree.fromstring(manifest_bytes)
    except Exception as error:
        raise ManifestRejected(
            f"Rejected: {MANIFEST_NAME} could not be parsed as XML ({error})."
        ) from error

    version_elements = _find_all(root, "schemaversion")
    raw_version = (version_elements[0].text or "").strip() if version_elements else ""
    if raw_version.startswith("1.2"):
        scorm_version = ScormVersion.SCORM_12
    elif "2004" in raw_version or raw_version.startswith("CAM"):
        scorm_version = ScormVersion.SCORM_2004
    else:
        raise ManifestRejected(
            f"Rejected: {MANIFEST_NAME} declares schemaversion {raw_version!r}, "
            "which is neither SCORM 1.2 nor 2004."
        )

    resources = {
        resource.get("identifier"): resource
        for resource in _find_all(root, "resource")
        if resource.get("identifier")
    }
    declared_hrefs = [
        href
        for element in root.iter()
        if _tag(element) in ("resource", "file") and (href := element.get("href"))
    ]

    entry_path = None
    organizations = _find_all(root, "organizations")
    default_id = organizations[0].get("default") if organizations else None
    candidates = _find_all(root, "organization")
    if default_id:
        candidates = [o for o in candidates if o.get("identifier") == default_id] or (
            candidates
        )
    for organization in candidates:
        for item in _find_all(organization, "item"):
            resource = resources.get(item.get("identifierref"))
            if resource is not None and resource.get("href"):
                entry_path = resource.get("href")
                break
        if entry_path:
            break

    if not entry_path:
        raise ManifestRejected(
            f"Rejected: {MANIFEST_NAME} does not name a launchable resource. "
            "Its default organization needs an item whose identifierref names "
            "a resource with an href. Re-export the package with a course "
            "structure rather than a bare list of files."
        )

    return ManifestInfo(
        scorm_version=scorm_version,
        # Normalised the same way archive entry names are, so an href written
        # "./scormdriver/indexAPI.html" still matches the file it names.
        entry_path=posixpath.normpath(entry_path.split("?", 1)[0]),
        declared_hrefs=declared_hrefs,
    )


def parse_driver_config(entry_page_bytes: bytes) -> DriverConfig | None:
    """Read the completion configuration out of the entry page.

    Returns None for any package we cannot read, which the upload dialog must
    say out loud rather than leave blank -- silence there reads as "nothing
    wrong", and that is exactly the mistake this is here to prevent.

    Args:
        entry_page_bytes (bytes): Raw bytes of the entry page.

    Returns:
        DriverConfig | None: The configuration, or None if this package was not
        built by a toolchain we can read.
    """
    match = _DRIVER_CONFIG.search(entry_page_bytes)
    if not match:
        return None
    try:
        config = json.loads(match.group(1).decode("utf-8", errors="replace"))
    except ValueError:
        return None
    if not isinstance(config, dict):
        return None

    percentage = config.get("completionPercentage")
    return DriverConfig(
        storyline_id=config.get("storylineId") or None,
        quiz_id=config.get("quizId") or None,
        reporting=config.get("reporting") or None,
        course_package_version=config.get("coursePackageVersion") or None,
        completion_percentage=(
            float(percentage) if isinstance(percentage, (int, float)) else None
        ),
    )
