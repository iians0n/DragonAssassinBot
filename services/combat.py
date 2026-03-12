"""Combat service — kill validation and execution."""

import time
from typing import Tuple, List

from models.player import Player
from models.kill import KillEvent
# from models.bounty import Bounty  # Bounty disabled
from storage.json_store import store
from services.registration import get_player, save_player
from utils.time_utils import is_game_hours
from config import COOLDOWN_BALL, COOLDOWN_STEALTH, POINTS_NORMAL_KILL, POINTS_STEALTH_KILL


def validate_kill(killer: Player, target: Player, kill_type: str, game_status: str) -> Tuple[bool, str]:
    """
    Validate whether a kill attempt is legal.
    Returns (is_valid, error_message).
    """
    # Game must be active
    if game_status != "active":
        return False, "❌ The game is not currently active."

    # Must be within game hours

    if not is_game_hours():
        return False, "❌ Kills are only allowed during game hours (9 AM – 11 PM SGT)."


    # Can't kill yourself
    if killer.user_id == target.user_id:
        return False, "❌ You can't kill yourself!"

    # Killer must be alive (not in cooldown)
    if not killer.is_active():
        if killer.status == "cooldown":
            from utils.time_utils import format_duration
            remaining = killer.cooldown_until - time.time()
            return False, f"❌ You're in cooldown! Respawn in {format_duration(max(0, remaining))}."
        return False, "❌ You're not in an active state."

    # Target must be alive
    if not target.can_be_killed():
        return False, f"❌ {target.name} is already dead (in cooldown). Wait for them to respawn!"

    # Unassigned players (Team 0) cannot participate in combat
    if killer.team == 0:
        return False, "❌ You have not been assigned to a team yet!"
    if target.team == 0:
        return False, f"❌ {target.name} has not been assigned to a team yet!"

    # Must be different teams
    if killer.team == target.team:
        return False, "❌ You can't kill your own teammate!"

    # Stealth kill: gender must match
    if kill_type == "stealth" and killer.gender != target.gender:
        return False, "❌ Stealth kills require killer and target to be the same gender."

    # Daily kill limit (normal kills only — stealth kills are unlimited)
    if kill_type != "stealth":
        from config import DAILY_KILL_LIMIT
        from services.game_manager import is_admin
        if not is_admin(killer.user_id):
            today_kills = get_daily_kill_count(killer.user_id)
            if today_kills >= DAILY_KILL_LIMIT:
                return False, f"❌ You've used all {DAILY_KILL_LIMIT} normal kills for today. Resets tomorrow at 9 AM!"

    return True, ""


def get_daily_kill_count(user_id: int) -> int:
    """Count how many normal (non-stealth) kills a player has made today (SGT)."""
    from datetime import datetime
    import pytz
    from config import TIMEZONE

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_ts = today_start.timestamp()

    kills = store.load_kill_log()
    count = 0
    for kill in kills:
        if (kill.get("killer_id") == user_id
                and kill.get("timestamp", 0) >= today_start_ts
                and kill.get("kill_type") != "stealth"):
            count += 1
    return count


def get_kills_remaining(user_id: int) -> int:
    """Get how many normal kills a player has left today (stealth kills are unlimited)."""
    from config import DAILY_KILL_LIMIT
    return max(0, DAILY_KILL_LIMIT - get_daily_kill_count(user_id))


def execute_kill(killer: Player, target: Player, kill_type: str,
                 witness: str = "", photo_file_id: str = "",
                 original_timestamp: float = 0.0) -> Tuple[KillEvent, int, list]:
    """
    Execute a validated kill. Updates player states and returns
    (KillEvent, bounty_bonus, newly_unlocked_achievements).
    If original_timestamp is provided, it is used as the kill time in the log.
    """
    from services.achievements import check_achievements
    from config import ROLE_PRESIDENT, ROLE_NORMAL

    now = time.time()

    if kill_type == "stealth":
        cooldown = COOLDOWN_STEALTH
        points = POINTS_STEALTH_KILL
        killer.kills_stealth += 1
    else:
        cooldown = COOLDOWN_BALL
        points = POINTS_NORMAL_KILL
        killer.kills_normal += 1

    # Check if target is president (before updating status)
    target_was_president = (target.role == ROLE_PRESIDENT and not target.president_used)

    # Update target
    target.status = "cooldown"
    target.cooldown_until = now + cooldown
    target.deaths += 1

    # If target was president, downgrade to normal after first death
    if target_was_president:
        target.president_used = True
        target.role = ROLE_NORMAL

    # Reset target's kill streak
    target.current_streak = 0

    # Update killer's kill streak
    killer.current_streak += 1
    if killer.current_streak > killer.best_streak:
        killer.best_streak = killer.current_streak

    # Bounty system disabled
    # bounty_bonus = _claim_bounties(target.user_id, killer.user_id)
    bounty_bonus = 0

    # Update killer points (base points only — role bonuses hidden until EOD)
    total_points = points + bounty_bonus
    killer.points += total_points

    # Accumulate hidden role bonus points (revealed at day end)
    from config import ROLE_NINJA, ROLE_SNIPER, POINTS_PRESIDENT_KILL
    bonus = 0
    if killer.role == ROLE_NINJA and kill_type == "stealth":
        bonus += POINTS_STEALTH_KILL  # x2 means +base again
    if killer.role == ROLE_SNIPER and kill_type == "normal":
        bonus += POINTS_NORMAL_KILL   # x2 means +base again
    if target_was_president:
        bonus += POINTS_PRESIDENT_KILL
    if bonus > 0:
        killer.bonus_points += bonus

    # Save both players
    save_player(killer)
    save_player(target)

    # Log the kill
    kill_event = KillEvent.create(
        killer_id=killer.user_id,
        target_id=target.user_id,
        kill_type=kill_type,
        witness=witness,
        photo_file_id=photo_file_id,
        points_awarded=total_points,
        bounty_claimed=bounty_bonus,
        timestamp=original_timestamp,
        target_was_president=target_was_president,
    )

    kills = store.load_kill_log()
    kills.append(kill_event.to_dict())
    store.save_kill_log(kills)

    # Check achievements for killer
    new_achievements = check_achievements(killer, kill_event, bounty_bonus)

    return kill_event, bounty_bonus, new_achievements



