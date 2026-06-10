"""Canonical order payment status transitions."""

from __future__ import annotations

ORDER_STATUSES = frozenset({"pending", "paid", "failed", "expired", "completed"})

# Terminal states: paid, expired, completed
VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"paid", "failed", "expired", "completed"}),
    "failed": frozenset({"pending"}),
    "paid": frozenset(),
    "expired": frozenset(),
    "completed": frozenset(),
}


class InvalidOrderTransition(ValueError):
    """Raised when an order status change is not allowed."""


def validate_order_transition(current: str, new: str) -> None:
    """Validate status transition. Same status is a no-op."""
    cur = (current or "pending").strip().lower()
    nxt = (new or "").strip().lower()
    if not nxt:
        raise InvalidOrderTransition("Target status is required")
    if nxt not in ORDER_STATUSES:
        raise InvalidOrderTransition(f"Unknown status: {nxt}")
    if cur == nxt:
        return
    allowed = VALID_TRANSITIONS.get(cur)
    if allowed is None or nxt not in allowed:
        raise InvalidOrderTransition(f"Cannot transition order from '{cur}' to '{nxt}'")
