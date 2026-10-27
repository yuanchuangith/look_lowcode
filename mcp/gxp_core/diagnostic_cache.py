"""Process-local pure diagnostic snapshots; every hit replays its read proofs.

Neither connections nor permission decisions are cached.  A proof includes every
actual selector (including empty results), schema read and design read. Large
design columns are re-read as UTF-8 digests under the same SQL predicates.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime


ANALYZER_VERSION = 1
MAX_ENTRIES = 32
MAX_ENTRY_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
IDLE_SECONDS = 300
_CONTENT = re.compile(r"(?P<expression>`[^`]+`|'')\s+AS\s+`(?P<alias>data|csharp_code)`", re.I)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _value(value):
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bytes):
        return int.from_bytes(value, "big") if value in (b"\x00", b"\x01") else value.decode("utf-8", errors="replace")
    return value


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def cache_key(repository, tool, arguments):
    # Use the already-loaded connection identity; never open configuration files,
    # read keyring values or expose this internal scope in a response/log.
    config = getattr(getattr(repository, "database", None), "config", None)
    names = ("host", "port", "database", "user", "credential_target")
    if config is None or any(not hasattr(config, name) for name in names):
        return None
    scope = [getattr(config, name) for name in names]
    return _digest([scope, tool, ANALYZER_VERSION, arguments])


@dataclass(frozen=True)
class ReadProof:
    sql: str
    params: object
    max_rows: int
    timeout_ms: int | None
    digest: str


class ReadManifest:
    def __init__(self):
        self.proofs = []
        self.complete = True

    def record(self, sql, params, max_rows, timeout_ms, rows, truncated):
        if truncated or len(self.proofs) >= 512:
            self.complete = False
            return
        columns = set()

        def replace(match):
            alias = match["alias"].lower()
            columns.add(alias)
            return f"SHA2(CONVERT(IFNULL({match['expression']},'') USING utf8mb4),256) AS `{alias}`"

        proof_sql = _CONTENT.sub(replace, sql)
        normalized = []
        for row in rows:
            if (set(row) & {"data", "csharp_code"}) - columns:
                self.complete = False
                return
            item = {key: _value(value) for key, value in row.items()}
            for key in columns:
                value = row.get(key)
                text = "" if value is None else value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
                item[key] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            normalized.append(item)
        try:
            self.proofs.append(ReadProof(proof_sql, deepcopy(params), max_rows, timeout_ms, _digest(normalized)))
        except (TypeError, ValueError):
            self.complete = False

    def verify(self, database):
        if not self.complete or not self.proofs:
            return False
        # A new request's DB sessions enforce current access to the original
        # tables/content columns. Failures propagate; cached data is not a fallback.
        for proof in self.proofs:
            with database.session(timeout_ms=proof.timeout_ms) as session:
                rows, truncated = session.query(proof.sql, proof.params, max_rows=proof.max_rows)
            if truncated or _digest([{key: _value(value) for key, value in row.items()} for row in rows]) != proof.digest:
                return False
        return True


class _RecordingSession:
    def __init__(self, session, manifest, timeout_ms):
        self.session, self.manifest, self.timeout_ms = session, manifest, timeout_ms

    def query(self, sql, params=None, *, max_rows=200):
        rows, truncated = self.session.query(sql, params, max_rows=max_rows)
        self.manifest.record(sql, params, max_rows, self.timeout_ms, rows, truncated)
        return rows, truncated

    def __getattr__(self, name):
        # Unknown read APIs cannot silently escape dependency collection.
        self.manifest.complete = False
        return getattr(self.session, name)


class _RecordingDatabase:
    def __init__(self, database, manifest):
        self.database, self.manifest = database, manifest

    @contextmanager
    def session(self, *, timeout_ms=None):
        with self.database.session(timeout_ms=timeout_ms) as session:
            yield _RecordingSession(session, self.manifest, timeout_ms)

    def __getattr__(self, name):
        self.manifest.complete = False
        return getattr(self.database, name)


@contextmanager
def record_reads(repository):
    database = repository.database
    manifest = ReadManifest()
    repository.database = _RecordingDatabase(database, manifest)
    try:
        yield manifest
    finally:
        repository.database = database


@dataclass(frozen=True)
class DiagnosticSnapshot:
    records: list
    envelope: dict
    fingerprint: str
    manifest: ReadManifest
    serialized_bytes: int


class DiagnosticCache:
    def __init__(self, *, max_entries=MAX_ENTRIES, max_entry_bytes=MAX_ENTRY_BYTES,
                 max_total_bytes=MAX_TOTAL_BYTES, idle_seconds=IDLE_SECONDS, clock=time.monotonic):
        self.max_entries, self.max_entry_bytes = max_entries, max_entry_bytes
        self.max_total_bytes, self.idle_seconds, self.clock = max_total_bytes, idle_seconds, clock
        self._items, self._bytes, self._lock = OrderedDict(), 0, threading.Lock()

    def _remove(self, key):
        snapshot, _ = self._items.pop(key)
        self._bytes -= snapshot.serialized_bytes

    def get(self, key):
        with self._lock:
            now = self.clock()
            for candidate, (_, accessed) in list(self._items.items()):
                if now - accessed >= self.idle_seconds:
                    self._remove(candidate)
            if key not in self._items:
                return None
            snapshot, _ = self._items[key]
            self._items[key] = snapshot, now
            self._items.move_to_end(key)
            return snapshot

    def put(self, key, snapshot):
        if not snapshot.manifest.complete or not snapshot.manifest.proofs or snapshot.serialized_bytes > min(self.max_entry_bytes, self.max_total_bytes):
            return
        with self._lock:
            if key in self._items:
                self._remove(key)
            while self._items and (len(self._items) >= self.max_entries or self._bytes + snapshot.serialized_bytes > self.max_total_bytes):
                self._remove(next(iter(self._items)))
            self._items[key] = snapshot, self.clock()
            self._bytes += snapshot.serialized_bytes

    def discard(self, key):
        with self._lock:
            if key in self._items:
                self._remove(key)

    def clear(self):
        with self._lock:
            self._items.clear()
            self._bytes = 0


DIAGNOSTIC_CACHE = DiagnosticCache()


def diagnostic_snapshot(repository, tool, arguments, build):
    from .diagnostic_output import _json as identity_json
    key = cache_key(repository, tool, arguments)
    if key is None:
        records, envelope, identity = build()
        return records, envelope, identity, None
    cached = DIAGNOSTIC_CACHE.get(key)
    if cached is not None:
        try:
            verified = cached.manifest.verify(repository.database)
        except Exception:
            DIAGNOSTIC_CACHE.discard(key)
            raise
        if verified:
            return cached.records, cached.envelope, None, cached.fingerprint
        DIAGNOSTIC_CACHE.discard(key)
    with record_reads(repository) as manifest:
        records, envelope, identity = build()
    encoded = identity_json(identity).encode("utf-8")
    fingerprint = hashlib.sha256(encoded).hexdigest()
    # Include manifest storage in the serialized accounting. No timing/cache data
    # enters the identity, so v1/v2 cursors survive a cache miss or eviction.
    proof_bytes = len(_json([proof.__dict__ for proof in manifest.proofs]).encode("utf-8"))
    DIAGNOSTIC_CACHE.put(key, DiagnosticSnapshot(records, envelope, fingerprint, manifest, len(encoded) + proof_bytes))
    return records, envelope, None, fingerprint
