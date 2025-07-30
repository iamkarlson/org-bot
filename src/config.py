import os

from .commands import (
    command_start,
    command_webhook,
    command_info,
    PostToGitJournal,
    PostToTodo,
)

commands = {
    "/start": command_start,
    "/webhook": command_webhook,
    "/info": command_info,
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
