"""Handlers for kill dispute callbacks and admin resolution."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

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
from config import COOLDOWN_BALL, COOLDOWN_STEALTH

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
    kill_event_dict, bounty_bonus = confirm_pending_kill(pk.id)

    if not kill_event_dict:
        await query.edit_message_text("❌ Failed to confirm kill. Contact an admin.")
        return

    # Update the button message
    await query.edit_message_text("✅ You accepted the kill. Cooldown started.")

    # Run post-kill flow
    await _post_kill_flow(context, pk, bounty_bonus)


async def _handle_dispute(query, context, pk):
    """Target disputed the kill."""
    disputed_pk = dispute_pending_kill(pk.id)

    if not disputed_pk:
        await query.edit_message_text("❌ Could not dispute this kill. It may have already been processed.")
        return

    # Update the button message
    await query.edit_message_text(
        "⚠️ You disputed this kill. An admin has been notified and will review it."
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
                f"An admin will review and resolve this."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not notify killer about dispute: {e}")

    # Notify all admins
    game = get_game_state()
    for admin_id in game.admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🔔 <b>Kill Dispute</b>\n\n"
                    f"Killer: <b>{killer_name}</b>\n"
                    f"Target: <b>{target_name}</b>\n"
                    f"Type: {pk.kill_type}\n"
                    f"Kill ID: <code>{pk.id}</code>\n\n"
                    f"Use:\n"
                    f"<code>/resolvekill {pk.id} approve</code>\n"
                    f"<code>/resolvekill {pk.id} reject</code>"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Could not notify admin {admin_id} about dispute: {e}")


async def resolvekill_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /resolvekill <kill_id> approve|reject — admin resolves a disputed kill."""
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
    kill_event_dict, bounty_bonus, pk = resolve_disputed_kill(
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
        await _post_kill_flow(context, pk, bounty_bonus)

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
        await update.message.reply_text(
            f"❌ Kill rejected. <b>{killer_name}</b> → <b>{target_name}</b> voided.",
            parse_mode="HTML",
        )
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


async def _post_kill_flow(context, pk, bounty_bonus):
    """
    Shared post-kill flow: announce to group and DM target about cooldown.
    Used by accept, auto-confirm, and admin approve.
    """
    killer = get_player(pk.killer_id)
    target = get_player(pk.target_id)

    if not killer or not target:
        return

    game = get_game_state()

    # Announce to group
    announcement = format_kill_announcement(
        killer.to_dict(), target.to_dict(), pk.kill_type, bounty_bonus
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
