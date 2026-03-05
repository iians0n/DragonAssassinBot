"""/ball, /postit command handlers — creates pending kills with dispute window."""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler

from services.registration import get_player, find_player_by_identifier
from services.combat import validate_kill
from services.game_manager import get_game_state
from services.pending_kill import create_pending_kill, has_pending_kill_against
from utils.formatting import player_mention
from utils.dm_only import dm_only
from config import KILL_DISPUTE_WINDOW

logger = logging.getLogger(__name__)


@dm_only
async def ball_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ball @target — report a normal kill."""
    await _process_kill(update, context, kill_type="normal")


@dm_only
async def postit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /postit @target — report a stealth kill (requires photo)."""
    await _process_kill(update, context, kill_type="stealth")


@dm_only
async def postit_photo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages with /postit caption."""
    # Parse args from caption since this isn't a regular CommandHandler
    caption = update.message.caption or ""
    parts = caption.split()
    # Set context.args manually (skip the /postit part)
    context.args = parts[1:] if len(parts) > 1 else []
    await _process_kill(update, context, kill_type="stealth")


async def _process_kill(update: Update, context: ContextTypes.DEFAULT_TYPE, kill_type: str):
    """Core kill processing logic — creates a pending kill instead of executing immediately."""
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
                "Usage: /postit <name or @username>\n"
                "📸 Attach a photo or reply to a photo as proof!"
            )
        else:
            await update.message.reply_text("Usage: /ball <name or @username>")
        return

    # Join all args as the identifier (supports multi-word display names)
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
                "Send /postit @username with a photo attached, "
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

    # Check for duplicate pending kill on same target
    if has_pending_kill_against(target.user_id):
        await update.message.reply_text(
            f"⚠️ There's already a pending kill on {target.name}. "
            f"Wait for it to resolve before reporting another."
        )
        return

    # Create pending kill (NOT executed yet)
    pending = create_pending_kill(
        killer, target, kill_type,
        witness=witness,
        photo_file_id=photo_file_id,
    )

    minutes = int(KILL_DISPUTE_WINDOW / 60)
    target_mention = player_mention(target.username, target.name)
    killer_mention = player_mention(killer.username, killer.name)

    # Reply to killer with kills remaining
    from services.combat import get_kills_remaining
    kills_left = get_kills_remaining(killer.user_id) - 1  # -1 for this pending kill
    kills_left_text = f"\n🎯 Kills remaining today: {max(0, kills_left)}"

    await update.message.reply_text(
        f"⏳ Kill reported on <b>{target_mention}</b>!\n\n"
        f"Waiting for confirmation ({minutes} min window).\n"
        f"If {target_mention} does not dispute, the kill will be auto-confirmed."
        f"{kills_left_text}",
        parse_mode="HTML",
    )

    # DM the target with Accept / Dispute buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept Kill", callback_data=f"kill_accept:{pending.id}"),
            InlineKeyboardButton("❌ Dispute Kill", callback_data=f"kill_dispute:{pending.id}"),
        ]
    ])

    kill_type_text = "🗡️ stealth kill (post-it)" if kill_type == "stealth" else "☠️ normal kill (ball)"

    try:
        await context.bot.send_message(
            chat_id=target.user_id,
            text=(
                f"⚠️ <b>Kill Report</b>\n\n"
                f"<b>{killer_mention}</b> reported a {kill_type_text} on you!\n\n"
                f"You have <b>{minutes} minutes</b> to respond.\n"
                f"If you don't respond, the kill will be <b>auto-confirmed</b>.\n\n"
                f"Do you accept or dispute this kill?"
            ),
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.warning(f"Could not DM target {target.user_id}: {e}")
        await update.message.reply_text(
            f"⚠️ Could not DM {target_mention}. They may need to start the bot first.\n"
            f"The kill will auto-confirm in {minutes} minutes if not disputed."
        )
