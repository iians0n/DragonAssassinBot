"""/wrapped command handler — Assassins Wrapped preview & delivery."""

import asyncio
import io
import logging
from typing import List, Tuple

from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes

from models.player import Player
from services.game_manager import is_admin
from services.wrapped import generate_all_wrapped
from utils.dm_only import dm_only
from utils.formatting import send_to_group

logger = logging.getLogger(__name__)

# In-memory cache of generated cards (cleared after send)
_cached_cards: List[Tuple[Player, bytes, Tuple[str, str, str, str]]] = []


@dm_only
async def wrapped_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /wrapped — admin-only, DM-only.

    • /wrapped          → generate & preview all cards to admin
    • /wrapped send     → deliver cards to every player + group summary
    """
    global _cached_cards

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    sub_command = context.args[0].lower() if context.args else ""

    # ── /wrapped send ─────────────────────────────────────────
    if sub_command == "send":
        if not _cached_cards:
            await update.message.reply_text(
                "⚠️ No cards cached. Run /wrapped first to preview."
            )
            return
        await _send_wrapped(update, context)
        return

    # ── /wrapped (preview) ────────────────────────────────────
    await update.message.reply_text("⏳ Generating Assassins Wrapped cards... This may take a moment.")

    cards = generate_all_wrapped()

    if not cards:
        await update.message.reply_text("❌ No players registered — nothing to wrap!")
        return

    _cached_cards = cards

    # Send every card to admin as a photo with caption
    preview_failed = 0
    for i, (player, img_bytes, (emoji, title, desc, quote)) in enumerate(cards):
        kd = round(player.kills_total / max(player.deaths, 1), 2)
        caption = (
            f"<b>{player.name}</b> (@{player.username})\n"
            f"{emoji} <b>{title}</b> — {desc}\n"
            f"<i>\"{quote}\"</i>\n\n"
            f"⚔️ Kills: {player.kills_total} | 💀 Deaths: {player.deaths}\n"
            f"📊 K/D: {kd} | 🏅 Points: {player.points}"
        )
        for attempt in range(3):
            try:
                await context.bot.send_photo(
                    chat_id=update.effective_user.id,
                    photo=io.BytesIO(img_bytes),
                    caption=caption,
                    parse_mode="HTML",
                    read_timeout=60,
                    write_timeout=60,
                )
                break
            except Exception as e:
                logger.warning(f"Wrapped preview send attempt {attempt+1} failed for {player.name}: {e}")
                if attempt < 2:
                    await asyncio.sleep(2)
                else:
                    preview_failed += 1
        # Small delay between sends to avoid rate limits
        if i < len(cards) - 1:
            await asyncio.sleep(1.5)

    await update.message.reply_text(
        f"✅ <b>{len(cards)}</b> Wrapped cards generated!\n\n"
        "Review them above. When you're happy, run:\n"
        "<code>/wrapped send</code>\n\n"
        "This will DM each player their card and post a summary to the group.",
        parse_mode="HTML",
    )


async def _send_wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deliver cached Wrapped cards to all players and post group summary."""
    global _cached_cards

    await update.message.reply_text("📤 Sending Wrapped cards to all players...")

    sent = 0
    failed = 0

    for i, (player, img_bytes, (emoji, title, desc, quote)) in enumerate(_cached_cards):
        kd = round(player.kills_total / max(player.deaths, 1), 2)
        caption = (
            f"🎮 <b>ASSASSINS WRAPPED 2026</b> 🎮\n\n"
            f"Hey <b>{player.name}</b>, here's your Wrapped!\n\n"
            f"Your award: {emoji} <b>{title}</b>\n"
            f"<i>\"{desc}\"</i>\n\n"
            f"⚔️ Kills: {player.kills_total} | 💀 Deaths: {player.deaths}\n"
            f"📊 K/D: {kd} | 🏅 Points: {player.points}\n\n"
            f"📢 <b>Quote of the Game:</b>\n"
            f"<i>\"{quote}\"</i>\n\n"
            f"GG, see you next season! 🎯"
        )
        for attempt in range(3):
            try:
                await context.bot.send_photo(
                    chat_id=player.user_id,
                    photo=io.BytesIO(img_bytes),
                    caption=caption,
                    parse_mode="HTML",
                    read_timeout=60,
                    write_timeout=60,
                )
                sent += 1
                break
            except Exception as e:
                logger.warning(f"Wrapped send attempt {attempt+1} failed for {player.name} ({player.user_id}): {e}")
                if attempt < 2:
                    await asyncio.sleep(2)
                else:
                    failed += 1
        # Small delay between sends to avoid rate limits
        if i < len(_cached_cards) - 1:
            await asyncio.sleep(1.5)

    # ── Group summary ─────────────────────────────────────────
    group_lines = [
        "╔══════════════════════════════════════╗",
        "║   🏆  ASSASSINS WRAPPED 2026  🏆      ║",
        "╚══════════════════════════════════════╝",
        "",
        "🎖️ <b>SUPERLATIVE AWARDS</b> 🎖️",
        "",
    ]
    for player, _, (emoji, title, desc, quote) in _cached_cards:
        group_lines.append(f"{emoji} <b>{title}</b> — {player.name}")

    group_lines.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
        "Check your DMs for your personal Wrapped card!",
        "GG everyone! See you next season 🎮",
    ])

    group_msg = "\n".join(group_lines)

    try:
        await send_to_group(context.bot, group_msg)
    except Exception as e:
        logger.warning(f"Could not post Wrapped summary to group: {e}")

    # ── Report to admin ───────────────────────────────────────
    await update.message.reply_text(
        f"✅ <b>Wrapped delivery complete!</b>\n\n"
        f"📬 Sent: {sent}\n"
        f"❌ Failed: {failed}\n"
        f"📢 Group summary posted.",
        parse_mode="HTML",
    )

    # Clear cache
    _cached_cards = []
