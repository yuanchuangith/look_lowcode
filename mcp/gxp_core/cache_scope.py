"""Database cache identity, without opening connections or reading credentials."""
from __future__ import annotations

from .config import ConfigurationError, default_config_path, load_config
from .handoff_store import environment_scope


def database_cache_scope(config=None) -> str | None:
    if config is None:
        try:
            config = load_config()
        except ConfigurationError:
            # Missing optional DB configuration keeps standalone CPM available.
            # An existing but invalid configuration must never select old caches.
            from .connection_settings import settings_path
            if default_config_path().exists() or settings_path().exists():
                raise
            return None
    return environment_scope(config)
