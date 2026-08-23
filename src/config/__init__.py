"""
Configuration module for org-bot.

This module provides:
1. Configuration settings (BotSettings, GitHubSettings, OrgSettings, ActionConfig)
2. Factory functions to create configured instances
"""

from typing import Callable, Dict, Any
from telegram import Bot

from .bot_config import BotSettings
from .github_settings import GitHubSettings
from .org_settings import OrgSettings
from .state_settings import StateSettings
from .action_config import ActionConfig

# Import commands and actions for factory functions
from ..commands import StartCommand, WebhookCommand, InfoCommand, SearchCommand, OpenCommand
from ..actions import (
    PostToGitJournal,
    PostToTodo,
    PostReplyToEntry,
)


def create_commands(
    get_bot: Callable[[], Bot],
    search_service: Any = None,
) -> Dict[str, Any]:
    """
    Factory function to create command instances.

    Args:
        get_bot: Callable that returns a Bot instance
        search_service: SearchService instance, or None when no state bucket
                        is configured (search command reports itself disabled)

    Returns:
        Dictionary mapping command names to command instances
    """
    return {
        "/start": StartCommand(get_bot),
        "/webhook": WebhookCommand(get_bot),
        "/info": InfoCommand(get_bot),
        "/search": SearchCommand(get_bot, search_service),
        "/open": OpenCommand(get_bot, search_service),
    }


def create_actions(
    github_settings: GitHubSettings,
    org_settings: OrgSettings,
) -> Dict[str, ActionConfig]:
    """
    Factory function to create action instances.

    Args:
        github_settings: GitHub configuration
        org_settings: Org-mode repository configuration

    Returns:
        Dictionary mapping action keywords to ActionConfig instances
    """
    # Initialize action instances
    journal = PostToGitJournal(
        github_token=github_settings.token,
        repo_name=github_settings.repo,
        file_path=org_settings.journal_file,
    )

    todo = PostToTodo(
        github_token=github_settings.token,
        repo_name=github_settings.repo,
        file_path=org_settings.todo_file,
    )

    reply = PostReplyToEntry(
        github_token=github_settings.token,
        repo_name=github_settings.repo,
        file_path=org_settings.journal_file,
        todo_file_path=org_settings.todo_file,
    )

    return {
        "journal": ActionConfig(
            function=journal.run,
            response_message="Added to journal!",
        ),
        "todo": ActionConfig(
            function=todo.run,
            response_message="Added to todo list!",
        ),
        "reply": ActionConfig(
            function=reply.run,
            response_message="Added reply to entry!",
        ),
    }


__all__ = [
    "BotSettings",
    "GitHubSettings",
    "OrgSettings",
    "StateSettings",
    "ActionConfig",
    "create_commands",
    "create_actions",
]
