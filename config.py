"""Configuration constants for the Assassins Game Tracker Bot."""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
ADMIN_PASSCODE = os.getenv("ADMIN_PASSCODE", "assassins2026")

# Game rules
GAME_DURATION_DAYS = 7
DAY_START_HOUR = 9       # 9 AM
DAY_END_HOUR = 23        # 11 PM
TIMEZONE = "Asia/Singapore"

# Cooldowns (seconds)
COOLDOWN_BALL = 7200     # 2 hours
COOLDOWN_STEALTH = 3600  # 1 hour

# Bounty
BOUNTY_DURATION = 86400  # 24 hours
MIN_BOUNTY = 1

# Kill dispute window (seconds)
KILL_DISPUTE_WINDOW = 900  # 15 minutes

# Rate limiting
MAX_COMMANDS_PER_MINUTE = 10

# Points
POINTS_NORMAL_KILL = 1
POINTS_STEALTH_KILL = 2

# Data paths
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
