import os
from typing import Callable
from telegram import Bot

from .commands import (
    StartCommand,
    WebhookCommand,
    InfoCommand,
    PostToGitJournal,
    PostToTodo,
)


def init_commands(get_bot: Callable[[], Bot]):
    """Initialize command instances with bot getter dependency."""
    return {
        "/start": StartCommand(get_bot),
        "/webhook": WebhookCommand(get_bot),
        "/info": InfoCommand(get_bot),
    }


# Configuration is coming from "JOURNAL_FILE" env variable.
github_token = os.getenv("GITHUB_TOKEN", None)
repo_name = os.getenv("GITHUB_REPO", None)
file_path = os.getenv("JOURNAL_FILE", "journal.md")

journal = PostToGitJournal(
    github_token=github_token, repo_name=repo_name, file_path=file_path
)

todo = PostToTodo(github_token=github_token, repo_name=repo_name, file_path="todo.org")

# Default action is to post to journal
default_action = journal.run

actions = {
    "journal": {"function": journal.run, "response": "Added to journal!"},
    "todo": {"function": todo.run, "response": "Added to todo list!"},
}
