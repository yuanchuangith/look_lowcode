from __future__ import annotations

import ipaddress
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_SCHEMA_TTL_SECONDS = 86400
DEFAULT_REFRESH_TIMEOUT_SECONDS = 300
DEFAULT_QUERY_TIMEOUT_MS = 10000
DEFAULT_VALIDATION_CONCURRENCY = 2
DEFAULT_MIN_DISTINCT_VALUES = 20
DEFAULT_POLICY_URL = "https://43-135-137-212.sslip.io:8892"
DEFAULT_POLICY_SCOPE_ID = "gxp-development"


def _config_root() -> Path:
    override = os.environ.get("GXP_LOWCODE_CONFIG_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        value = os.environ.get("APPDATA")
        return Path(value) if value else Path.home() / "AppData" / "Roaming"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    value = os.environ.get("XDG_CONFIG_HOME")
    return Path(value).expanduser() if value else Path.home() / ".config"


def schema_runtime_root() -> Path:
    override = os.environ.get("GXP_LOWCODE_RUNTIME_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        value = os.environ.get("LOCALAPPDATA")
        base = Path(value) if value else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        value = os.environ.get("XDG_DATA_HOME")
        base = Path(value).expanduser() if value else Path.home() / ".local" / "share"
    return base / "GxpLowcodeReadonly"


def schema_config_path() -> Path:
    override = os.environ.get("GXP_LOWCODE_SCHEMA_CONFIG")
    return Path(override).expanduser().resolve() if override else _config_root() / "GxpLowcodeReadonly" / "schema.json"


def schema_status_path() -> Path:
    return schema_runtime_root() / "schema-refresh-status.json"


def schema_lock_path() -> Path:
    return schema_runtime_root() / "schema-refresh.lock"


def schema_policy_cache_path() -> Path:
    return schema_runtime_root() / "relation-policy-cache.json"


def default_schema_snapshot_dir() -> Path:
    return schema_runtime_root() / "schema-snapshot"


def _is_local_http(parsed) -> bool:
    host = (parsed.hostname or "").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class SchemaSnapshotConfig:
    snapshot_dir: str = str(default_schema_snapshot_dir())
    policy_url: str = DEFAULT_POLICY_URL
    policy_scope_id: str = DEFAULT_POLICY_SCOPE_ID
    ttl_seconds: int = DEFAULT_SCHEMA_TTL_SECONDS
    refresh_timeout_seconds: int = DEFAULT_REFRESH_TIMEOUT_SECONDS
    query_timeout_ms: int = DEFAULT_QUERY_TIMEOUT_MS
    validation_concurrency: int = DEFAULT_VALIDATION_CONCURRENCY
    min_distinct_values: int = DEFAULT_MIN_DISTINCT_VALUES

    @classmethod
    def from_dict(cls, raw: dict) -> "SchemaSnapshotConfig":
        forbidden = {key for key in raw if any(word in key.lower() for word in ("password", "token", "secret"))}
        if forbidden:
            raise ValueError("schema.json 不得包含密码、令牌或密钥字段")
        config = cls(
            snapshot_dir=str(raw.get("snapshot_dir") or default_schema_snapshot_dir()),
            policy_url=str(raw.get("policy_url", DEFAULT_POLICY_URL)).rstrip("/"),
            policy_scope_id=str(raw.get("policy_scope_id", DEFAULT_POLICY_SCOPE_ID)).strip(),
            ttl_seconds=int(raw.get("ttl_seconds", DEFAULT_SCHEMA_TTL_SECONDS)),
            refresh_timeout_seconds=int(raw.get("refresh_timeout_seconds", DEFAULT_REFRESH_TIMEOUT_SECONDS)),
            query_timeout_ms=int(raw.get("query_timeout_ms", DEFAULT_QUERY_TIMEOUT_MS)),
            validation_concurrency=int(raw.get("validation_concurrency", DEFAULT_VALIDATION_CONCURRENCY)),
            min_distinct_values=int(raw.get("min_distinct_values", DEFAULT_MIN_DISTINCT_VALUES)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not Path(self.snapshot_dir).is_absolute():
            raise ValueError("snapshot_dir 必须是绝对路径")
        parsed = urlparse(self.policy_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("policy_url 必须是有效 HTTP(S) 地址")
        if parsed.scheme != "https" and not _is_local_http(parsed):
            raise ValueError("远程 policy_url 必须使用 HTTPS；HTTP 仅允许 localhost")
        if not self.policy_scope_id:
            raise ValueError("policy_scope_id 不能为空")
        if not 1 <= self.validation_concurrency <= 2:
            raise ValueError("validation_concurrency 必须为 1 或 2")
        if self.ttl_seconds < 1 or self.refresh_timeout_seconds < 1:
            raise ValueError("TTL 和刷新超时必须是正整数")
        if not 100 <= self.query_timeout_ms <= 10000:
            raise ValueError("query_timeout_ms 必须在 100-10000 之间")
        if self.min_distinct_values < 1:
            raise ValueError("min_distinct_values 必须是正整数")


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def load_schema_config() -> SchemaSnapshotConfig:
    path = schema_config_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return SchemaSnapshotConfig()
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("schema.json 不是有效 UTF-8 JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("schema.json 顶层必须是对象")
    return SchemaSnapshotConfig.from_dict(raw)


def save_schema_config(config: SchemaSnapshotConfig) -> Path:
    config.validate()
    path = schema_config_path()
    _atomic_json(path, asdict(config))
    return path
