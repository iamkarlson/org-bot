import os
from unittest import TestCase

from src.commands.post_to_journal import PostToGitJournal


class TestPostToGitJournal(TestCase):
    def test_run(self):
        """
        Test setups some mock data, and runs the task.
        """
        github_token = os.getenv("GITHUB_TOKEN", None)
        repo_name = os.getenv("GITHUB_REPO", None)
        file_path = os.getenv("JOURNAL_FILE", "journal.md")

        task = PostToGitJournal(
            github_token=github_token,
            repo_name="iamkarlson/braindb",
            file_path="test_journal.org",
        )
        mock_message = type(
            "Message",
            (object,),
            {
                "message_id": 1,
                "text": "This is a test message.",
            },
        )
        mock_message.chat = type(
            "Chat",
            (object,),
            {
                "id": 1,
            },
        )
        task.run(message=mock_message)

    def test__append_text_to_file(self):
        self.fail()

    def test__get_text_from_message(self):
        self.fail()
