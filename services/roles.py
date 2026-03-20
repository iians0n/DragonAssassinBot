"""Role management service — assignment, bonuses, and team GC messaging."""

import logging
import random
from typing import List, Tuple
from datetime import datetime

import pytz

from models.player import Player
from services.registration import get_all_players, get_team_players, save_player
from storage.json_store import store
from config import (
    ROLE_NORMAL, ROLE_NINJA, ROLE_SNIPER, ROLE_PRESIDENT,
    POINTS_NORMAL_KILL, POINTS_STEALTH_KILL, POINTS_PRESIDENT_KILL,
    NINJA_STEALTH_MULTIPLIER, SNIPER_NORMAL_MULTIPLIER, TIMEZONE,
)

logger = logging.getLogger(__name__)

ROLE_DISPLAY = {
    ROLE_NORMAL: "👤 Normal",
    ROLE_NINJA: "🥷 Ninja",
    ROLE_SNIPER: "🎯 Sniper",
    ROLE_PRESIDENT: "👑 President",
}


def get_role_display(role: str) -> str:
    """Get emoji + label for a role."""
    return ROLE_DISPLAY.get(role, "👤 Normal")


def assign_roles_to_team(team: int) -> List[Player]:
    """Randomly assign exactly 1 Ninja, 1 Sniper, 1 President to a team.

    Remaining players become Normal. Returns list of updated players.
    """
    players = get_team_players(team)
    if not players:
        return []

    # Shuffle to randomize role assignments
    random.shuffle(players)

    roles_to_assign = [ROLE_NINJA, ROLE_SNIPER, ROLE_PRESIDENT]

    for player in players:
        if roles_to_assign:
            player.role = roles_to_assign.pop(0)
        else:
            player.role = ROLE_NORMAL

        # Reset president_used for new president
        if player.role == ROLE_PRESIDENT:
            player.president_used = False

        save_player(player)

    return players


def assign_all_roles() -> dict:
    """Assign roles for all 4 teams. Returns {team: [players]}."""
    result = {}
    for team in range(1, 5):
        result[team] = assign_roles_to_team(team)
    return result


def calculate_daily_bonuses() -> List[Tuple[int, int, str]]:
    """Calculate role-based bonus points from today's kills.

    Scans the kill log for kills that happened today (SGT).
    Returns list of (user_id, bonus_amount, reason) tuples.
    """
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_ts = today_start.timestamp()

    kills = store.load_kill_log()
    players_dict = store.load_players()

    bonuses: List[Tuple[int, int, str]] = []

    for kill in kills:
        if kill.get("timestamp", 0) < today_start_ts:
            continue

        killer_id = kill.get("killer_id")
        killer_data = players_dict.get(str(killer_id))
        if not killer_data:
            continue

        killer_role = killer_data.get("role", ROLE_NORMAL)
        kill_type = kill.get("kill_type", "normal")

        # Ninja bonus: extra points for stealth kills (x2 means +base again)
        if killer_role == ROLE_NINJA and kill_type == "stealth":
            bonus = POINTS_STEALTH_KILL  # The extra from x2
            bonuses.append((killer_id, bonus, f"🥷 Ninja stealth bonus (+{bonus})"))

        # Sniper bonus: extra points for normal kills (x2 means +base again)
        if killer_role == ROLE_SNIPER and kill_type == "normal":
            bonus = POINTS_NORMAL_KILL  # The extra from x2
            bonuses.append((killer_id, bonus, f"🎯 Sniper precision bonus (+{bonus})"))

        # President kill bonus: awarded to killer
        if kill.get("target_was_president", False):
            bonuses.append((killer_id, POINTS_PRESIDENT_KILL,
                            f"👑 President elimination bonus (+{POINTS_PRESIDENT_KILL})"))

    return bonuses


def apply_daily_bonuses() -> List[Tuple[str, int, str]]:
    """Move accumulated hidden bonus points into visible points.

    Returns list of (player_name, bonus_amount, description) for announcement.
    """
    all_players = get_all_players()
    results = []

    for player in all_players:
        if player.bonus_points > 0:
            player.points += player.bonus_points
            results.append((player.name, player.bonus_points, f"Role bonus: +{player.bonus_points}"))
            player.bonus_points = 0
            save_player(player)

    return results


async def send_roles_to_team_gc(bot, team: int, players: List[Player], game_state):
    """Send role assignments to a team's group chat."""
    team_chat_id = game_state.team_chat_ids.get(str(team))
    if not team_chat_id:
        logger.info(f"No GC set for team {team}, skipping role announcement")
        return

    lines = [f"🎭 <b>New Role Assignments — Team {team}</b>", ""]
    for p in players:
        if p.role == ROLE_NORMAL:
            continue  # Only show special roles
        lines.append(f"  {get_role_display(p.role)} — <b>{p.name}</b>")

    lines.append("")
    lines.append("<i>🤫 Keep your roles secret from other teams!</i>")

    try:
        kwargs = {
            "chat_id": team_chat_id,
            "text": "\n".join(lines),
            "parse_mode": "HTML",
        }
        topic_id = getattr(game_state, "team_topic_ids", {}).get(str(team))
        if topic_id:
            kwargs["message_thread_id"] = topic_id
            
        await bot.send_message(**kwargs)
    except Exception as e:
        logger.warning(f"Could not send roles to team {team} GC: {e}")


async def send_bonus_summary_to_team_gc(bot, team: int, results: List[Tuple[str, int, str]], game_state):
    """Send bonus point summary to a team's GC (only shows that team's players)."""
    team_chat_id = game_state.team_chat_ids.get(str(team))
    if not team_chat_id:
        return

    team_players = get_team_players(team)
    team_names = {p.name for p in team_players}

    team_results = [(name, bonus, reason) for name, bonus, reason in results if name in team_names]
    if not team_results:
        return

    lines = [f"🎁 <b>Daily Role Bonuses — Team {team}</b>", ""]
    for name, bonus, reason in team_results:
        lines.append(f"  <b>{name}</b>: +{bonus} pts ({reason})")

    try:
        kwargs = {
            "chat_id": team_chat_id,
            "text": "\n".join(lines),
            "parse_mode": "HTML",
        }
        topic_id = getattr(game_state, "team_topic_ids", {}).get(str(team))
        if topic_id:
            kwargs["message_thread_id"] = topic_id
            
        await bot.send_message(**kwargs)
    except Exception as e:
        logger.warning(f"Could not send bonus summary to team {team} GC: {e}")
