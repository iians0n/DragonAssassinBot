"""Leaderboard computation service."""

from typing import Optional, List, Dict

from storage.json_store import store


def get_individual_rankings() -> List[dict]:
    """Get all players sorted by points (desc), then KDA (desc)."""
    players = store.load_players()
    player_list = list(players.values())

    return sorted(
        player_list,
        key=lambda p: (
            p.get("points", 0),
            (p.get("kills_normal", 0) + p.get("kills_stealth", 0)) / max(1, p.get("deaths", 0)),
        ),
        reverse=True,
    )


def get_team_rankings() -> List[dict]:
    """Get team stats sorted by total points."""
    players = store.load_players()
    teams: dict[int, dict] = {}

    for p in players.values():
        t = p.get("team", 0)
        if t not in teams:
            teams[t] = {"team": t, "kills": 0, "deaths": 0, "points": 0, "players": 0}

        kills_total = p.get("kills_normal", 0) + p.get("kills_stealth", 0)
        teams[t]["kills"] += kills_total
        teams[t]["deaths"] += p.get("deaths", 0)
        teams[t]["points"] += p.get("points", 0)
        teams[t]["players"] += 1

    for t_data in teams.values():
        t_data["avg_kda"] = t_data["kills"] / max(1, t_data["deaths"])

    return sorted(teams.values(), key=lambda t: t["points"], reverse=True)


def get_player_stats(user_id: int) -> Optional[dict]:
    """Get detailed stats for a specific player."""
    players = store.load_players()
    key = str(user_id)
    if key not in players:
        return None

    p = players[key]
    kills_total = p.get("kills_normal", 0) + p.get("kills_stealth", 0)

    # Get kill history
    kills = store.load_kill_log()
    kill_events = [k for k in kills if k.get("killer_id") == user_id]
    death_events = [k for k in kills if k.get("target_id") == user_id]

    return {
        **p,
        "kills_total": kills_total,
        "kda": kills_total / max(1, p.get("deaths", 0)),
        "recent_kills": kill_events[-5:],  # Last 5 kills
        "recent_deaths": death_events[-5:],  # Last 5 deaths
    }
