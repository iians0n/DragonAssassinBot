"""Background scheduler for cooldowns, bounties, and daily reminders."""

import logging
from telegram.ext import ContextTypes

from services.combat import restore_expired_cooldowns
from services.bounty import expire_bounties
from services.game_manager import get_game_state
from utils.formatting import send_to_group
from utils.time_utils import is_game_hours

logger = logging.getLogger(__name__)


async def cooldown_check_job(context: ContextTypes.DEFAULT_TYPE):
    """Periodically restore players whose cooldown has expired."""
    restored = restore_expired_cooldowns()
    if restored:
        game = get_game_state()
        for player in restored:
            try:
                await send_to_group(
                    context.bot,
                    f"💚 <b>{player.name}</b> has respawned and is back in the game!",
                    game,
                )
            except Exception as e:
                logger.warning(f"Failed to send respawn notification: {e}")


async def bounty_expiry_job(context: ContextTypes.DEFAULT_TYPE):
    """Expire overdue bounties and refund points."""
    expired = expire_bounties()
    if expired:
        game = get_game_state()
        for bounty, refunded in expired:
            try:
                await send_to_group(
                    context.bot,
                    f"⏰ A bounty of {refunded} pts has expired. Points refunded.",
                    game,
                )
            except Exception as e:
                logger.warning(f"Failed to send bounty expiry notification: {e}")


async def game_day_start_job(context: ContextTypes.DEFAULT_TYPE):
    """Notify group that game day has started."""
    game = get_game_state()
    if not game.is_active():
        return
    try:
        await send_to_group(
            context.bot,
            "🎯 <b>Game day has started!</b> Happy hunting! 🏹\n\n"
            "Game hours: 9 AM – 11 PM SGT",
            game,
        )
    except Exception as e:
        logger.warning(f"Failed to send day start notification: {e}")


async def game_day_warning_job(context: ContextTypes.DEFAULT_TYPE):
    """Warn group that game day is ending soon."""
    game = get_game_state()
    if not game.is_active():
        return
    try:
        await send_to_group(
            context.bot,
            "⚠️ <b>Game day ends in 1 hour!</b> Get your last kills in! ⏰",
            game,
        )
    except Exception as e:
        logger.warning(f"Failed to send day warning notification: {e}")


async def game_day_end_job(context: ContextTypes.DEFAULT_TYPE):
    """Notify group that game day has ended."""
    game = get_game_state()
    if not game.is_active():
        return
    try:
        await send_to_group(
            context.bot,
            "🌙 <b>Game day has ended.</b> See you tomorrow at 9 AM! 😴\n\n"
            "No kills count outside game hours.",
            game,
        )
    except Exception as e:
        logger.warning(f"Failed to send day end notification: {e}")
