"""
Pytest configuration and fixtures for org-bot tests.

This module provides:
- Detailed logging configuration
- Mock Telegram message objects
- Test fixtures for different message types
- Git submodule verification
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, Mock

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# Configure root logger for maximum verbosity
def configure_verbose_logging() -> None:
    """Configure comprehensive logging for all tests."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler with detailed formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # Very detailed formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s.%(msecs)03d [%(levelname)-8s] [%(name)-30s] %(funcName)-25s:%(lineno)-4d - %(message)s',
        datefmt='%Y-%m-%d_%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Also configure specific loggers
    for logger_name in ['src', 'telegram', 'github', 'urllib3']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)

    logging.info("=" * 100)
    logging.info("VERBOSE LOGGING CONFIGURED FOR ORG-BOT TESTS")
    logging.info("=" * 100)


# Configure logging at module import
configure_verbose_logging()


@pytest.fixture(scope="session", autouse=True)
def log_test_session_start() -> None:
    """Log the start of the test session."""
    logging.info("=" * 100)
    logging.info("STARTING TEST SESSION")
    logging.info(f"Python version: {sys.version}")
    logging.info(f"Working directory: {os.getcwd()}")
    logging.info(f"Test directory: {Path(__file__).parent}")
    logging.info("=" * 100)


@pytest.fixture(scope="function", autouse=True)
def log_test_function(request: pytest.FixtureRequest) -> None:
    """Log the start and end of each test function."""
    test_name = request.node.name
    logging.info("")
    logging.info("=" * 100)
    logging.info(f"STARTING TEST: {test_name}")
    logging.info("=" * 100)

    yield

    logging.info("=" * 100)
    logging.info(f"COMPLETED TEST: {test_name}")
    logging.info("=" * 100)
    logging.info("")


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the fixtures directory."""
    fixtures_path = Path(__file__).parent / "fixtures"
    logging.debug(f"Fixtures directory: {fixtures_path}")
    return fixtures_path


@pytest.fixture
def org_files_dir(fixtures_dir: Path) -> Path:
    """Return the path to the org-files submodule directory."""
    org_files_path = fixtures_dir / "org-files"
    logging.debug(f"Org files directory: {org_files_path}")

    if not org_files_path.exists():
        logging.warning(f"Org files directory does not exist: {org_files_path}")
        logging.warning("This directory should be a git submodule with test org files")

    return org_files_path


@pytest.fixture
def sample_image_path(fixtures_dir: Path) -> Path:
    """Return path to a sample test image."""
    image_path = fixtures_dir / "images" / "test_image.png"
    logging.debug(f"Sample image path: {image_path}")
    return image_path


@pytest.fixture
def sample_file_path(fixtures_dir: Path) -> Path:
    """Return path to a sample test file."""
    file_path = fixtures_dir / "files" / "test_document.pdf"
    logging.debug(f"Sample file path: {file_path}")
    return file_path


@pytest.fixture
def mock_telegram_message_text() -> Mock:
    """
    Create a mock Telegram text message.

    Returns a message object with:
    - message_id
    - text content
    - chat object with id
    """
    logging.debug("Creating mock text message")

    message = Mock()
    message.message_id = 12345
    message.text = "This is a test message from the unit tests."
    message.caption = None
    message.photo = None
    message.document = None

    # Mock chat object
    chat = Mock()
    chat.id = 1234567890
    message.chat = chat

    logging.debug(f"Mock message created - ID: {message.message_id}, Chat ID: {chat.id}")
    logging.debug(f"Message text: {message.text}")

    return message


@pytest.fixture
def mock_telegram_message_photo() -> Mock:
    """
    Create a mock Telegram photo message.

    Returns a message object with:
    - message_id
    - caption (text)
    - photo array
    - chat object with id
    """
    logging.debug("Creating mock photo message")

    message = Mock()
    message.message_id = 12346
    message.text = None
    message.caption = "This is a photo caption from the unit tests."

    # Mock photo array (Telegram sends multiple sizes)
    photo = Mock()
    photo.file_id = "mock_photo_file_id_123"
    photo.file_size = 1024 * 50  # 50KB
    photo.width = 800
    photo.height = 600
    message.photo = [photo]

    message.document = None

    # Mock chat object
    chat = Mock()
    chat.id = 1234567890
    message.chat = chat

    logging.debug(f"Mock photo message created - ID: {message.message_id}, Chat ID: {chat.id}")
    logging.debug(f"Message caption: {message.caption}")
    logging.debug(f"Photo file_id: {photo.file_id}")

    return message


@pytest.fixture
def mock_telegram_message_document() -> Mock:
    """
    Create a mock Telegram document/file message.

    Returns a message object with:
    - message_id
    - caption (text)
    - document object
    - chat object with id
    """
    logging.debug("Creating mock document message")

    message = Mock()
    message.message_id = 12347
    message.text = None
    message.caption = "This is a document caption from the unit tests."
    message.photo = None

    # Mock document object
    document = Mock()
    document.file_id = "mock_document_file_id_456"
    document.file_name = "test_document.pdf"
    document.file_size = 1024 * 100  # 100KB
    document.mime_type = "application/pdf"
    message.document = document

    # Mock chat object
    chat = Mock()
    chat.id = 1234567890
    message.chat = chat

    logging.debug(f"Mock document message created - ID: {message.message_id}, Chat ID: {chat.id}")
    logging.debug(f"Message caption: {message.caption}")
    logging.debug(f"Document file_id: {document.file_id}, filename: {document.file_name}")

    return message


@pytest.fixture
def mock_github_token() -> str:
    """Return a mock GitHub token or get from environment."""
    token = os.getenv("GITHUB_TOKEN", "mock_github_token_for_testing")
    logging.debug(f"Using GitHub token: {token[:10]}..." if len(token) > 10 else "Using mock token")
    return token


@pytest.fixture
def mock_github_repo() -> str:
    """Return a mock GitHub repository name or get from environment."""
    repo = os.getenv("TEST_GITHUB_REPO", "test-user/test-repo")
    logging.debug(f"Using GitHub repository: {repo}")
    return repo


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Return test configuration dictionary."""
    config = {
        "github_token": os.getenv("GITHUB_TOKEN", "mock_token"),
        "github_repo": os.getenv("TEST_GITHUB_REPO", "test-user/test-repo"),
        "journal_file": "test_journal.org",
        "todo_file": "test_todo.org",
    }

    logging.debug("Test configuration:")
    for key, value in config.items():
        if "token" in key.lower():
            logging.debug(f"  {key}: {value[:10]}..." if len(str(value)) > 10 else f"  {key}: ***")
        else:
            logging.debug(f"  {key}: {value}")

    return config
