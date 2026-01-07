"""
This module provides diffrent message "shortcuts" for posting different kind of notes.
For example, posting to a journal, posting a todo, replying to an entry, and, perhaps, add to a shopping list.
"""

from .post_to_journal import PostToGitJournal
from .post_to_todo import PostToTodo
from .post_reply import PostReplyToEntry

__all__ = [
    "PostToGitJournal",
    "PostToTodo",
    "PostReplyToEntry",
]
