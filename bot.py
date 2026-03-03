"""Assassins Game Tracker Bot — Entry point."""

import logging
from datetime import time as dt_time

import pytz
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from config import BOT_TOKEN, TIMEZONE
from handlers.start import start_command, profile_command, get_registration_handler
from handlers.kill import kill_command, stealthkill_command, stealthkill_photo_command
from handlers.leaderboard import leaderboard_command, team_command, stats_command
from handlers.bounty import bounty_command, bounties_command
from handlers.countdown import countdown_command
from handlers.achievements import achievements_command
from handlers.dispute import kill_callback_handler, resolvekill_command
from handlers.admin import (
    startgame_command,
    endgame_command,
    pausegame_command,
    addplayer_command,
    resetkill_command,
    admin_command,
)
from services.scheduler import (
    cooldown_check_job,
    bounty_expiry_job,
    pending_kill_expiry_job,
    leaderboard_update_job,
    game_day_start_job,
    game_day_warning_job,
    game_day_end_job,
)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Suppress noisy httpx logs
logging.getLogger("httpx").setLevel(logging.WARNING)


def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set! Copy .env.example to .env and add your token.")
        return

    # Build application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # --- Register handlers ---

    # Registration conversation (must be added before simple command handlers)
    app.add_handler(get_registration_handler())

    # Simple commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("myprofile", profile_command))

    # Kill commands
    app.add_handler(CommandHandler("kill", kill_command))
    app.add_handler(CommandHandler("stealthkill", stealthkill_command))
    # Also handle photos with /stealthkill as caption
    app.add_handler(MessageHandler(
        filters.PHOTO & filters.CaptionRegex(r"^/stealthkill"),
        stealthkill_photo_command,
    ))

    # Leaderboard
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("team", team_command))
    app.add_handler(CommandHandler("stats", stats_command))

    # Bounty
    app.add_handler(CommandHandler("bounty", bounty_command))
    app.add_handler(CommandHandler("bounties", bounties_command))

    # Countdown
    app.add_handler(CommandHandler("countdown", countdown_command))

    # Achievements
    app.add_handler(CommandHandler("achievements", achievements_command))
    app.add_handler(CommandHandler("badges", achievements_command))

    # Admin
    app.add_handler(CommandHandler("startgame", startgame_command))
    app.add_handler(CommandHandler("endgame", endgame_command))
    app.add_handler(CommandHandler("pausegame", pausegame_command))
    app.add_handler(CommandHandler("addplayer", addplayer_command))
    app.add_handler(CommandHandler("resetkill", resetkill_command))
    app.add_handler(CommandHandler("resolvekill", resolvekill_command))
    app.add_handler(CommandHandler("admin", admin_command))

    # Kill dispute callbacks (Accept / Dispute inline buttons)
    app.add_handler(CallbackQueryHandler(kill_callback_handler, pattern=r"^kill_(accept|dispute):"))

    # --- Schedule background jobs ---
    job_queue = app.job_queue
    tz = pytz.timezone(TIMEZONE)

    # Cooldown check — every 60 seconds
    job_queue.run_repeating(cooldown_check_job, interval=60, first=10)

    # Bounty expiry check — every 5 minutes
    job_queue.run_repeating(bounty_expiry_job, interval=300, first=30)

    # Pending kill auto-confirm — every 60 seconds
    job_queue.run_repeating(pending_kill_expiry_job, interval=60, first=15)

    # Leaderboard update — every 30 minutes
    job_queue.run_repeating(leaderboard_update_job, interval=1800, first=60)

    # Daily notifications (SGT)
    job_queue.run_daily(game_day_start_job, time=dt_time(hour=9, minute=0, tzinfo=tz))
    job_queue.run_daily(game_day_warning_job, time=dt_time(hour=22, minute=0, tzinfo=tz))
    job_queue.run_daily(game_day_end_job, time=dt_time(hour=23, minute=0, tzinfo=tz))

    # --- Start polling ---
    logger.info("🎯 Assassins Game Tracker Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
