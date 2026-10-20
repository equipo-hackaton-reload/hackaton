"""Caché en disco (sqlite) de llamadas pagadas: LLM, juez y, en el futuro, motores reales.

La clave es `(adaptador, modelo, hash del estado o prompt, repetición)`. El valor se guarda como
JSON. Se desactiva con `CACHE_ENABLED=false`: entonces `get` siempre falla y `set` no hace nada.
"""

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from posiq.settings import Settings


def stable_hash(payload: Any) -> str:
    """Hash estable de un objeto JSON (claves ordenadas)."""
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class DiskCache:
    def __init__(self, path: str | Path, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        if enabled:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(path), check_same_thread=False)
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS cache ("
                "key TEXT PRIMARY KEY, value TEXT NOT NULL, "
                "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            self._conn.commit()

    @classmethod
    def from_settings(cls, settings: Settings) -> "DiskCache":
        return cls(settings.cache_path, enabled=settings.cache_enabled)

    @staticmethod
    def key(adaptador: str, modelo: str, payload: Any, repeticion: int = 0) -> str:
        return f"{adaptador}|{modelo}|{stable_hash(payload)}|{repeticion}"

    def get(self, key: str) -> Any | None:
        if self._conn is None:
            return None
        with self._lock:
            row = self._conn.execute("SELECT value FROM cache WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def set(self, key: str, value: Any) -> None:
        if self._conn is None:
            return
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False, default=str)),
            )
            self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
