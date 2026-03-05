"""Decorator to restrict commands to private (DM) chats only."""

import functools


def dm_only(func):
    """Only allow the wrapped command handler in private chats.

    If invoked in a group/supergroup, replies with a short redirect message
    and returns without executing the handler.
    """
    @functools.wraps(func)
    async def wrapper(update, context):
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "📩 Please use this command in a private message to the bot."
            )
            return
        return await func(update, context)
    return wrapper