def revert_kill(kill_entry: dict) -> Tuple[bool, str]:
    """
    Fully revert a confirmed kill. Undoes all stat/point changes for both
    killer and target, handles role bonuses, and removes the kill from the log.
    Returns (success, message).
    """
    from config import (
        ROLE_NINJA, ROLE_SNIPER, ROLE_PRESIDENT, ROLE_NORMAL,
        POINTS_STEALTH_KILL, POINTS_NORMAL_KILL, POINTS_PRESIDENT_KILL,
    )

    kill_id = kill_entry.get("id")
    killer_id = kill_entry.get("killer_id")
    target_id = kill_entry.get("target_id")
    kill_type = kill_entry.get("kill_type", "normal")
    points_awarded = kill_entry.get("points_awarded", 0)
    target_was_president = kill_entry.get("target_was_president", False)

    killer = get_player(killer_id)
    target = get_player(target_id)

    if not killer or not target:
        return False, "Could not find killer or target player data."

    # --- Revert target ---
    target.status = "alive"
    target.cooldown_until = 0.0
    target.deaths = max(0, target.deaths - 1)

    # Restore president role if this kill caused demotion
    if target_was_president:
        target.role = ROLE_PRESIDENT
        target.president_used = False

    # --- Revert killer ---
    if kill_type == "stealth":
        killer.kills_stealth = max(0, killer.kills_stealth - 1)
    else:
        killer.kills_normal = max(0, killer.kills_normal - 1)

    # Subtract base points
    killer.points -= points_awarded

    # Subtract hidden role bonuses
    bonus_to_remove = 0
    if killer.role == ROLE_NINJA and kill_type == "stealth":
        bonus_to_remove += POINTS_STEALTH_KILL
    if killer.role == ROLE_SNIPER and kill_type == "normal":
        bonus_to_remove += POINTS_NORMAL_KILL
    if target_was_president:
        bonus_to_remove += POINTS_PRESIDENT_KILL
    if bonus_to_remove > 0:
        killer.bonus_points = max(0, killer.bonus_points - bonus_to_remove)

    # Revert streak (can't perfectly restore, just decrement)
    killer.current_streak = max(0, killer.current_streak - 1)

    # Save both players
    save_player(killer)
    save_player(target)

    # Remove kill from log
    kills = store.load_kill_log()
    kills = [k for k in kills if k.get("id") != kill_id]
    store.save_kill_log(kills)

    return True, f"Reverted kill: {killer.name} → {target.name}"


# Bounty system disabled
# def _claim_bounties(target_id: int, killer_id: int) -> int:
#     """Claim all active bounties on a target. Returns total bounty points."""
#     bounties = store.load_bounties()
#     total_bonus = 0
#
#     for b_data in bounties:
#         b = Bounty.from_dict(b_data)
#         if b.target_id == target_id and b.is_active():
#             b.claim(killer_id)
#             total_bonus += b.points
#             b_data.update(b.to_dict())
#
#     if total_bonus > 0:
#         store.save_bounties(bounties)
#         killer = get_player(killer_id)
#         if killer:
#             killer.bounties_collected += total_bonus
#             save_player(killer)
#
#     return total_bonus


def restore_expired_cooldowns() -> List[Player]:
    """Check all players and restore any expired cooldowns. Returns restored players."""
    players = store.load_players()
    restored = []
    now = time.time()

    for key, p_data in players.items():
        if p_data.get("status") == "cooldown" and now >= p_data.get("cooldown_until", 0):
            p_data["status"] = "alive"
            p_data["cooldown_until"] = 0.0
            restored.append(Player.from_dict(p_data))

    if restored:
        store.save_players(players)

    return restored
