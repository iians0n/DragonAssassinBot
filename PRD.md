Assassins Game Tracker Bot - PRD

1. Project Overview

Project Name: Assassins Tracker Bot
Platform: Telegram
Core Functionality: Real-time kill/death tracking, KDA leaderboards, bounty system, and game state management for a week-long campus Assassins game
Target Users: NUS college activity participants (4 teams, ~20-50 players)


2. Game Rules (As Given)

• 4 teams — Bot assigns/registers teams
• Normal kill: ping pong ball throw — User reports kill with timestamp + witness
• Stealth kill: post-it + photo — User uploads photo as proof
• Hit by ball = dead 2 hours — Bot tracks "cooldown" state
• Day: 9am - 11pm — Bot auto-enables/disables kills based on time
• Duration: 1 week — Game start/end timestamps
• Win: most kills/points — Leaderboard ranks by points

3. Core Features

3.1 Player & Team Registration

• /start — Shows game info + register button
• /register — Collect: name, telegram username, gender (M/F), team choice (or auto-assign)
• /myprofile — View own stats
• Admin can: add/remove players, assign teams, reset game
3.2 Kill Reporting System

Normal Kill (Ball): /kill @target [witness]

• Bot verifies: target is alive, killer is alive, time is within game hours (9am-11pm)
• Target enters 2-hour cooldown (marked as "dead" but can be revived)
• Killer gains +1 kill, +1 point
Stealth Kill (Post-it + Photo): /stealthkill @target [photo]

• Upload photo as proof
• Bot verifies: target is alive, gender match (killer.gender == target.gender), time within game hours
• Stealth kills worth +2 points (higher risk/reward)
• Target enters 1-hour cooldown (softer penalty for being stealth-killed)
Kill Confirmation:

• Target receives DM: "You were killed by @killer! [type]. Cooldown: X hours."
• Attack message posted to group: "☠️ @killer eliminated @target!"
3.3 Death & Cooldown Tracking

• Bot tracks alive / cooldown / dead states
• During cooldown (2hr for ball, 1hr for stealth):  • Cannot kill others
  • Can still be killed (counts as "vulnerable")

• After cooldown: full status restored
3.4 Live KDA Leaderboard

Individual Stats:

• Kills (K)
• Deaths (D)
• KDA Ratio: K / max(1, D)
• Points: K + 2×StealthKills
Team Stats:

• Total kills per team
• Total deaths caused
• Team KDA average
• Team rank
Commands:

• /leaderboard — Show top 10 individual + team rankings
• /team — Show your team's stats
• /stats @username — Detailed stats for a player
Auto-post: Live leaderboard update to group after each kill

3.5 Countdown System

• /countdown — Shows days remaining, hours until game day ends (11pm), next day starts (9am)
• Daily reminder: "🎯 Game day ends in X hours!"
• Admin controls: /startgame / /endgame / /pausegame
3.6 Bounty System

Place Bounty: /bounty @target [points]

• Any player can put a bounty on any other player (from their own points)
• Minimum bounty: 1 point
• Bounty lasts 24 hours or until claimed
Claim Bounty:

• When a bounty-hunted target is killed: Killer gains kill points + bounty points
• Bounty creator gets nothing (it's a "fee" to hire a hit)
• If bounty expires: points returned to creator
Bounty Board: /bounties — List all active bounties (anonymized target)


4. Bot Commands Summary
| Command               | Who   | Description           |
| --------------------- | ----- | --------------------- |
| /start                | All   | Game intro + register |
| /register             | All   | Sign up               |
| /profile              | All   | View your stats       |
| /kill @target         | All   | Report normal kill    |
| /stealthkill @target  | All   | Report stealth kill   |
| /leaderboard          | All   | View rankings         |
| /team                 | All   | View team stats       |
| /stats @user          | All   | View someone's stats  |
| /bounty @target [pts] | All   | Place bounty          |
| /bounties             | All   | View active bounties  |
| /countdown            | All   | Time remaining        |
| /startgame            | Admin | Begin game            |
| /endgame              | Admin | End game              |
| /pausegame            | Admin | Pause                 |
| /addplayer @user      | Admin | Manual add            |
| /resetkill @user      | Admin | Revive manually       |
5. Data Model

Player: user_id, username, name, gender (M/F), team (1-4), status (alive/cooldown/eliminated), cooldown_until, kills_normal, kills_stealth, deaths, points, bounties_placed, bounties_collected

Bounty: id, creator_id, target_id, points, created_at, expires_at, claimed

Game: status (pending/active/paused/completed), start_time, end_time, day_start_hour (9), day_end_hour (23), cooldown_ball_ms (7200000), cooldown_stealth_ms (3600000)


6. User Flows

Registration: /start → enter name, gender, team pref → confirmed

Kill: Killer does /kill @target → Bot validates (alive? within 9am-11pm? not in cooldown?) → Valid: target cooldown 2hr, killer +1 point, announce in group. Invalid: error message.

Bounty: /bounty @target 5 → placed (24hr expiry) → If someone kills target → they get kill points + bounty points


7. Non-Functional Requirements

• Response time: < 1 second
• Photo storage: Keep 7 days, then auto-delete
• Spam protection: Rate limit (max 10/min per user)
• Admin override for disputes
• Persistence: SQLite or JSON file

8. Milestones

• M1: Player registration + team assignment
• M2: Kill/death reporting + cooldown logic
• M3: Leaderboard + auto-post to group
• M4: Countdown timer + daily start/stop
• M5: Bounty system
• M6: Admin panel + dispute handling
• M7: Testing + deployment

9. Tech Stack

• Language: Python (aiogram) or Node.js (telegraf)
• Hosting: Railway / Render / Cloudflare Workers (free tier)
• Database: SQLite or Supabase
• Storage: Telegram file storage for photos

10. Why This Bot

• Real-time, no manual tracking
• Transparent scores prevent disputes
• Adds game depth (bounties, stealth bonus)
• Works entirely in Telegram — no extra app needed
• Automated cooldown + game hour enforcement