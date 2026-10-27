"""Small, unsigned transport guidance; never a replacement for source evidence."""
from __future__ import annotations

from copy import deepcopy


def guidance(code, affects, *, next_read=None, can_continue=(), stop_reason=None, attempted=()):
    return {
        "evidence_gaps": [{"code": code, "affects": list(affects) if isinstance(affects, (list, tuple)) else [affects],
                           "next_read": deepcopy(next_read), "can_continue": list(can_continue)}],
        "fallback": {"attempted": list(attempted), "stop_reason": stop_reason,
                     "max_additional_calls": 3, "budget_ms": 30000},
    }
