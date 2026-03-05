"""Admin command handlers: /startgame, /endgame, /pausegame, /addplayer, /resetkill, /admin."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_PASSCODE
from services.game_manager import is_admin, start_game, end_game, toggle_pause, get_game_state, promote_to_admin
from services.registration import get_player, find_player_by_identifier, save_player, register_player
from services.leaderboard import get_individual_rankings
from utils.formatting import format_leaderboard, format_team_leaderboard, send_to_group

logger = logging.getLogger(__name__)


def admin_check(func):
    """Decorator to check admin privileges."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is for admins only.")
            return
        return await func(update, context)
    return wrapper


@admin_check
async def startgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /startgame — begin the game."""
    game = get_game_state()

    if game.is_active():
        await update.message.reply_text("⚠️ Game is already active!")
        return

    game = start_game()

    # Update group chat ID if issued in a group
    if update.effective_chat.type in ("group", "supergroup"):
        from services.game_manager import save_game_state
        game.group_chat_id = update.effective_chat.id
        # Save topic/thread ID if used in a forum topic
        if update.message.message_thread_id:
            game.group_topic_id = update.message.message_thread_id
        else:
            game.group_topic_id = 0
        save_game_state(game)

    await update.message.reply_text(
        "🎮 <b>THE GAME HAS BEGUN!</b> 🎮\n\n"
        "⏰ Duration: 7 days\n"
        "🕘 Game hours: 9 AM – 11 PM SGT\n\n"
        "Good luck, assassins! 🎯",
        parse_mode="HTML",
    )

    # Also post to group if we have a group ID
    group_id = game.group_chat_id
    if group_id and update.effective_chat.id != group_id:
        try:
            await send_to_group(
                context.bot,
                "🎮 <b>THE GAME HAS BEGUN!</b> 🎮\n\n"
                "⏰ Duration: 7 days\n"
                "🕘 Game hours: 9 AM – 11 PM SGT\n\n"
                "Good luck, assassins! 🎯",
                game,
            )
        except Exception as e:
            logger.warning(f"Could not post to group: {e}")


@admin_check
async def endgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /endgame — end the game and post final results."""
    game = end_game()

    # Generate final leaderboard
    rankings = get_individual_rankings()
    lb_text = format_leaderboard(rankings)
    team_text = format_team_leaderboard(rankings)

    final_msg = (
        "🏁 <b>GAME OVER!</b> 🏁\n\n"
        f"{lb_text}\n{team_text}\n\n"
        "Thanks for playing, assassins! 🎉"
    )

    await update.message.reply_text(final_msg, parse_mode="HTML")

    # Post to group
    group_id = game.group_chat_id
    if group_id and update.effective_chat.id != group_id:
        try:
            await send_to_group(context.bot, final_msg, game)
        except Exception as e:
            logger.warning(f"Could not post final results to group: {e}")


@admin_check
async def pausegame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pausegame — toggle pause."""
    game = toggle_pause()
    status = "⏸️ PAUSED" if game.status == "paused" else "▶️ RESUMED"
    await update.message.reply_text(
        f"🎮 Game {status}",
        parse_mode="HTML",
    )


@admin_check
async def addplayer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /addplayer @username — manually register a player."""
    if not context.args:
        await update.message.reply_text("Usage: /addplayer @username [name] [M/F] [team 1-4]")
        return

    username = context.args[0].lstrip("@")

    # Check if already registered
    existing = find_player_by_identifier(username)
    if existing:
        await update.message.reply_text(f"⚠️ {username} is already registered.")
        return

    # Parse optional args
    name = context.args[1] if len(context.args) > 1 else username
    gender = context.args[2].upper() if len(context.args) > 2 else "M"
    team = int(context.args[3]) if len(context.args) > 3 else 0  # 0 = auto-balance

    if gender not in ("M", "F"):
        gender = "M"
    if team not in (0, 1, 2, 3, 4):
        team = 0

    await update.message.reply_text(
        f"⚠️ Note: Admin add requires the player's Telegram user ID.\n"
        f"Ask @{username} to send /register to the bot directly.\n\n"
        f"Alternatively, they can message the bot with /start."
    )


