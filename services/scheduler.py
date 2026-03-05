"""Background scheduler for cooldowns, bounties, pending kills, and daily reminders."""

import logging
from telegram.ext import ContextTypes

from services.combat import restore_expired_cooldowns
from services.bounty import expire_bounties
from services.pending_kill import get_expired_pending_kills, confirm_pending_kill
from services.game_manager import get_game_state
from services.registration import get_player
from utils.formatting import (
    format_kill_announcement,
    format_leaderboard,
    format_team_leaderboard,
    send_to_group,
)
from utils.time_utils import is_game_hours
from config import COOLDOWN_BALL, COOLDOWN_STEALTH

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
    """Notify group that game day has ended, apply role bonuses, and reshuffle roles."""
    game = get_game_state()
    if not game.is_active():
        return

    # 1. Apply daily role bonuses
    from services.roles import apply_daily_bonuses, assign_all_roles, send_roles_to_team_gc, send_bonus_summary_to_team_gc

    bonus_results = apply_daily_bonuses()

    # 2. Announce day end to main group
    try:
        bonus_msg = ""
        if bonus_results:
            total_bonus = sum(b for _, b, _ in bonus_results)
            bonus_msg = f"\n\n🎁 <b>Role bonuses applied!</b> ({total_bonus} pts distributed)"
        await send_to_group(
            context.bot,
            "🌙 <b>Game day has ended.</b> See you tomorrow at 9 AM! 😴\n\n"
            "No kills count outside game hours."
            f"{bonus_msg}",
            game,
        )
    except Exception as e:
        logger.warning(f"Failed to send day end notification: {e}")

    # 3. Send bonus details to each team GC
    if bonus_results:
        for team in range(1, 5):
            try:
                await send_bonus_summary_to_team_gc(context.bot, team, bonus_results, game)
            except Exception as e:
                logger.warning(f"Failed to send bonus summary to team {team}: {e}")

    # 4. Reshuffle roles for next day
    role_result = assign_all_roles()

    # 5. Send new roles to team GCs
    for team, players in role_result.items():
        try:
            await send_roles_to_team_gc(context.bot, team, players, game)
        except Exception as e:
            logger.warning(f"Failed to send new roles to team {team} GC: {e}")


async def pending_kill_expiry_job(context: ContextTypes.DEFAULT_TYPE):
    """Auto-confirm pending kills whose dispute window has expired."""
    expired = get_expired_pending_kills()
    if not expired:
        return

    game = get_game_state()

    for pk in expired:
        kill_event_dict, bounty_bonus, new_achievements = confirm_pending_kill(pk.id, resolution_type="auto-confirmed")
        if not kill_event_dict:
            continue

        killer = get_player(pk.killer_id)
        target = get_player(pk.target_id)
        if not killer or not target:
            continue

        # Announce to group (with streak + achievements)
        announcement = format_kill_announcement(
            killer.to_dict(), target.to_dict(), pk.kill_type, bounty_bonus,
            new_achievements=new_achievements,
        )
        group_id = game.group_chat_id
        if group_id:
            try:
                await send_to_group(context.bot, announcement, game)
            except Exception as e:
                logger.warning(f"Could not post auto-confirmed kill to group: {e}")

        # DM target about cooldown
        cooldown_hours = COOLDOWN_STEALTH / 3600 if pk.kill_type == "stealth" else COOLDOWN_BALL / 3600
        try:
            await context.bot.send_message(
                chat_id=target.user_id,
                text=(
                    f"⏰ Your dispute window expired. The kill by <b>{killer.name}</b> "
                    f"has been <b>auto-confirmed</b>.\n"
                    f"💀 Cooldown: {cooldown_hours:.0f} hour(s). You'll respawn automatically."
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Could not DM target about auto-confirm: {e}")

        # Notify killer
        try:
            await context.bot.send_message(
                chat_id=killer.user_id,
                text=(
                    f"✅ Your kill on <b>{target.name}</b> has been <b>auto-confirmed</b>! "
                    f"(No dispute within the window)"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Could not DM killer about auto-confirm: {e}")


_leaderboard_counter = 0

async def leaderboard_update_job(context: ContextTypes.DEFAULT_TYPE):
    """Post leaderboard to group chat on a scheduled interval."""
    if not is_game_hours():
        return

    global _leaderboard_counter

    game = get_game_state()
    if not game.is_active():
        return

    group_id = game.group_chat_id
    if not group_id:
        return

    try:
        from services.leaderboard import get_individual_rankings
        rankings = get_individual_rankings()
        if not rankings:
            return
        _leaderboard_counter += 1
        lb_text = format_leaderboard(rankings)
        team_text = format_team_leaderboard(rankings)
        counter_text = f"\n📡 <i>Update #{_leaderboard_counter}</i>"
        await send_to_group(context.bot, f"{lb_text}\n{team_text}{counter_text}", game)
    except Exception as e:
        logger.warning(f"Could not post scheduled leaderboard update: {e}")
