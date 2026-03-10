"""Message formatting templates and emoji helpers."""

from typing import List, Dict, Tuple


TEAM_EMOJIS = {0: "⚪️", 1: "🔴", 2: "🔵", 3: "🟢", 4: "🟡"}
TEAM_NAMES = {0: "Unassigned", 1: "Team Red", 2: "Team Blue", 3: "Team Green", 4: "Team Yellow"}


def team_label(team: int) -> str:
    """Get formatted team label with emoji."""
    return f"{TEAM_EMOJIS.get(team, '⚪')} {TEAM_NAMES.get(team, f'Team {team}')}"


def player_mention(username: str, name: str) -> str:
    """Format a player mention."""
    if username:
        return f"@{username}"
    return name


def format_player_card(player_data: dict) -> str:
    """Format a player's profile card."""
    p = player_data
    status_emoji = {"alive": "💚", "cooldown": "💀", "eliminated": "☠️"}.get(p["status"], "❓")
    kills_total = p["kills_normal"] + p["kills_stealth"]
    kda = kills_total / max(1, p["deaths"])

    lines = [
        f"👤 <b>{p['name']}</b>",
        f"{team_label(p['team'])}",
        f"Status: {status_emoji} {p['status'].upper()}",
    ]

    # Show role (only visible in private /profile)
    role = p.get('role', 'normal')
    if role != 'normal':
        from services.roles import get_role_display
        lines.append(f"Role: {get_role_display(role)}")

    lines.append("")
    lines.extend([
        f"⚔️ Kills: {kills_total} ({p['kills_normal']} normal, {p['kills_stealth']} stealth)",
        f"💀 Deaths: {p['deaths']}",
        f"📊 KDA: {kda:.1f}",
        f"🏆 Points: {p['points']}",
    ])

    # Show pending hidden bonus points (private only)
    bonus_pts = p.get("bonus_points", 0)
    if bonus_pts > 0:
        lines.append(f"🎁 Pending Bonus: +{bonus_pts} pts (revealed at day end)")

    # Streak info
    current_streak = p.get("current_streak", 0)
    best_streak = p.get("best_streak", 0)
    if best_streak > 0:
        streak_line = f"🔥 Streak: {current_streak} current"
        if best_streak > current_streak:
            streak_line += f" | {best_streak} best"
        lines.append(streak_line)

    # Achievement count
    achievements = p.get("achievements", [])
    if achievements:
        lines.append(f"🏅 Badges: {len(achievements)} unlocked")

    if p.get("cooldown_until", 0) > 0 and p["status"] == "cooldown":
        import time
        remaining = p["cooldown_until"] - time.time()
        if remaining > 0:
            from utils.time_utils import format_duration
            lines.append(f"⏳ Cooldown: {format_duration(remaining)} remaining")

    return "\n".join(lines)


def format_leaderboard(players: List[dict]) -> str:
    """Format the individual leaderboard."""
    if not players:
        return "📊 No players registered yet."

    # Sort by points descending, then by KDA
    sorted_players = sorted(
        players,
        key=lambda p: (p["points"], (p["kills_normal"] + p["kills_stealth"]) / max(1, p["deaths"])),
        reverse=True,
    )

    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    
    from datetime import datetime
    import pytz
    sgt = pytz.timezone("Asia/Singapore")
    now_str = datetime.now(sgt).strftime("%d %b %Y, %I:%M %p SGT")
    
    lines = ["🏆 <b>ASSASSINS LEADERBOARD</b> 🏆", f"🕐 <i>{now_str}</i>", "", "👤 <b>Individual Rankings:</b>"]

    for i, p in enumerate(sorted_players[:10]):
        kills_total = p["kills_normal"] + p["kills_stealth"]
        kda = kills_total / max(1, p["deaths"])
        prefix = medals.get(i, f"{i+1}.")
        team = team_label(p["team"])
        lines.append(
            f"{prefix} <b>{p['name']}</b> ({team}) — "
            f"{p['points']} pts | K:{kills_total} D:{p['deaths']} | KDA: {kda:.1f}"
        )

    return "\n".join(lines)


