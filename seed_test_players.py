"""Seed test players into the game for testing kill streaks & achievements."""

import json
import os
import time

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PLAYERS_FILE = os.path.join(DATA_DIR, "players.json")

# Load existing players
with open(PLAYERS_FILE, "r") as f:
    players = json.load(f)

# Test players on different teams (teams 2, 3, 4) so you can kill them
test_players = [
    {"user_id": 100001, "username": "target_alpha", "name": "Alpha", "gender": "M", "team": 2},
    {"user_id": 100002, "username": "target_bravo", "name": "Bravo", "gender": "M", "team": 3},
    {"user_id": 100003, "username": "target_charlie", "name": "Charlie", "gender": "M", "team": 4},
    {"user_id": 100004, "username": "target_delta", "name": "Delta", "gender": "M", "team": 2},
    {"user_id": 100005, "username": "target_echo", "name": "Echo", "gender": "M", "team": 3},
    {"user_id": 100006, "username": "target_foxtrot", "name": "Foxtrot", "gender": "M", "team": 4},
    {"user_id": 100007, "username": "target_golf", "name": "Golf", "gender": "M", "team": 2},
    {"user_id": 100008, "username": "target_hotel", "name": "Hotel", "gender": "F", "team": 3},
    {"user_id": 100009, "username": "target_india", "name": "India", "gender": "F", "team": 4},
    {"user_id": 100010, "username": "target_juliet", "name": "Juliet", "gender": "F", "team": 2},
]

for tp in test_players:
    uid = str(tp["user_id"])
    if uid not in players:
        players[uid] = {
            **tp,
            "status": "alive",
            "cooldown_until": 0.0,
            "kills_normal": 0,
            "kills_stealth": 0,
            "deaths": 0,
            "points": 0,
            "bounties_placed": 0,
            "bounties_collected": 0,
            "current_streak": 0,
            "best_streak": 0,
            "achievements": [],
            "registered_at": time.time(),
        }
        print(f"  ✅ Added {tp['name']} (@{tp['username']}) — Team {tp['team']}")
    else:
        print(f"  ⏭️  {tp['name']} already exists, skipping")

with open(PLAYERS_FILE, "w") as f:
    json.dump(players, f, indent=2, ensure_ascii=False)

print(f"\n🎯 Done! {len(test_players)} test players ready.")
print(f"\nYou can now use in Telegram:")
print(f"  /kill Alpha")
print(f"  /kill Bravo")
print(f"  /kill Charlie")
print(f"  ... etc (kill 3+ to see streak announcements!)")
print(f"\n⚠️  Note: The bot can't DM fake players, so you'll see warnings in logs — that's normal.")
