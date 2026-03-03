"""Combat service — kill validation and execution."""

import time
from typing import Tuple, List

from models.player import Player
from models.kill import KillEvent
from models.bounty import Bounty
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

    # Must be within game hours (disabled for testing)
    # if not is_game_hours():
    #     return False, "❌ Kills are only allowed during game hours (9 AM – 11 PM SGT)."

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

    # Must be different teams
    if killer.team == target.team:
        return False, "❌ You can't kill your own teammate!"

    # Stealth kill: gender must match
    if kill_type == "stealth" and killer.gender != target.gender:
        return False, "❌ Stealth kills require killer and target to be the same gender."

    return True, ""


def execute_kill(killer: Player, target: Player, kill_type: str,
                 witness: str = "", photo_file_id: str = "",
                 original_timestamp: float = 0.0) -> Tuple[KillEvent, int]:
    """
    Execute a validated kill. Updates player states and returns (KillEvent, bounty_bonus).
    If original_timestamp is provided, it is used as the kill time in the log.
    """
    now = time.time()

    if kill_type == "stealth":
        cooldown = COOLDOWN_STEALTH
        points = POINTS_STEALTH_KILL
        killer.kills_stealth += 1
    else:
        cooldown = COOLDOWN_BALL
        points = POINTS_NORMAL_KILL
        killer.kills_normal += 1

    # Update target
    target.status = "cooldown"
    target.cooldown_until = now + cooldown
    target.deaths += 1

    # Check and claim bounties on target
    bounty_bonus = _claim_bounties(target.user_id, killer.user_id)

    # Update killer points
    total_points = points + bounty_bonus
    killer.points += total_points

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
    )

    kills = store.load_kill_log()
    kills.append(kill_event.to_dict())
    store.save_kill_log(kills)

    return kill_event, bounty_bonus


def _claim_bounties(target_id: int, killer_id: int) -> int:
    """Claim all active bounties on a target. Returns total bounty points."""
    bounties = store.load_bounties()
    total_bonus = 0

    for b_data in bounties:
        b = Bounty.from_dict(b_data)
        if b.target_id == target_id and b.is_active():
            b.claim(killer_id)
            total_bonus += b.points
            # Update in list
            b_data.update(b.to_dict())

    if total_bonus > 0:
        store.save_bounties(bounties)
        # Update killer's bounties_collected
        killer = get_player(killer_id)
        if killer:
            killer.bounties_collected += total_bonus
            save_player(killer)

    return total_bonus


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
