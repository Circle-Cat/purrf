from backend.common.communication_enums import InboundKind

_AUTO_PRECEDENCE = {"auto_reply", "bulk", "junk", "list"}


def classify_inbound(parsed: dict) -> InboundKind:
    """Bounce first: Gmail marks its bounces Auto-Submitted too."""
    if parsed.get("failed_recipients") is not None:
        return InboundKind.BOUNCE
    auto = (parsed.get("auto_submitted") or "").strip().lower()
    if auto and auto != "no":
        return InboundKind.AUTO_REPLY
    if (parsed.get("precedence") or "").strip().lower() in _AUTO_PRECEDENCE:
        return InboundKind.AUTO_REPLY
    return InboundKind.HUMAN
