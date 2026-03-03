"""Achievement checking service."""

import time
from typing import List, Tuple

from models.player import Player
from models.achievement import ACHIEVEMENTS
from services.registration import save_player


def check_achievements(player: Player, kill_event=None, bounty_bonus: int = 0) -> List[Tuple[str, str, str]]:
    """
    Check if a player has unlocked any new achievements.
    Returns list of (emoji, name, description) for newly unlocked achievements.
    """
    newly_unlocked = []

    checks = {
        # Kill milestones
        "first_blood": lambda: player.kills_total >= 1,
        "serial_killer": lambda: player.kills_total >= 10,
        "legend": lambda: player.kills_total >= 20,

        # Streak achievements
        "triple_kill": lambda: player.current_streak >= 3,
        "penta_kill": lambda: player.current_streak >= 5,
        "unstoppable": lambda: player.current_streak >= 10,

        # Stealth achievements
        "shadow": lambda: player.kills_stealth >= 3,
        "silent_assassin": lambda: player.kills_stealth >= 5,

        # Bounty achievements
        "bounty_hunter": lambda: bounty_bonus > 0,

        # Resilience achievements
        "survivor": lambda: player.deaths >= 5 and player.kda > 1.0,
        "comeback_kid": lambda: (
            kill_event is not None
            and hasattr(kill_event, "timestamp")
            and player.cooldown_until > 0
            and (kill_event.timestamp - player.cooldown_until) <= 600
            and (kill_event.timestamp - player.cooldown_until) >= 0
        ),
    }

    for achievement_id, check_fn in checks.items():
        if achievement_id in player.achievements:
            continue  # Already unlocked
        if achievement_id not in ACHIEVEMENTS:
            continue  # Unknown achievement

        try:
            if check_fn():
                player.achievements.append(achievement_id)
                emoji, name, desc = ACHIEVEMENTS[achievement_id]
                newly_unlocked.append((emoji, name, desc))
        except Exception:
            pass  # Skip broken checks silently

    if newly_unlocked:
        save_player(player)

    return newly_unlocked
