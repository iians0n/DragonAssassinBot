"""/start, /register, /profile command handlers."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from services.registration import register_player, get_player, is_registered
from utils.formatting import format_player_card, team_label
from utils.dm_only import dm_only

logger = logging.getLogger(__name__)

# Conversation states for registration
NAME, GENDER, TEAM = range(3)

GAME_INTRO = (
    "🎯 <b>ASSASSINS GAME TRACKER</b> 🎯\n\n"
    "Welcome to the Assassins Game!\n\n"
    "📋 <b>Rules:</b>\n"
    "• 4 teams compete over 1 week\n"
    "• 🏓 /ball (ping pong throw): +10 pts, target cooldown 2hrs\n"
    "• 🗡️ /postit (post-it + photo): +5 pts, must be same gender, 1hr cooldown\n"
    "• 🎭 Hidden roles: Ninja, Sniper, President — bonus points at day end!\n"
    "• 🎯 Max 2 kills per day\n"
    "• Game hours: 9 AM – 11 PM SGT\n"
    "• Most points wins! 🏆\n\n"
    "Hit /register to join the game!"
)


@dm_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command — show game info."""
    if is_registered(update.effective_user.id):
        await update.message.reply_text(
            GAME_INTRO + "\n\n✅ You're already registered! Use /profile to see your stats.",
            parse_mode="HTML",
        )
    else:
        keyboard = [[InlineKeyboardButton("📝 Register Now", callback_data="begin_register")]]
        await update.message.reply_text(
            GAME_INTRO,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


@dm_only
async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Begin registration — ask for name. Triggered by /register or button."""
    user_id = update.effective_user.id
    if is_registered(user_id):
        text = "✅ You're already registered! Use /profile to see your stats."
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, parse_mode="HTML")
        else:
            await update.message.reply_text(text, parse_mode="HTML")
        return ConversationHandler.END

    text = "📝 <b>Registration</b>\n\nWhat's your name? (This will be your display name)"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text(text, parse_mode="HTML")
    return NAME


async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive name, ask for gender."""
    name = update.message.text.strip()
    if not name or len(name) > 50:
        await update.message.reply_text("❌ Please enter a valid name (1-50 characters).")
        return NAME

    context.user_data["reg_name"] = name

    keyboard = [
        [
            InlineKeyboardButton("♂️ Male", callback_data="gender_M"),
            InlineKeyboardButton("♀️ Female", callback_data="gender_F"),
        ]
    ]
    await update.message.reply_text(
        f"👋 Hi <b>{name}</b>! What's your gender?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return GENDER


async def register_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive gender, ask for team."""
    query = update.callback_query
    await query.answer()

    gender = query.data.split("_")[1]  # "M" or "F"
    context.user_data["reg_gender"] = gender

    keyboard = [
        [
            InlineKeyboardButton(f"🔴 Team 1", callback_data="team_1"),
            InlineKeyboardButton(f"🔵 Team 2", callback_data="team_2"),
        ],
        [
            InlineKeyboardButton(f"🟢 Team 3", callback_data="team_3"),
            InlineKeyboardButton(f"🟡 Team 4", callback_data="team_4"),
        ],
        [InlineKeyboardButton("🎲 Random (auto-balance)", callback_data="team_0")],
    ]
    await query.edit_message_text(
        "Choose your team:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return TEAM


async def register_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive team, complete registration."""
    query = update.callback_query
    await query.answer()

    team = int(query.data.split("_")[1])  # 0-4
    user = update.effective_user

    try:
        player = register_player(
            user_id=user.id,
            username=user.username or "",
            name=context.user_data["reg_name"],
            gender=context.user_data["reg_gender"],
            team=team,
        )
        await query.edit_message_text(
            f"✅ <b>Registration Complete!</b>\n\n"
            f"{format_player_card(player.to_dict())}\n\n"
            f"Use /profile anytime to see your stats. Good luck! 🎯",
            parse_mode="HTML",
        )
    except ValueError as e:
        await query.edit_message_text(f"❌ {e}")

    # Clear temp data
    context.user_data.pop("reg_name", None)
    context.user_data.pop("reg_gender", None)
    return ConversationHandler.END


async def register_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel registration."""
    await update.message.reply_text("❌ Registration cancelled.")
    context.user_data.pop("reg_name", None)
    context.user_data.pop("reg_gender", None)
    return ConversationHandler.END


@dm_only
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /profile — show own stats."""
    player = get_player(update.effective_user.id)
    if not player:
        await update.message.reply_text(
            "❌ You're not registered yet. Use /register to join!",
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(
        format_player_card(player.to_dict()),
        parse_mode="HTML",
    )


def get_registration_handler() -> ConversationHandler:
    """Build the registration ConversationHandler."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("register", register_start),
            CallbackQueryHandler(register_start, pattern="^begin_register$"),
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            GENDER: [CallbackQueryHandler(register_gender, pattern="^gender_")],
            TEAM: [CallbackQueryHandler(register_team, pattern="^team_")],
        },
        fallbacks=[CommandHandler("cancel", register_cancel)],
    )
