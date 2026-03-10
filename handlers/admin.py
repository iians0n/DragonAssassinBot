"""Admin command handlers: /startgame, /endgame, /pausegame, /addplayer, /revive, /admin."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_PASSCODE
from services.game_manager import is_admin, start_game, end_game, toggle_pause, get_game_state, promote_to_admin
from services.registration import get_player, find_player_by_identifier, save_player, register_player
from services.leaderboard import get_individual_rankings
from utils.formatting import format_leaderboard, format_team_leaderboard, send_to_group
from utils.dm_only import dm_only

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


@dm_only
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


@dm_only
@admin_check
async def pausegame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pausegame — toggle pause."""
    game = toggle_pause()
    status = "⏸️ PAUSED" if game.status == "paused" else "▶️ RESUMED"
    await update.message.reply_text(
        f"🎮 Game {status}",
        parse_mode="HTML",
    )


@dm_only
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


@dm_only
@admin_check
async def revive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /revive <name or @username> — revive a player."""
    if not context.args:
        await update.message.reply_text("Usage: /revive <name or @username>")
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
                "• /revive — Revive players\n"
                "• /revertkill — Revert a kill (undo stats & points)\n"
                "• /assignroles — Assign random roles\n"
                "• /setteamgc — Set team group chat"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not DM new admin {user.id}: {e}")


@dm_only
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
    
    # Save topic/thread ID if used in a forum topic
    if update.message.message_thread_id:
        game.team_topic_ids[str(team)] = update.message.message_thread_id
    elif str(team) in getattr(game, 'team_topic_ids', {}):
        game.team_topic_ids.pop(str(team), None)
        
    save_game_state(game)

    from utils.formatting import team_label
    await update.message.reply_text(
        f"✅ This chat is now set as <b>{team_label(team)}</b>'s group chat.\n"
        f"Role announcements will be sent here.",
        parse_mode="HTML",
    )


@admin_check
async def setpoints_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setpoints <player> <amount> — set a player's points to an exact value."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /setpoints <name or @username> <amount>")
        return

    try:
        amount = int(context.args[-1])
    except ValueError:
        await update.message.reply_text("❌ Amount must be a number.")
        return

    identifier = " ".join(context.args[:-1])
    player = find_player_by_identifier(identifier)
    if not player:
        await update.message.reply_text(f"❌ Player '{identifier}' not found.")
        return

    old_points = player.points
    player.points = amount
    save_player(player)

    await update.message.reply_text(
        f"✅ <b>{player.name}</b> points: {old_points} → <b>{amount}</b>",
        parse_mode="HTML",
    )


@admin_check
async def addpoints_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /addpoints <player> <amount> — add/subtract points (supports negative)."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /addpoints <name or @username> <amount>\nUse negative for subtraction: /addpoints @alice -10")
        return

    try:
        amount = int(context.args[-1])
    except ValueError:
        await update.message.reply_text("❌ Amount must be a number.")
        return

    identifier = " ".join(context.args[:-1])
    player = find_player_by_identifier(identifier)
    if not player:
        await update.message.reply_text(f"❌ Player '{identifier}' not found.")
        return

    old_points = player.points
    player.points += amount
    save_player(player)

    sign = "+" if amount >= 0 else ""
    await update.message.reply_text(
        f"✅ <b>{player.name}</b> points: {old_points} → <b>{player.points}</b> ({sign}{amount})",
        parse_mode="HTML",
    )


@admin_check
async def setrole_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setrole <player> <role> — manually assign a role."""
    from config import ROLE_NORMAL, ROLE_NINJA, ROLE_SNIPER, ROLE_PRESIDENT

    valid_roles = {
        "normal": ROLE_NORMAL,
        "ninja": ROLE_NINJA,
        "sniper": ROLE_SNIPER,
        "president": ROLE_PRESIDENT,
    }

    if not context.args or len(context.args) < 2:
        roles_list = ", ".join(valid_roles.keys())
        await update.message.reply_text(f"Usage: /setrole <name or @username> <role>\nValid roles: {roles_list}")
        return

    role_input = context.args[-1].lower()
    if role_input not in valid_roles:
        roles_list = ", ".join(valid_roles.keys())
        await update.message.reply_text(f"❌ Invalid role. Valid roles: {roles_list}")
        return

    identifier = " ".join(context.args[:-1])
    player = find_player_by_identifier(identifier)
    if not player:
        await update.message.reply_text(f"❌ Player '{identifier}' not found.")
        return

    old_role = player.role
    player.role = valid_roles[role_input]

    # Reset president_used if assigning president
    if player.role == ROLE_PRESIDENT:
        player.president_used = False

    save_player(player)

    from services.roles import get_role_display
    await update.message.reply_text(
        f"✅ <b>{player.name}</b> role: {get_role_display(old_role)} → <b>{get_role_display(player.role)}</b>",
        parse_mode="HTML",
    )


