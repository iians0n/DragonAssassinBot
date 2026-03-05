"""Handlers for kill dispute callbacks and admin resolution."""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes

import pytz

from services.pending_kill import (
    get_pending_kill,
    confirm_pending_kill,
    dispute_pending_kill,
    resolve_disputed_kill,
)
from services.registration import get_player
from services.game_manager import get_game_state, is_admin
from utils.formatting import (
    format_kill_announcement,
    send_to_group,
    player_mention,
)
from config import COOLDOWN_BALL, COOLDOWN_STEALTH, TIMEZONE
from utils.dm_only import dm_only

logger = logging.getLogger(__name__)


async def kill_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Accept / Dispute inline button presses from the target player."""
    query = update.callback_query
    await query.answer()

    data = query.data  # e.g. "kill_accept:uuid" or "kill_dispute:uuid"
    if ":" not in data:
        return

    action, pending_kill_id = data.split(":", 1)
    pk = get_pending_kill(pending_kill_id)

    if not pk:
        await query.edit_message_text("❌ This kill report no longer exists.")
        return

    user_id = query.from_user.id

    # Only the target can respond
    if user_id != pk.target_id:
        await query.answer("❌ Only the target player can respond to this.", show_alert=True)
        return

    if pk.status != "pending":
        status_text = {"confirmed": "already confirmed", "disputed": "already disputed",
                       "rejected": "already rejected"}.get(pk.status, pk.status)
        await query.edit_message_text(f"ℹ️ This kill has been {status_text}.")
        return

    if action == "kill_accept":
        await _handle_accept(query, context, pk)
    elif action == "kill_dispute":
        await _handle_dispute(query, context, pk)


async def _handle_accept(query, context, pk):
    """Target accepted the kill."""
    kill_event_dict, bounty_bonus, new_achievements = confirm_pending_kill(pk.id)

    if not kill_event_dict:
        await query.edit_message_text("❌ Failed to confirm kill. Contact an admin.")
        return

    # Update the button message
    await query.edit_message_text("✅ You accepted the kill. Cooldown started.")

    # Run post-kill flow
    await _post_kill_flow(context, pk, bounty_bonus, new_achievements)


async def _handle_dispute(query, context, pk):
    """Target clicked dispute — prompt for a reason before processing."""
    # Store the pending kill ID so we can process it when the reason arrives
    context.user_data["awaiting_dispute_reason"] = pk.id

    # Update the button message
    await query.edit_message_text(
        "⚠️ You're disputing this kill.\n\n"
        "📝 Please type a short reason for your dispute:"
    )

    # Send a ForceReply to guide the user to type
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="✏️ Type your dispute reason below:",
        reply_markup=ForceReply(selective=True),
    )


async def dispute_reason_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Capture the dispute reason text after the user clicked Dispute."""
    pending_kill_id = context.user_data.pop("awaiting_dispute_reason", None)
    if not pending_kill_id:
        return  # Not awaiting a dispute reason, ignore

    reason = update.message.text.strip()[:200]  # Cap at 200 chars
    pk = get_pending_kill(pending_kill_id)

    if not pk:
        await update.message.reply_text("❌ This kill report no longer exists.")
        return

    if pk.status != "pending":
        await update.message.reply_text("ℹ️ This kill has already been processed.")
        return

    disputed_pk = dispute_pending_kill(pk.id, reason=reason)

    if not disputed_pk:
        await update.message.reply_text("❌ Could not dispute this kill. It may have already been processed.")
        return

    await update.message.reply_text(
        "⚠️ Dispute submitted! An admin has been notified and will review it."
    )

    # Notify killer
    killer = get_player(pk.killer_id)
    killer_name = killer.name if killer else "Unknown"
    target = get_player(pk.target_id)
    target_name = target.name if target else "Unknown"

    try:
        await context.bot.send_message(
            chat_id=pk.killer_id,
            text=(
                f"⚠️ <b>{target_name}</b> disputed your kill!\n"
                f"📝 Reason: <i>{reason}</i>\n"
                f"An admin will review and resolve this."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not notify killer about dispute: {e}")

    # Format kill time for the admin notification
    try:
        tz = pytz.timezone(TIMEZONE)
        kill_time = datetime.fromtimestamp(pk.timestamp, tz=tz).strftime("%d %b, %I:%M:%S %p SGT")
    except Exception:
        kill_time = "Unknown"

    # Build inline buttons for admins
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve Kill", callback_data=f"admin_approve:{pk.id}"),
            InlineKeyboardButton("❌ Reject Kill", callback_data=f"admin_reject:{pk.id}"),
        ]
    ])

    # Notify all admins with dispute reason included
    game = get_game_state()
    admin_messages = []
    for admin_id in game.admin_ids:
        try:
            msg = await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🔔 <b>Kill Dispute — Needs Your Review</b>\n\n"
                    f"🗡️ <b>{killer_name}</b> claims to have killed <b>{target_name}</b>\n"
                    f"⏰ Kill reported at {kill_time}\n"
                    f"🎯 Type: {pk.kill_type}\n\n"
                    f"<b>{target_name}</b> disputes this kill.\n"
                    f"📝 Reason: <i>{reason}</i>\n\n"
                    f"Please review and tap a button below:"
                ),
                parse_mode="HTML",
                reply_markup=buttons,
            )
            admin_messages.append((admin_id, msg.message_id))
        except Exception as e:
            logger.warning(f"Could not notify admin {admin_id} about dispute: {e}")

    # Store admin message IDs so we can update them when resolved
    if "dispute_messages" not in context.bot_data:
        context.bot_data["dispute_messages"] = {}
    context.bot_data["dispute_messages"][pk.id] = admin_messages


