"""/bounty, /bounties command handlers."""

import logging
import time
from telegram import Update
from telegram.ext import ContextTypes

from services.registration import get_player, find_player_by_identifier
from services.bounty import place_bounty, get_active_bounties
from services.game_manager import get_game_state
from utils.formatting import team_label, send_to_group
from utils.time_utils import format_duration

logger = logging.getLogger(__name__)


async def bounty_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /bounty @target [points] — place a bounty."""
    user = update.effective_user

    # Check game is active
    game = get_game_state()
    if not game.is_active():
        await update.message.reply_text("❌ The game is not currently active.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /bounty @username [points]\n"
            "Example: /bounty @player123 5"
        )
        return

    target_username = context.args[0].lstrip("@")
    try:
        points = int(context.args[-1])  # Last arg is points
        # Everything between first arg and last arg is the name
        name_parts = context.args[:-1]
    except ValueError:
        await update.message.reply_text("❌ Points must be a number. Example: /bounty @player 5")
        return

    identifier = " ".join(name_parts)
    target = find_player_by_identifier(identifier)
    if not target:
        await update.message.reply_text(f"❌ Player '{identifier}' not found.")
        return

    success, error_msg, bounty = place_bounty(user.id, target.user_id, points)
    if not success:
        await update.message.reply_text(error_msg)
        return

    await update.message.reply_text(
        f"🎯 <b>Bounty Placed!</b>\n\n"
        f"💰 <b>{points} pts</b> on @{target_username}\n"
        f"⏰ Expires in 24 hours\n\n"
        f"Anyone who kills this target will collect the bounty!",
        parse_mode="HTML",
    )

    # Announce to group
    group_id = game.group_chat_id
    if group_id and update.effective_chat.id != group_id:
        try:
            await send_to_group(
                context.bot,
                f"🎯 <b>New Bounty!</b>\n"
                f"💰 {points} pts on a {team_label(target.team)} member "
                f"({'M' if target.gender == 'M' else 'F'})\n"
                f"⏰ Expires in 24 hours",
                game,
            )
        except Exception as e:
            logger.warning(f"Could not post bounty to group: {e}")


async def bounties_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /bounties — list all active bounties (anonymized)."""
    active = get_active_bounties()

    if not active:
        await update.message.reply_text("🎯 No active bounties right now.")
        return

    lines = ["🎯 <b>ACTIVE BOUNTIES</b> 🎯", ""]

    for i, b in enumerate(active, 1):
        # Get target info for anonymized display
        target = get_player(b.target_id)
        if target:
            hint = f"{team_label(target.team)} ({'M' if target.gender == 'M' else 'F'})"
        else:
            hint = "Unknown"

        remaining = b.expires_at - time.time()
        time_str = format_duration(max(0, remaining))

        lines.append(f"{i}. 💰 <b>{b.points} pts</b> — Target: {hint} — Expires in {time_str}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