@admin_check
async def viewroles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /viewroles — show all players and their roles (admin eyes only)."""
    from services.registration import get_team_players
    from services.roles import get_role_display
    from utils.formatting import team_label

    lines = ["🔍 <b>All Player Roles</b>", ""]

    for team in range(1, 5):
        players = get_team_players(team)
        if not players:
            continue

        lines.append(f"<b>{team_label(team)}</b>")
        for p in sorted(players, key=lambda x: x.role):
            lines.append(f"  {get_role_display(p.role)} — {p.name} ({p.points} pts)")
        lines.append("")

    if len(lines) <= 2:
        await update.message.reply_text("📊 No players registered yet.")
        return

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@admin_check
async def toggleteammode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /toggleteammode — toggle between auto and manual team assignment."""
    from services.game_manager import get_game_state, save_game_state
    game = get_game_state()
    
    if game.team_assignment_mode == "auto":
        game.team_assignment_mode = "manual"
    else:
        game.team_assignment_mode = "auto"
        
    save_game_state(game)
    
    await update.message.reply_text(
        f"✅ Team assignment mode is now set to <b>{game.team_assignment_mode.upper()}</b>.",
        parse_mode="HTML",
    )


@admin_check
async def setteam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setteam <team 1-4> <player1> [player2] ... — assign players to a team."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /setteam <team 1-4> <player1> [player2] ...\nExample: /setteam 2 @alice Bob")
        return

    try:
        team = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Team must be a number (1-4).")
        return

    if team not in (1, 2, 3, 4):
        await update.message.reply_text("❌ Team must be 1-4.")
        return

    from utils.formatting import team_label
    from services.registration import find_player_by_identifier, save_player
    team_name = team_label(team)
    
    identifiers = context.args[1:]
    success = []
    failed = []

    for identifier in identifiers:
        player = find_player_by_identifier(identifier)
        if player:
            player.team = team
            save_player(player)
            success.append(player.name)
        else:
            failed.append(identifier)

    msg = ""
    if success:
        msg += f"✅ Added to <b>{team_name}</b>:\n• " + "\n• ".join(success) + "\n\n"
    if failed:
        msg += f"❌ Not found:\n• " + "\n• ".join(failed)
        
    if not msg:
        msg = "No players processed."

    await update.message.reply_text(msg, parse_mode="HTML")


