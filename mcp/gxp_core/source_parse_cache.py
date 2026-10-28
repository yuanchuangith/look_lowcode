"""Process-local pure parse reuse; never a source freshness or permission cache."""
from __future__ import annotations

from collections import OrderedDict
from copy import copy, deepcopy
from threading import RLock
import sys
from typing import Any

from .source_lex import LexedSource


def _copy_parse(value: Any) -> Any:
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], LexedSource):
        data, original = value
        lexed = copy(original)
        # Text and Token tuples are immutable. Copy only mutable containers;
        # generic deepcopy reconstructs every token and can cost more than parsing.
        lexed.errors = list(original.errors)
        lexed.strings = list(original.strings)
        lexed.line_starts = list(original.line_starts)
        lexed._tokens = list(original._tokens) if original._tokens is not None else None
        lexed._pairs = dict(original._pairs) if original._pairs is not None else None
        return deepcopy(data), lexed
    return deepcopy(value)


def _size(value: Any, seen: set[int] | None = None) -> int:
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = sys.getsizeof(value)
    if isinstance(value, dict):
        return size + sum(_size(key, seen) + _size(item, seen) for key, item in value.items())
    if isinstance(value, (tuple, list, set, frozenset)):
        return size + sum(_size(item, seen) for item in value)
    if hasattr(value, "__dict__"):
        return size + _size(vars(value), seen)
    return size


class SourceParseCache:
    def __init__(self, max_entries: int = 128, max_bytes: int = 32 * 1024 * 1024,
                 max_entry_bytes: int = 4 * 1024 * 1024):
        self.max_entries, self.max_bytes, self.max_entry_bytes = max_entries, max_bytes, max_entry_bytes
        self._entries: OrderedDict[tuple, tuple[Any, int]] = OrderedDict()
        self._bytes = 0
        self._lock = RLock()

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._bytes = 0

    def get(self, key: tuple) -> Any:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            self._entries.move_to_end(key)
            # Backend binding mutates parse data; no consumer receives the cached object.
            return _copy_parse(entry[0])

    def put(self, key: tuple, value: Any) -> None:
        size = _size((key, value))
        if size > min(self.max_entry_bytes, self.max_bytes) or self.max_entries < 1:
            return
        with self._lock:
            old = self._entries.pop(key, None)
            if old is not None:
                self._bytes -= old[1]
            self._entries[key] = (_copy_parse(value), size)
            self._bytes += size
            while len(self._entries) > self.max_entries or self._bytes > self.max_bytes:
                _, (_, removed_size) = self._entries.popitem(last=False)
                self._bytes -= removed_size


SOURCE_PARSE_CACHE = SourceParseCache()
