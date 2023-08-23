import os

from src.commands import *
from src.commands.post_to_journal import PostToGitJournal

commands = {
    "/start": command_start,
    "/webhook": command_webhook,
    "/info": command_info,
}


# Configuration is coming from "JOURNAL_FILE" env variable.

file_path = os.getenv("JOURNAL_FILE", "journal.md")
github_token = os.getenv("GITHUB_TOKEN", None)
journal = PostToGitJournal(config={file_path: file_path, github_token: github_token})
post_to_journal = journal.run

default_action = post_to_journal
