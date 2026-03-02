"""Message formatting templates and emoji helpers."""

from typing import List, Dict


TEAM_EMOJIS = {1: "🔴", 2: "🔵", 3: "🟢", 4: "🟡"}
TEAM_NAMES = {1: "Team Red", 2: "Team Blue", 3: "Team Green", 4: "Team Yellow"}


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
        "",
        f"⚔️ Kills: {kills_total} ({p['kills_normal']} normal, {p['kills_stealth']} stealth)",
        f"💀 Deaths: {p['deaths']}",
        f"📊 KDA: {kda:.1f}",
        f"🏆 Points: {p['points']}",
    ]

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


def format_kill_announcement(killer: dict, target: dict, kill_type: str, bounty_bonus: int = 0) -> str:
    """Format kill announcement for group chat."""
    killer_name = player_mention(killer["username"], killer["name"])
    target_name = player_mention(target["username"], target["name"])

    if kill_type == "stealth":
        emoji = "🗡️"
        type_text = "stealth-eliminated"
        pts = "+2 points"
    else:
        emoji = "☠️"
        type_text = "eliminated"
        pts = "+1 point"

    msg = f"{emoji} <b>{killer_name}</b> {type_text} <b>{target_name}</b>! ({pts})"

    if bounty_bonus > 0:
        msg += f"\n💰 Bounty claimed! +{bounty_bonus} bonus points!"

    return msg


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


async def send_to_group(bot, text: str, game_state=None, parse_mode: str = "HTML"):
    """Send a message to the group chat, respecting forum topic if set."""
    if game_state is None:
        from services.game_manager import get_game_state
        game_state = get_game_state()

    group_id = game_state.group_chat_id
    if not group_id:
        return

    kwargs = {
        "chat_id": group_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    topic_id = getattr(game_state, "group_topic_id", 0)
    if topic_id:
        kwargs["message_thread_id"] = topic_id

    await bot.send_message(**kwargs)

