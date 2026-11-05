"""Checks on Kit broadcast HTML that Purrf runs before handing a draft to an admin."""

import hashlib
import json
import re

_HREF = re.compile(r"""href\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
_ALLOWED_PREFIXES = ("https://", "http://", "mailto:", "tel:", "#", "{{")


def find_invalid_hrefs(html: str) -> list[str]:
    """Return hrefs Kit's editor rejects (no supported scheme), each once, in
    order of first appearance. Kit refuses to open a draft that has any of them,
    and refuses to send a button whose link is empty."""
    seen: list[str] = []
    for match in _HREF.finditer(html):
        href = match.group(1) if match.group(1) is not None else match.group(2)
        if href.strip().lower().startswith(_ALLOWED_PREFIXES):
            continue
        if href not in seen:
            seen.append(href)
    return seen


def broadcast_fingerprint(
    *, content: str, subject: str, email_address: str, subscriber_filter: list
) -> str:
    """Hash of the broadcast fields an admin approves on the preview. Scheduling
    compares it against a fresh read so what goes out is what was previewed."""
    payload = json.dumps(
        {
            "content": content,
            "subject": subject,
            "email_address": email_address,
            "subscriber_filter": subscriber_filter,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fingerprint_of(broadcast: dict) -> str:
    return broadcast_fingerprint(
        content=broadcast.get("content") or "",
        subject=broadcast.get("subject") or "",
        email_address=broadcast.get("email_address") or "",
        subscriber_filter=broadcast.get("subscriber_filter") or [],
    )


def targets_only_tag(broadcast: dict, tag_id: int, sender_address: str) -> bool:
    """True when the draft still goes to this one tag and nobody else, from the
    configured sender -- what Purrf wrote when it created the draft."""
    groups = broadcast.get("subscriber_filter") or []
    if len(groups) != 1 or groups[0].get("any") or groups[0].get("none"):
        return False
    conditions = groups[0].get("all") or []
    only_tag = (
        len(conditions) == 1
        and conditions[0].get("type") == "tag"
        and conditions[0].get("ids") == [tag_id]
    )
    return only_tag and broadcast.get("email_address") == sender_address
