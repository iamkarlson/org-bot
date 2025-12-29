import os
from dataclasses import dataclass
from typing import Callable, Dict, Any
from telegram import Bot

from .commands import StartCommand, WebhookCommand, InfoCommand
from .actions import (
    PostToGitJournal,
    PostToTodo,
    PostReplyToEntry,
)


@dataclass
class BotConfig:
    """Core bot configuration from environment."""

    bot_token: str
    authorized_chat_ids: list[int]
    ignored_chat_ids: list[int]
    forward_unauthorized_to: int | None
    sentry_dsn: str

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Load configuration from environment variables."""
        authorized_ids = [
            int(id) for id in os.environ["AUTHORIZED_CHAT_IDS"].split(",")
        ]
        ignored_ids = [
            int(id)
            for id in os.environ.get("IGNORED_CHAT_IDS", "").split(",")
            if id
        ]
        forward_to = os.environ.get("FORWARD_UNAUTHORIZED_TO")

        return cls(
            bot_token=os.environ["BOT_TOKEN"],
            authorized_chat_ids=authorized_ids,
            ignored_chat_ids=ignored_ids,
            forward_unauthorized_to=int(forward_to) if forward_to else None,
            sentry_dsn=os.environ.get("SENTRY_DSN", ""),
        )


@dataclass
class GitHubConfig:
    """GitHub integration configuration."""

    token: str
    repo_name: str
    journal_file: str
    todo_file: str

    @classmethod
    def from_env(cls) -> "GitHubConfig":
        """Load GitHub configuration from environment variables."""
        return cls(
            token=os.environ.get("GITHUB_TOKEN", ""),
            repo_name=os.environ.get("GITHUB_REPO", ""),
            journal_file=os.environ.get("JOURNAL_FILE", "journal.md"),
            todo_file="todo.org",
        )


@dataclass
class ActionConfig:
    """Configuration for a single action."""

    function: Callable
    response_message: str


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


def create_actions(github_config: GitHubConfig) -> Dict[str, ActionConfig]:
    """
    Factory function to create action instances.

    Args:
        github_config: GitHub configuration dataclass

    Returns:
        Dictionary mapping action keywords to ActionConfig instances
    """
    # Initialize action instances
    journal = PostToGitJournal(
        github_token=github_config.token,
        repo_name=github_config.repo_name,
        file_path=github_config.journal_file,
    )

    todo = PostToTodo(
        github_token=github_config.token,
        repo_name=github_config.repo_name,
        file_path=github_config.todo_file,
    )

    reply = PostReplyToEntry(
        github_token=github_config.token,
        repo_name=github_config.repo_name,
        file_path=github_config.journal_file,
        todo_file_path=github_config.todo_file,
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
