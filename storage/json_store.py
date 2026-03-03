"""Thread-safe JSON file storage with in-memory caching.

Saves include human-readable display fields (_display / _name) so admins
can easily read and amend the JSON files without decoding timestamps or
cross-referencing player IDs.
"""

import copy
import json
import os
import threading
from datetime import datetime
from typing import Any

import pytz

from config import DATA_DIR, TIMEZONE


class JsonStore:
    """Simple JSON file store with atomic writes and in-memory cache."""

    def __init__(self):
        self._locks: dict[str, threading.Lock] = {}
        self._cache: dict[str, Any] = {}
        self._global_lock = threading.Lock()
        os.makedirs(DATA_DIR, exist_ok=True)

    # ── internal helpers ─────────────────────────────────────────────

    def _get_lock(self, filepath: str) -> threading.Lock:
        with self._global_lock:
            if filepath not in self._locks:
                self._locks[filepath] = threading.Lock()
            return self._locks[filepath]

    def _filepath(self, name: str) -> str:
        return os.path.join(DATA_DIR, f"{name}.json")

    # Suffixes used for display-only fields (stripped on load)
    _DISPLAY_SUFFIXES = ("_display", "_name")

    @staticmethod
    def _strip_display_fields(data: Any) -> Any:
        """Recursively remove enrichment-only fields from loaded data."""
        if isinstance(data, dict):
            return {
                k: JsonStore._strip_display_fields(v)
                for k, v in data.items()
                if not k.endswith(JsonStore._DISPLAY_SUFFIXES)
            }
        if isinstance(data, list):
            return [JsonStore._strip_display_fields(item) for item in data]
        return data

    @staticmethod
    def _format_ts(epoch: float) -> str:
        """Convert a Unix epoch float to a human-readable SGT string."""
        if not epoch:
            return ""
        try:
            tz = pytz.timezone(TIMEZONE)
            dt = datetime.fromtimestamp(epoch, tz=tz)
            return dt.strftime("%d %b %Y, %I:%M %p SGT")
        except (OSError, ValueError, OverflowError):
            return str(epoch)

    def _player_lookup(self) -> dict[int, str]:
        """Return {user_id_int: 'Name (@username)'} from current players."""
        players = self.load_players()
        lookup: dict[int, str] = {}
        for uid_str, p in players.items():
            name = p.get("name", "?")
            uname = p.get("username", "")
            label = f"{name} (@{uname})" if uname else name
            lookup[int(uid_str)] = label
        return lookup

    # ── timestamp fields to enrich per file type ─────────────────────

    _TS_FIELDS_GAME = [
        "start_time", "end_time",
    ]
    _TS_FIELDS_PLAYER = [
        "registered_at", "cooldown_until",
    ]
    _TS_FIELDS_KILL = [
        "timestamp",
    ]
    _TS_FIELDS_PENDING = [
        "timestamp", "expires_at",
    ]
    _TS_FIELDS_BOUNTY = [
        "created_at", "expires_at",
    ]

    # ── player-id fields to resolve per file type ────────────────────

    _ID_FIELDS_KILL = [
        ("killer_id", "killer_name"),
        ("target_id", "target_name"),
    ]
    _ID_FIELDS_PENDING = [
        ("killer_id", "killer_name"),
        ("target_id", "target_name"),
        ("resolved_by", "resolved_by_name"),
    ]
    _ID_FIELDS_BOUNTY = [
        ("creator_id", "creator_name"),
        ("target_id", "target_name"),
        ("claimed_by", "claimed_by_name"),
    ]

    # ── enrichment helpers ───────────────────────────────────────────

    def _enrich_timestamps(self, record: dict, fields: list[str]) -> dict:
        """Add <field>_display entries for each timestamp field."""
        for field in fields:
            val = record.get(field)
            if val is not None:
                record[f"{field}_display"] = self._format_ts(val)
        return record

    def _enrich_player_ids(
        self, record: dict, fields: list[tuple[str, str]],
        lookup: dict[int, str],
    ) -> dict:
        """Add <name_field> entries resolved from player lookup."""
        for id_field, name_field in fields:
            uid = record.get(id_field)
            if uid:
                record[name_field] = lookup.get(int(uid), f"Unknown ({uid})")
        return record

    def _enrich_list(
        self, records: list, ts_fields: list[str],
        id_fields: list[tuple[str, str]] = None,
    ) -> list:
        """Deep-copy a list of records and enrich each entry."""
        enriched = copy.deepcopy(records)
        lookup = self._player_lookup() if id_fields else {}
        for rec in enriched:
            self._enrich_timestamps(rec, ts_fields)
            if id_fields:
                self._enrich_player_ids(rec, id_fields, lookup)
        return enriched

    # ── core load / save ─────────────────────────────────────────────

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
                data = self._strip_display_fields(data)
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

    # ── typed load / save with enrichment ────────────────────────────

    def load_players(self) -> dict:
        """Load all players as {user_id_str: player_dict}."""
        return self.load("players", default={})

    def save_players(self, players: dict):
        enriched = copy.deepcopy(players)
        for p in enriched.values():
            self._enrich_timestamps(p, self._TS_FIELDS_PLAYER)
        # Write enriched copy to disk, cache original
        self._save_enriched("players", players, enriched)

    def load_game(self) -> dict:
        """Load game state."""
        return self.load("game", default={})

    def save_game(self, game: dict):
        enriched = copy.deepcopy(game)
        self._enrich_timestamps(enriched, self._TS_FIELDS_GAME)
        self._save_enriched("game", game, enriched)

    def load_bounties(self) -> list:
        """Load all bounties as list of dicts."""
        return self.load("bounties", default=[])

    def save_bounties(self, bounties: list):
        enriched = self._enrich_list(
            bounties, self._TS_FIELDS_BOUNTY, self._ID_FIELDS_BOUNTY,
        )
        self._save_enriched("bounties", bounties, enriched)

    def load_kill_log(self) -> list:
        """Load kill history as list of dicts."""
        return self.load("kill_log", default=[])

    def save_kill_log(self, kills: list):
        enriched = self._enrich_list(
            kills, self._TS_FIELDS_KILL, self._ID_FIELDS_KILL,
        )
        self._save_enriched("kill_log", kills, enriched)

    def load_pending_kills(self) -> list:
        """Load pending kills awaiting confirmation/dispute."""
        return self.load("pending_kills", default=[])

    def save_pending_kills(self, pending_kills: list):
        enriched = self._enrich_list(
            pending_kills, self._TS_FIELDS_PENDING, self._ID_FIELDS_PENDING,
        )
        self._save_enriched("pending_kills", pending_kills, enriched)

    # ── private: write enriched copy, cache original ─────────────────

    def _save_enriched(self, name: str, original: Any, enriched: Any):
        """Write the enriched data to disk but cache the clean original."""
        filepath = self._filepath(name)
        lock = self._get_lock(filepath)

        with lock:
            tmp_path = filepath + ".tmp"
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(enriched, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, filepath)
                self._cache[filepath] = original
            except IOError:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise


# Singleton instance
store = JsonStore()
