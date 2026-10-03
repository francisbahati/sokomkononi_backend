"""
FimiPay order-id helpers.

FimiPay rejects an order_id it has already seen ("order_id is already in use"),
so every payment ATTEMPT needs a unique id. We keep the record's primary key in
the id so the webhook can find the record:

    BND-5-a1b2c3d4   ->  prefix "BND", pk 5
    BND-5            ->  prefix "BND", pk 5   (old format, still accepted)
"""
import re
import uuid

_ORDER_ID_RE = re.compile(r"^([A-Z]+)-(\d+)(?:-[A-Za-z0-9]+)?$")


def make_order_id(prefix, pk):
    """Unique order id for one payment attempt, e.g. BND-5-a1b2c3d4."""
    return f"{prefix}-{pk}-{uuid.uuid4().hex[:8]}"


def parse_order_id(order_id):
    """Return (prefix, pk) or (None, None) if the id has an unknown shape."""
    match = _ORDER_ID_RE.match(order_id or "")
    if not match:
        return None, None
    return match.group(1), int(match.group(2))