@dm_only
@admin_check
async def revertkill_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /revertkill <target> — show kills on a target for admin to revert."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from storage.json_store import store
    from datetime import datetime
    import pytz
    from config import TIMEZONE

    if not context.args:
        await update.message.reply_text("Usage: /revertkill <name or @username>")
        return

    identifier = " ".join(context.args)
    target = find_player_by_identifier(identifier)

    if not target:
        await update.message.reply_text(f"❌ Player '{identifier}' not found.")
        return

    # Find all kills where this player was the target
    kills = store.load_kill_log()
    target_kills = [k for k in kills if k.get("target_id") == target.user_id]

    if not target_kills:
        await update.message.reply_text(
            f"❌ No kills found on <b>{target.name}</b>.",
            parse_mode="HTML",
        )
        return

    # Sort newest first
    target_kills.sort(key=lambda k: k.get("timestamp", 0), reverse=True)

    tz = pytz.timezone(TIMEZONE)
    lines = [f"🔄 <b>Kills on {target.name}</b> — tap to revert:\n"]
    buttons = []

    for i, kill in enumerate(target_kills, 1):
        killer = get_player(kill.get("killer_id"))
        killer_name = killer.name if killer else f"ID:{kill.get('killer_id')}"
        kill_type = kill.get("kill_type", "normal")
        type_emoji = "🔇" if kill_type == "stealth" else "🏀"
        president_tag = " 👑" if kill.get("target_was_president") else ""

        # Format timestamp
        ts = kill.get("timestamp", 0)
        try:
            dt = datetime.fromtimestamp(ts, tz=tz)
            time_str = dt.strftime("%d %b, %I:%M %p")
        except Exception:
            time_str = "Unknown time"

        pts = kill.get("points_awarded", 0)
        lines.append(
            f"{i}. {type_emoji} <b>{killer_name}</b> → {target.name}{president_tag}\n"
            f"    {time_str} • {pts} pts"
        )

        kill_id = kill.get("id", "")
        buttons.append([InlineKeyboardButton(
            f"↩️ Revert #{i}: {killer_name} ({type_emoji})",
            callback_data=f"revert_kill:{kill_id}",
        )])

    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=markup,
    )


async def revertkill_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin tapping a revert button for a specific kill."""
    from services.game_manager import is_admin
    from services.combat import revert_kill
    from storage.json_store import store

    query = update.callback_query
    await query.answer()

    # Admin check
    if not is_admin(query.from_user.id):
        await query.answer("❌ Admins only.", show_alert=True)
        return

    kill_id = query.data.split(":", 1)[1]

    # Find the kill in the log
    kills = store.load_kill_log()
    kill_entry = None
    for k in kills:
        if k.get("id") == kill_id:
            kill_entry = k
            break

    if not kill_entry:
        await query.edit_message_text("❌ Kill not found — it may have already been reverted.")
        return

    # Get player names before reverting
    killer = get_player(kill_entry.get("killer_id"))
    target = get_player(kill_entry.get("target_id"))
    killer_name = killer.name if killer else "Unknown"
    target_name = target.name if target else "Unknown"
    kill_type = kill_entry.get("kill_type", "normal")
    type_emoji = "🔇" if kill_type == "stealth" else "🏀"
    pts = kill_entry.get("points_awarded", 0)
    was_president = kill_entry.get("target_was_president", False)

    # Perform the revert
    success, msg = revert_kill(kill_entry)

    if not success:
        await query.edit_message_text(f"❌ Failed to revert: {msg}")
        return

    # Build confirmation
    details = [
        f"✅ <b>Kill Reverted Successfully</b>\n",
        f"{type_emoji} <b>{killer_name}</b> → <b>{target_name}</b>",
        f"",
        f"📋 <b>Changes applied:</b>",
        f"• {target_name}: revived 💚, deaths -1",
        f"• {killer_name}: {kill_type} kills -1, points -{pts}",
    ]
    if was_president:
        details.append(f"• {target_name}: 👑 president role restored")

    await query.edit_message_text("\n".join(details), parse_mode="HTML")

    # Notify the revived target
    if target:
        try:
            await context.bot.send_message(
                chat_id=target.user_id,
                text="💚 A kill on you has been reverted by an admin! You're back in the game!",
            )
        except Exception as e:
            logger.warning(f"Could not notify revived player: {e}")

    # Notify the killer
    if killer:
        try:
            await context.bot.send_message(
                chat_id=killer.user_id,
                text=(
                    f"⚠️ Your {kill_type} kill on <b>{target_name}</b> has been reverted by an admin.\n"
                    f"Points adjusted: -{pts}"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Could not notify killer about revert: {e}")