@admin_check
async def resetkill_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /resetkill <name or @username> — revive a player."""
    if not context.args:
        await update.message.reply_text("Usage: /resetkill <name or @username>")
        return

    identifier = " ".join(context.args)
    player = find_player_by_identifier(identifier)

    if not player:
        await update.message.reply_text(f"❌ Player '{identifier}' not found.")
        return

    player.status = "alive"
    player.cooldown_until = 0.0
    save_player(player)

    await update.message.reply_text(
        f"✅ <b>{player.name}</b> (@{player.username}) has been revived! 💚",
        parse_mode="HTML",
    )

    # Notify the player
    try:
        await context.bot.send_message(
            chat_id=player.user_id,
            text="💚 You've been revived by an admin! You're back in the game!",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not notify revived player: {e}")


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin <passcode> — self-register as admin with passcode."""
    user = update.effective_user

    # Try to delete the message containing the passcode (for security)
    try:
        await update.message.delete()
    except Exception:
        pass  # Bot may not have delete permissions in some chats

    # Check if already admin
    if is_admin(user.id):
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text="✅ You're already an admin!",
            )
        except Exception:
            pass
        return

    # Check passcode
    if not context.args:
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text="Usage: /admin <passcode>\n\n"
                     "⚠️ Send this in a private chat with the bot for security!",
            )
        except Exception:
            pass
        return

    passcode = " ".join(context.args)
    if passcode != ADMIN_PASSCODE:
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text="❌ Invalid passcode.",
            )
        except Exception:
            pass
        return

    # Promote to admin
    promote_to_admin(user.id)

    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=(
                "🔑 <b>Admin access granted!</b>\n\n"
                "You now have access to:\n"
                "• /startgame — Begin the game\n"
                "• /endgame — End the game\n"
                "• /pausegame — Pause/resume\n"
                "• /addplayer — Add players\n"
                "• /resetkill — Revive players\n"
                "• /assignroles — Assign random roles\n"
                "• /setteamgc — Set team group chat"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not DM new admin {user.id}: {e}")


@admin_check
async def assignroles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /assignroles — randomly assign roles to all teams."""
    from services.roles import assign_all_roles, send_roles_to_team_gc

    result = assign_all_roles()

    game = get_game_state()

    lines = ["🎭 <b>Roles assigned!</b>\n"]
    for team, players in result.items():
        team_line = f"Team {team}: "
        role_parts = []
        for p in players:
            from services.roles import get_role_display
            role_parts.append(f"{p.name} ({get_role_display(p.role)})")
        team_line += ", ".join(role_parts) if role_parts else "No players"
        lines.append(team_line)

    # Reply to admin with full overview
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    # Send roles to each team's GC
    for team, players in result.items():
        await send_roles_to_team_gc(context.bot, team, players, game)

    await update.message.reply_text("✅ Role announcements sent to team group chats.")


@admin_check
async def setteamgc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setteamgc <team> — set current chat as a team's GC."""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Usage: /setteamgc <team number 1-4>")
        return

    try:
        team = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Team must be a number (1-4).")
        return

    if team not in (1, 2, 3, 4):
        await update.message.reply_text("❌ Team must be 1-4.")
        return

    chat_id = update.effective_chat.id

    from services.game_manager import save_game_state
    game = get_game_state()
    game.team_chat_ids[str(team)] = chat_id
    save_game_state(game)

    from utils.formatting import team_label
    await update.message.reply_text(
        f"✅ This chat is now set as <b>{team_label(team)}</b>'s group chat.\n"
        f"Role announcements will be sent here.",
        parse_mode="HTML",
    )

