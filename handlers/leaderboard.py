"""/leaderboard, /team, /stats command handlers."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from services.registration import get_player, find_player_by_identifier
from services.leaderboard import get_individual_rankings, get_player_stats
from utils.formatting import (
    format_leaderboard,
    format_team_leaderboard,
    format_player_card,
    team_label,
)
from utils.dm_only import dm_only

logger = logging.getLogger(__name__)


@dm_only
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /leaderboard — show top 10 + team rankings."""
    rankings = get_individual_rankings()
    if not rankings:
        await update.message.reply_text("📊 No players registered yet. Nothing to show!")
        return

    lb_text = format_leaderboard(rankings)
    team_text = format_team_leaderboard(rankings)
    await update.message.reply_text(
        f"{lb_text}\n{team_text}",
        parse_mode="HTML",
    )


@dm_only
async def team_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /team — show your team's stats."""
    player = get_player(update.effective_user.id)
    if not player:
        await update.message.reply_text("❌ You're not registered. Use /register first.")
        return

    from services.registration import get_team_players
    teammates = get_team_players(player.team)

    total_kills = sum(p.kills_total for p in teammates)
    total_deaths = sum(p.deaths for p in teammates)
    total_points = sum(p.points for p in teammates)
    avg_kda = total_kills / max(1, total_deaths)

    lines = [
        f"👥 <b>{team_label(player.team)}</b>",
        f"Players: {len(teammates)}",
        "",
        f"⚔️ Total Kills: {total_kills}",
        f"💀 Total Deaths: {total_deaths}",
        f"📊 Avg KDA: {avg_kda:.1f}",
        f"🏆 Total Points: {total_points}",
        "",
        "<b>Members:</b>",
    ]

    # Sort teammates by points
    sorted_mates = sorted(teammates, key=lambda p: p.points, reverse=True)
    for p in sorted_mates:
        status_emoji = {"alive": "💚", "cooldown": "💀", "eliminated": "☠️"}.get(p.status, "❓")
        lines.append(f"  {status_emoji} {p.name} — {p.points} pts | K:{p.kills_total} D:{p.deaths}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@dm_only
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats @username — detailed stats for a player."""
    if not context.args:
        # Show own stats
        player = get_player(update.effective_user.id)
        if not player:
            await update.message.reply_text("❌ You're not registered. Use /register first.")
            return
        await update.message.reply_text(
            format_player_card(player.to_dict()),
            parse_mode="HTML",
        )
        return

    identifier = " ".join(context.args)
    target = find_player_by_identifier(identifier)
    if not target:
        await update.message.reply_text(f"❌ Player '{identifier}' not found.")
        return

    stats = get_player_stats(target.user_id)
    if not stats:
        await update.message.reply_text(f"❌ Could not load stats for '{identifier}'.")
        return

    await update.message.reply_text(
        format_player_card(stats),
        parse_mode="HTML",
    )
