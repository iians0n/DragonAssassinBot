"""Thread-safe JSON file storage with in-memory caching."""

import json
import os
import threading
from typing import Any

from config import DATA_DIR


class JsonStore:
    """Simple JSON file store with atomic writes and in-memory cache."""

    def __init__(self):
        self._locks: dict[str, threading.Lock] = {}
        self._cache: dict[str, Any] = {}
        self._global_lock = threading.Lock()
        os.makedirs(DATA_DIR, exist_ok=True)

    def _get_lock(self, filepath: str) -> threading.Lock:
        with self._global_lock:
            if filepath not in self._locks:
                self._locks[filepath] = threading.Lock()
            return self._locks[filepath]

    def _filepath(self, name: str) -> str:
        return os.path.join(DATA_DIR, f"{name}.json")

    def load(self, name: str, default: Any = None) -> Any:
        """Load data from JSON file. Returns default if file doesn't exist."""
        filepath = self._filepath(name)
        lock = self._get_lock(filepath)

        with lock:
            # Return cached version if available
            if filepath in self._cache:
                return self._cache[filepath]

            if not os.path.exists(filepath):
                data = default if default is not None else {}
                self._cache[filepath] = data
                return data

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._cache[filepath] = data
                return data
            except (json.JSONDecodeError, IOError):
                data = default if default is not None else {}
                self._cache[filepath] = data
                return data

    def save(self, name: str, data: Any):
        """Atomically save data to JSON file."""
        filepath = self._filepath(name)
        lock = self._get_lock(filepath)

        with lock:
            tmp_path = filepath + ".tmp"
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, filepath)
                self._cache[filepath] = data
            except IOError:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise

    def load_players(self) -> dict:
        """Load all players as {user_id_str: player_dict}."""
        return self.load("players", default={})

    def save_players(self, players: dict):
        self.save("players", players)

    def load_game(self) -> dict:
        """Load game state."""
        return self.load("game", default={})

    def save_game(self, game: dict):
        self.save("game", game)

    def load_bounties(self) -> list:
        """Load all bounties as list of dicts."""
        return self.load("bounties", default=[])

    def save_bounties(self, bounties: list):
        self.save("bounties", bounties)

    def load_kill_log(self) -> list:
        """Load kill history as list of dicts."""
        return self.load("kill_log", default=[])

    def save_kill_log(self, kills: list):
        self.save("kill_log", kills)

    def load_pending_kills(self) -> list:
        """Load pending kills awaiting confirmation/dispute."""
        return self.load("pending_kills", default=[])

    def save_pending_kills(self, pending_kills: list):
        self.save("pending_kills", pending_kills)


# Singleton instance
store = JsonStore()
