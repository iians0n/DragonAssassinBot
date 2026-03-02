"""Game state management service."""

from models.game import GameState
from storage.json_store import store
from config import ADMIN_IDS, GROUP_CHAT_ID


def get_game_state() -> GameState:
    """Get current game state, creating default if none exists."""
    data = store.load_game()
    if not data:
        game = GameState(
            admin_ids=ADMIN_IDS,
            group_chat_id=GROUP_CHAT_ID,
        )
        store.save_game(game.to_dict())
        return game
    return GameState.from_dict(data)


def save_game_state(game: GameState):
    """Save game state."""
    store.save_game(game.to_dict())


def is_admin(user_id: int) -> bool:
    """Check if a user is an admin."""
    game = get_game_state()
    return user_id in game.admin_ids or user_id in ADMIN_IDS


def start_game() -> GameState:
    """Start the game."""
    game = get_game_state()
    game.start()
    save_game_state(game)
    return game


def end_game() -> GameState:
    """End the game."""
    game = get_game_state()
    game.end()
    save_game_state(game)
    return game


def toggle_pause() -> GameState:
    """Toggle pause state."""
    game = get_game_state()
    game.pause()
    save_game_state(game)
    return game


def promote_to_admin(user_id: int):
    """Add a user to the admin list."""
    game = get_game_state()
    if user_id not in game.admin_ids:
        game.admin_ids.append(user_id)
        save_game_state(game)
