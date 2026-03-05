# 🎯 DragonAssassinBot

A Telegram bot for running a week-long campus Assassins game with real-time kill tracking, hidden roles, KDA leaderboards, bounties, kill streaks, and achievements.

**Platform:** Telegram  
**Target Users:** NUS college activity participants (4 teams, ~20–50 players)

---

## 🎮 Game Rules

- **4 teams** compete over 1 week
- 🏓 **Ball kill** (`/ball`): +10 points, target cooldown 2 hours
- 🗡️ **Post-it kill** (`/postit`): +5 points, same gender only, 1 hour cooldown
- 🎯 **Max 2 kills per day**
- 🎭 **Hidden roles** — each team gets 1 Ninja, 1 Sniper, 1 President (randomly assigned daily)
- **Game hours:** 9 AM – 11 PM SGT
- **Most points wins!**

### 🎭 Roles (Hidden)

Roles are secret — only your team's GC knows. Bonus points are applied at **end of day** so other teams can't deduce roles from the leaderboard.

| Role | Bonus |
|---|---|
| 🥷 Ninja | x2 points on post-it kills (+5 bonus) |
| 🎯 Sniper | x2 points on ball kills (+10 bonus) |
| 👑 President | Worth 50 pts to killer. Becomes Normal after dying once |
| 👤 Normal | No special bonus |

---

## 📋 Commands

### Player Commands

| Command | Description |
|---|---|
| `/start` | Show game info and register button |
| `/register` | Sign up — enter name, gender, team |
| `/profile` | View your stats, role, streak, and badges |
| `/ball <name>` | Report a ball kill (ping pong throw) |
| `/postit <name>` | Report a post-it kill (requires photo proof) |
| `/leaderboard` | View top 10 players + team rankings |
| `/team` | View your team's stats and members |
| `/stats <name>` | View detailed stats for any player |
| `/bounty <name> <pts>` | Place a bounty on a player (costs your points) |
| `/bounties` | View all active bounties |
| `/countdown` | Time remaining in the game |
| `/achievements` | View your unlocked badges |

### Admin Commands

| Command | Description |
|---|---|
| `/admin <passcode>` | Self-register as admin with passcode |
| `/startgame` | Begin the game (sets group chat + 7-day timer) |
| `/endgame` | End the game and post final results |
| `/pausegame` | Toggle pause/resume |
| `/assignroles` | Randomly assign roles to all teams |
| `/setteamgc <1-4>` | Set current chat as a team's group chat |
| `/addplayer <@user>` | Manually add a player |
| `/resetkill <name>` | Revive a player (clear cooldown) |
| `/resolvekill <id> approve/reject` | Resolve a disputed kill |

---

## ⏰ Daily Schedule (SGT)

| Time | Event |
|---|---|
| 9:00 AM | 🎯 Game day starts |
| 9 AM – 11 PM | Kills award base points (10/5). Role bonuses accumulate silently |
| Every 3 hours | 📊 Leaderboard posted to group |
| 10:00 PM | ⚠️ "1 hour warning" |
| 11:00 PM | 🌙 Day ends → bonuses applied → roles reshuffled → new roles sent to team GCs |

---

## 🔥 Kill Streaks

Consecutive kills without dying trigger group announcements:

| Streak | Announcement |
|---|---|
| 3 | 🔥 TRIPLE KILL |
| 5 | 💥 PENTA KILL |
| 7 | ⚡ DOMINATING |
| 10 | ☄️ UNSTOPPABLE |
| 15 | 👑 GODLIKE |

---

## 🏅 Achievements

| Badge | Name | How to Unlock |
|---|---|---|
| 🩸 | First Blood | Get your first kill |
| 💀 | Serial Killer | 10 total kills |
| 👑 | Legend | 20 total kills |
| 🔥 | Triple Kill | Reach a 3 kill streak |
| 💥 | Penta Kill | Reach a 5 kill streak |
| ⚡ | Unstoppable | Reach a 10 kill streak |
| 🥷 | Shadow | 3 stealth kills |
| 🗡️ | Silent Assassin | 5 stealth kills |
| 💰 | Bounty Hunter | Claim your first bounty |
| 🛡️ | Survivor | Die 5 times with positive KDA |
| 🔄 | Comeback Kid | Kill within 10 min of respawning |

---

## 🚀 Setup

```bash
# Clone
git clone https://github.com/iians0n/DragonAssassinBot.git
cd DragonAssassinBot

# Install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your BOT_TOKEN and ADMIN_IDS

# Run
python bot.py
```

---

## 🛠️ Tech Stack

- **Language:** Python 3.9+
- **Framework:** [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v20+
- **Storage:** JSON files with in-memory caching
- **Scheduling:** APScheduler (cooldowns, bounty expiry, daily notifications)