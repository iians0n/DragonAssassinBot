"""/kill, /stealthkill command handlers."""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from services.registration import get_player, find_player_by_identifier
from services.combat import validate_kill, execute_kill
from services.game_manager import get_game_state
from utils.formatting import (
    format_kill_announcement,
    format_death_dm,
    format_leaderboard,
    format_team_leaderboard,
    send_to_group,
)
from config import COOLDOWN_BALL, COOLDOWN_STEALTH

logger = logging.getLogger(__name__)


async def kill_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /kill @target — report a normal kill."""
    await _process_kill(update, context, kill_type="normal")


async def stealthkill_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stealthkill @target — report a stealth kill (requires photo)."""
    await _process_kill(update, context, kill_type="stealth")


async def stealthkill_photo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages with /stealthkill caption."""
    # Parse args from caption since this isn't a regular CommandHandler
    caption = update.message.caption or ""
    parts = caption.split()
    # Set context.args manually (skip the /stealthkill part)
    context.args = parts[1:] if len(parts) > 1 else []
    await _process_kill(update, context, kill_type="stealth")


async def _process_kill(update: Update, context: ContextTypes.DEFAULT_TYPE, kill_type: str):
    """Core kill processing logic for both normal and stealth kills."""
    user = update.effective_user

    # Get killer
    killer = get_player(user.id)
    if not killer:
        await update.message.reply_text("❌ You're not registered. Use /register first.")
        return

    # Parse target from command args
    if not context.args:
        if kill_type == "stealth":
            await update.message.reply_text(
                "Usage: /stealthkill <name or @username>\n"
                "📸 Attach a photo or reply to a photo as proof!"
            )
        else:
            await update.message.reply_text("Usage: /kill <name or @username>")
        return

    # Join all args as the identifier (supports multi-word display names)
    # e.g. /kill John Doe  or  /kill @johndoe
    identifier = " ".join(context.args)
    target = find_player_by_identifier(identifier)
    if not target:
        await update.message.reply_text(
            f"❌ Player '{identifier}' not found. Make sure they're registered.\n"
            f"You can use their display name or @username."
        )
        return

    # For stealth kills, check for photo
    photo_file_id = ""
    if kill_type == "stealth":
        if update.message.photo:
            photo_file_id = update.message.photo[-1].file_id
        elif update.message.reply_to_message and update.message.reply_to_message.photo:
            photo_file_id = update.message.reply_to_message.photo[-1].file_id
        else:
            await update.message.reply_text(
                "❌ Stealth kills require photo proof!\n"
                "Send /stealthkill @username with a photo attached, "
                "or reply to a photo with the command."
            )
            return

    # Get witness (optional second arg)
    witness = ""
    if len(context.args) > 1:
        witness = context.args[1].lstrip("@")

    # Validate
    game = get_game_state()
    valid, error_msg = validate_kill(killer, target, kill_type, game.status)
    if not valid:
        await update.message.reply_text(error_msg, parse_mode="HTML")
        return

    # Execute kill
    kill_event, bounty_bonus = execute_kill(
        killer, target, kill_type,
        witness=witness,
        photo_file_id=photo_file_id,
    )

    # Refresh player data after kill
    killer = get_player(user.id)
    target = get_player(kill_event.target_id)

    # Announce to group
    announcement = format_kill_announcement(
        killer.to_dict(), target.to_dict(), kill_type, bounty_bonus
    )

    # Send to current chat
    await update.message.reply_text(
        f"✅ Kill confirmed!\n\n{announcement}",
        parse_mode="HTML",
    )

    # Try to DM the target
    cooldown_hours = COOLDOWN_STEALTH / 3600 if kill_type == "stealth" else COOLDOWN_BALL / 3600
    dm_text = format_death_dm(killer.to_dict(), kill_type, cooldown_hours)
    try:
        await context.bot.send_message(
            chat_id=target.user_id,
            text=dm_text,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not DM target {target.user_id}: {e}")

    # Post to group chat if this isn't the group
    group_id = game.group_chat_id
    if group_id and update.effective_chat.id != group_id:
        try:
            await send_to_group(context.bot, announcement, game)
        except Exception as e:
            logger.warning(f"Could not post to group {group_id}: {e}")

    # Auto-post leaderboard update to group
    if group_id:
        try:
            from services.leaderboard import get_individual_rankings
            rankings = get_individual_rankings()
            lb_text = format_leaderboard(rankings)
            team_text = format_team_leaderboard(rankings)
            await send_to_group(context.bot, f"{lb_text}\n{team_text}", game)
        except Exception as e:
            logger.warning(f"Could not post leaderboard update: {e}")

