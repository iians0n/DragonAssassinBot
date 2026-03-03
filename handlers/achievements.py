"""/achievements command handler."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from services.registration import get_player, find_player_by_identifier
from utils.formatting import format_achievements

logger = logging.getLogger(__name__)


async def achievements_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /achievements — view your badges or another player's badges."""
    if context.args:
        # View someone else's achievements
        identifier = " ".join(context.args)
        target = find_player_by_identifier(identifier)
        if not target:
            await update.message.reply_text(f"❌ Player '{identifier}' not found.")
            return

        text = f"🏅 <b>{target.name}'s Achievements</b>\n\n"
        text += format_achievements(target.achievements)
        await update.message.reply_text(text, parse_mode="HTML")
    else:
        # View own achievements
        player = get_player(update.effective_user.id)
        if not player:
            await update.message.reply_text("❌ You're not registered. Use /register first.")
            return

        text = format_achievements(player.achievements)
        await update.message.reply_text(text, parse_mode="HTML")