async def admin_resolve_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin Approve / Reject inline button presses for disputed kills."""
    query = update.callback_query
    user_id = query.from_user.id

    if not is_admin(user_id):
        await query.answer("❌ Only admins can resolve disputes.", show_alert=True)
        return

    await query.answer()

    data = query.data  # e.g. "admin_approve:uuid" or "admin_reject:uuid"
    if ":" not in data:
        return

    action, pending_kill_id = data.split(":", 1)
    approved = action == "admin_approve"

    kill_event_dict, bounty_bonus, pk, new_achievements = resolve_disputed_kill(
        pending_kill_id, approved, user_id
    )

    if pk is None:
        await query.edit_message_text("❌ Kill not found or not in disputed status.")
        return

    # Get the name of the admin who resolved
    admin_name = query.from_user.first_name or "Admin"

    killer = get_player(pk.killer_id)
    target = get_player(pk.target_id)
    killer_name = killer.name if killer else "Unknown"
    target_name = target.name if target else "Unknown"

    # Format kill time for the resolved message
    try:
        tz = pytz.timezone(TIMEZONE)
        kill_time = datetime.fromtimestamp(pk.timestamp, tz=tz).strftime("%d %b, %I:%M:%S %p SGT")
    except Exception:
        kill_time = "Unknown"

    dispute_reason = pk.disputed_reason or "No reason given"

    if approved:
        resolved_text = (
            f"✅ <b>Kill Approved by Admin {admin_name}</b>\n\n"
            f"🗡️ <b>{killer_name}</b> → <b>{target_name}</b>\n"
            f"⏰ Kill reported at {kill_time}\n"
            f"🎯 Type: {pk.kill_type}\n"
            f"📝 Dispute reason: <i>{dispute_reason}</i>\n\n"
            f"Points awarded. Cooldown started for {target_name}."
        )
        await query.edit_message_text(resolved_text, parse_mode="HTML")
        # Run post-kill flow
        await _post_kill_flow(context, pk, bounty_bonus, new_achievements)

        # Notify both players
        try:
            await context.bot.send_message(
                chat_id=pk.killer_id,
                text=f"✅ Admin approved your kill on <b>{target_name}</b>!",
                parse_mode="HTML",
            )
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=pk.target_id,
                text=f"⚖️ Admin reviewed the dispute and <b>approved</b> the kill. Cooldown started.",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        resolved_text = (
            f"❌ <b>Kill Rejected by Admin {admin_name}</b>\n\n"
            f"🗡️ <b>{killer_name}</b> → <b>{target_name}</b>\n"
            f"⏰ Kill reported at {kill_time}\n"
            f"🎯 Type: {pk.kill_type}\n"
            f"📝 Dispute reason: <i>{dispute_reason}</i>\n\n"
            f"No points awarded. {target_name} is safe."
        )
        await query.edit_message_text(resolved_text, parse_mode="HTML")
        # Notify both players
        try:
            await context.bot.send_message(
                chat_id=pk.killer_id,
                text=f"❌ Admin rejected your kill on <b>{target_name}</b>. No points awarded.",
                parse_mode="HTML",
            )
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=pk.target_id,
                text=f"⚖️ Admin reviewed the dispute and <b>rejected</b> the kill. You're safe!",
                parse_mode="HTML",
            )
        except Exception:
            pass

    # Update all other admins' messages for this dispute
    dispute_messages = context.bot_data.get("dispute_messages", {}).get(pending_kill_id, [])
    for chat_id, msg_id in dispute_messages:
        if chat_id == user_id:
            continue  # already edited via query.edit_message_text
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=resolved_text,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Could not update admin {chat_id}'s dispute message: {e}")

    # Clean up stored message IDs
    context.bot_data.get("dispute_messages", {}).pop(pending_kill_id, None)


@dm_only
async def resolvekill_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /resolvekill <kill_id> approve|reject — admin resolves a disputed kill (text fallback)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /resolvekill <kill_id> approve|reject"
        )
        return

    pending_kill_id = context.args[0]
    decision = context.args[1].lower()

    if decision not in ("approve", "reject"):
        await update.message.reply_text("❌ Decision must be 'approve' or 'reject'.")
        return

    approved = decision == "approve"
    kill_event_dict, bounty_bonus, pk, new_achievements = resolve_disputed_kill(
        pending_kill_id, approved, update.effective_user.id
    )

    if pk is None:
        await update.message.reply_text(
            "❌ Kill not found or not in disputed status."
        )
        return

    killer = get_player(pk.killer_id)
    target = get_player(pk.target_id)
    killer_name = killer.name if killer else "Unknown"
    target_name = target.name if target else "Unknown"

    if approved:
        await update.message.reply_text(
            f"✅ Kill approved! <b>{killer_name}</b> → <b>{target_name}</b>",
            parse_mode="HTML",
        )
        # Run post-kill flow
        await _post_kill_flow(context, pk, bounty_bonus, new_achievements)

        try:
            await context.bot.send_message(
                chat_id=pk.killer_id,
                text=f"✅ Admin approved your kill on <b>{target_name}</b>!",
                parse_mode="HTML",
            )
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=pk.target_id,
                text=f"⚖️ Admin reviewed the dispute and <b>approved</b> the kill. Cooldown started.",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        await update.message.reply_text(
            f"❌ Kill rejected. <b>{killer_name}</b> → <b>{target_name}</b> voided.",
            parse_mode="HTML",
        )
        try:
            await context.bot.send_message(
                chat_id=pk.killer_id,
                text=f"❌ Admin rejected your kill on <b>{target_name}</b>. No points awarded.",
                parse_mode="HTML",
            )
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=pk.target_id,
                text=f"⚖️ Admin reviewed the dispute and <b>rejected</b> the kill. You're safe!",
                parse_mode="HTML",
            )
        except Exception:
            pass


async def _post_kill_flow(context, pk, bounty_bonus, new_achievements=None):
    """
    Shared post-kill flow: announce to group and DM target about cooldown.
    Used by accept, auto-confirm, and admin approve.
    """
    killer = get_player(pk.killer_id)
    target = get_player(pk.target_id)

    if not killer or not target:
        return

    game = get_game_state()

    # Announce to group (with streak + achievements)
    announcement = format_kill_announcement(
        killer.to_dict(), target.to_dict(), pk.kill_type, bounty_bonus,
        new_achievements=new_achievements,
    )

    group_id = game.group_chat_id
    if group_id:
        try:
            await send_to_group(context.bot, announcement, game)
        except Exception as e:
            logger.warning(f"Could not post kill announcement to group: {e}")

    # DM target about cooldown
    cooldown_hours = COOLDOWN_STEALTH / 3600 if pk.kill_type == "stealth" else COOLDOWN_BALL / 3600
    try:
        await context.bot.send_message(
            chat_id=target.user_id,
            text=(
                f"💀 Kill confirmed. You are now in cooldown for {cooldown_hours:.0f} hour(s).\n"
                f"You'll respawn automatically."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not DM target {target.user_id}: {e}")
