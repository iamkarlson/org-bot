"""
Configuration module for org-bot.

This module provides:
1. Configuration dataclasses (BotConfig, GitHubConfig, ActionConfig)
2. Factory functions to create configured instances
"""

from typing import Callable, Dict, Any
from telegram import Bot

from .bot_config import BotConfig
from .github_settings import GitHubSettings
from .org_settings import OrgSettings
from .action_config import ActionConfig

# Import commands and actions for factory functions
from ..commands import StartCommand, WebhookCommand, InfoCommand
from ..actions import (
    PostToGitJournal,
    PostToTodo,
    PostReplyToEntry,
)


def create_commands(get_bot: Callable[[], Bot]) -> Dict[str, Any]:
    """
    Factory function to create command instances.

    Args:
        get_bot: Callable that returns a Bot instance

    Returns:
        Dictionary mapping command names to command instances
    """
    return {
        "/start": StartCommand(get_bot),
        "/webhook": WebhookCommand(get_bot),
        "/info": InfoCommand(get_bot),
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
    "BotConfig",
    "GitHubSettings",
    "OrgSettings",
    "ActionConfig",
    "create_commands",
    "create_actions",
]