def format_team_leaderboard(players: List[dict]) -> str:
    """Format team rankings."""
    if not players:
        return "📊 No players registered yet."

    teams: dict[int, dict] = {}
    for p in players:
        t = p["team"]
        if t not in teams:
            teams[t] = {"kills": 0, "deaths": 0, "points": 0, "count": 0}
        kills_total = p["kills_normal"] + p["kills_stealth"]
        teams[t]["kills"] += kills_total
        teams[t]["deaths"] += p["deaths"]
        teams[t]["points"] += p["points"]
        teams[t]["count"] += 1

    sorted_teams = sorted(teams.items(), key=lambda x: x[1]["points"], reverse=True)

    lines = ["", "👥 <b>Team Rankings:</b>"]
    medals = {0: "🏅", 1: "🥈", 2: "🥉"}

    for i, (team_num, stats) in enumerate(sorted_teams):
        avg_kda = (stats["kills"] / max(1, stats["deaths"]))
        prefix = medals.get(i, f"{i+1}.")
        lines.append(
            f"{prefix} {team_label(team_num)} — "
            f"{stats['points']} pts | {stats['kills']}K {stats['deaths']}D | "
            f"Avg KDA: {avg_kda:.1f} | {stats['count']} players"
        )

    return "\n".join(lines)


def format_kill_announcement(killer: dict, target: dict, kill_type: str,
                             bounty_bonus: int = 0,
                             new_achievements: list = None) -> str:
    """Format kill announcement for group chat."""
    from models.achievement import STREAK_MILESTONES
    from config import POINTS_NORMAL_KILL, POINTS_STEALTH_KILL

    killer_name = player_mention(killer["username"], killer["name"])
    target_name = player_mention(target["username"], target["name"])

    if kill_type == "stealth":
        emoji = "🗡️"
        type_text = "stealth-eliminated"
        pts = f"+{POINTS_STEALTH_KILL} points"
    else:
        emoji = "☠️"
        type_text = "eliminated"
        pts = f"+{POINTS_NORMAL_KILL} points"

    msg = f"{emoji} <b>{killer_name}</b> {type_text} <b>{target_name}</b>! ({pts})"

    if bounty_bonus > 0:
        msg += f"\n💰 Bounty claimed! +{bounty_bonus} bonus points!"

    # Streak announcement
    streak = killer.get("current_streak", 0)
    if streak >= 3:
        # Find the highest matching milestone
        best_milestone = None
        for threshold in sorted(STREAK_MILESTONES.keys(), reverse=True):
            if streak >= threshold:
                best_milestone = STREAK_MILESTONES[threshold]
                break
        if best_milestone:
            s_emoji, s_text = best_milestone
            msg += f"\n{s_emoji} <b>{killer_name}</b> is on a <b>{streak} KILL STREAK — {s_text}!</b>"

    # Achievement announcements
    if new_achievements:
        for a_emoji, a_name, a_desc in new_achievements:
            msg += f"\n🏅 <b>{killer_name}</b> unlocked: {a_emoji} <b>{a_name}</b> — {a_desc}"

    return msg


def format_achievements(achievements: list) -> str:
    """Format a player's achievements list for /achievements command."""
    from models.achievement import ACHIEVEMENTS

    if not achievements:
        return "🏅 No achievements unlocked yet. Get out there and start hunting!"

    lines = ["🏅 <b>ACHIEVEMENTS</b> 🏅", ""]
    for a_id in achievements:
        if a_id in ACHIEVEMENTS:
            emoji, name, desc = ACHIEVEMENTS[a_id]
            lines.append(f"{emoji} <b>{name}</b> — {desc}")

    lines.append(f"\n<i>{len(achievements)}/{len(ACHIEVEMENTS)} unlocked</i>")
    return "\n".join(lines)


def format_death_dm(killer: dict, kill_type: str, cooldown_hours: float) -> str:
    """Format death notification DM to target."""
    killer_name = player_mention(killer["username"], killer["name"])

    if kill_type == "stealth":
        return (
            f"🗡️ You were stealth-killed by <b>{killer_name}</b> (post-it)!\n"
            f"⏳ Cooldown: {cooldown_hours:.0f} hour(s). You'll respawn automatically."
        )
    return (
        f"☠️ You were killed by <b>{killer_name}</b> (ball throw)!\n"
        f"⏳ Cooldown: {cooldown_hours:.0f} hour(s). You'll respawn automatically."
    )


async def send_to_group(bot, text: str, game_state=None, parse_mode: str = "HTML", photo_file_id: str = None):
    """Send a message to the group chat, respecting forum topic if set."""
    if game_state is None:
        from services.game_manager import get_game_state
        game_state = get_game_state()

    group_id = game_state.group_chat_id
    if not group_id:
        return

    kwargs = {
        "chat_id": group_id,
        "parse_mode": parse_mode,
    }
    topic_id = getattr(game_state, "group_topic_id", 0)
    if topic_id:
        kwargs["message_thread_id"] = topic_id

    if photo_file_id:
        kwargs["caption"] = text
        kwargs["photo"] = photo_file_id
        await bot.send_photo(**kwargs)
    else:
        kwargs["text"] = text
        await bot.send_message(**kwargs)

