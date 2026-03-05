"""/countdown command handler."""

import time
from telegram import Update
from telegram.ext import ContextTypes

from services.game_manager import get_game_state
from utils.time_utils import get_sg_now, format_countdown, seconds_until_hour, is_game_hours
from config import DAY_START_HOUR, DAY_END_HOUR, GAME_DURATION_DAYS
from utils.dm_only import dm_only


@dm_only
async def countdown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /countdown — show time remaining."""
    game = get_game_state()

    if game.status == "pending":
        await update.message.reply_text("⏳ The game hasn't started yet. Stay tuned!")
        return

    if game.status == "completed":
        await update.message.reply_text("🏁 The game is over! Check /leaderboard for final results.")
        return

    if game.status == "paused":
        await update.message.reply_text("⏸️ The game is currently paused.")
        return

    now = time.time()
    sg_now = get_sg_now()

    # Calculate game day number
    elapsed_days = int((now - game.start_time) / 86400) + 1
    total_days = GAME_DURATION_DAYS

    # Time calculations
    total_remaining = max(0, game.end_time - now)

    if is_game_hours():
        # During game hours
        secs_until_end = seconds_until_hour(DAY_END_HOUR)
        secs_until_start = seconds_until_hour(DAY_START_HOUR)
        status_line = f"🟢 <b>GAME IS LIVE</b>"
        time_line = f"🎯 Game hours END in: <b>{format_countdown(secs_until_end)}</b>"
    else:
        # Outside game hours
        secs_until_start = seconds_until_hour(DAY_START_HOUR)
        secs_until_end = seconds_until_hour(DAY_END_HOUR)
        status_line = f"🔴 <b>GAME HOURS CLOSED</b>"
        time_line = f"🌅 Next game day starts in: <b>{format_countdown(secs_until_start)}</b>"

    lines = [
        "⏰ <b>GAME COUNTDOWN</b> ⏰",
        "",
        status_line,
        "",
        f"📅 Day {min(elapsed_days, total_days)} of {total_days}",
        time_line,
        f"📊 Total time remaining: <b>{format_countdown(total_remaining)}</b>",
    ]

    # Current time
    lines.append(f"\n🕐 Current time: {sg_now.strftime('%I:%M %p SGT')}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
