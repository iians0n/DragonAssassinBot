"""Player registration and team assignment service."""

from typing import Optional, List

from models.player import Player
from storage.json_store import store


def get_player(user_id: int) -> Optional[Player]:
    """Get a player by Telegram user ID."""
    players = store.load_players()
    key = str(user_id)
    if key in players:
        return Player.from_dict(players[key])
    return None


def get_all_players() -> List[Player]:
    """Get all registered players."""
    players = store.load_players()
    return [Player.from_dict(p) for p in players.values()]


def is_registered(user_id: int) -> bool:
    """Check if a user is registered."""
    return str(user_id) in store.load_players()


def register_player(user_id: int, username: str, name: str, gender: str, team: int) -> Player:
    """Register a new player. Raises ValueError if already registered."""
    players = store.load_players()
    key = str(user_id)

    if key in players:
        raise ValueError("You are already registered!")

    # Auto-balance: if team is 0, check the team assignment mode
    if team == 0:
        from services.game_manager import get_game_state
        game = get_game_state()
        if game.team_assignment_mode == "auto":
            team = _get_smallest_team(players)
        # If manual, team stays 0 (Unassigned)

    player = Player(
        user_id=user_id,
        username=username,
        name=name,
        gender=gender.upper(),
        team=team,
    )

    players[key] = player.to_dict()
    store.save_players(players)
    return player


def save_player(player: Player):
    """Update an existing player's data."""
    players = store.load_players()
    players[str(player.user_id)] = player.to_dict()
    store.save_players(players)


def find_player_by_username(username: str) -> Optional[Player]:
    """Find a player by their Telegram @username."""
    clean = username.lstrip("@").lower()
    players = store.load_players()
    for p_data in players.values():
        if p_data.get("username", "").lower() == clean:
            return Player.from_dict(p_data)
    return None


def find_player_by_name(name: str) -> Optional[Player]:
    """Find a player by display name (fuzzy: lowercase, stripped spaces)."""
    normalized = name.lower().replace(" ", "")
    players = store.load_players()
    for p_data in players.values():
        player_name = p_data.get("name", "").lower().replace(" ", "")
        if player_name == normalized:
            return Player.from_dict(p_data)
    return None


def find_player_by_identifier(identifier: str) -> Optional[Player]:
    """
    Find a player by @username OR display name.
    Tries @username first, then falls back to fuzzy name match.
    """
    # If starts with @, treat as username
    if identifier.startswith("@"):
        return find_player_by_username(identifier)

    # Try username first (without @)
    player = find_player_by_username(identifier)
    if player:
        return player

    # Fall back to display name (fuzzy: lowercase, no spaces)
    return find_player_by_name(identifier)


def get_team_players(team: int) -> List[Player]:
    """Get all players on a specific team."""
    return [p for p in get_all_players() if p.team == team]


def _get_smallest_team(players: dict) -> int:
    """Find the team with fewest members for auto-balancing."""
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for p in players.values():
        t = p.get("team", 0)
        if t in counts:
            counts[t] += 1
    return min(counts, key=counts.get)

