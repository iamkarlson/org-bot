# Org-Bot Unit Tests

Comprehensive unit tests for the org-bot Telegram bot.

## Overview

This test suite provides comprehensive coverage for the main bot functionality:

- **PostToGitJournal**: Tests for posting journal entries to GitHub org-mode files
- **PostToTodo**: Tests for posting TODO items to GitHub org-mode files

Each class is tested with three message types:
- Text messages
- Photo messages (with captions)
- File/document messages (with captions)

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Pytest configuration and fixtures
├── test_journal_posting.py     # Journal posting tests (3 tests)
├── test_todo_posting.py        # TODO posting tests (3 tests)
├── fixtures/                   # Test fixtures directory
│   ├── org-files/             # Git submodule with org files
│   ├── images/                # Sample images for testing
│   └── files/                 # Sample files for testing
└── README.md                  # This file
```

## Setup Instructions

### 1. Install Dependencies

```bash
# Using taskfile
task sync_deps

# Or directly with uv
uv sync
```

### 2. Set Up Git Submodule for Test Org Files

The tests expect org files to be available in `tests/fixtures/org-files` as a git submodule.

**Option A: Add Your Existing Org Files Repository**

```bash
# Navigate to project root
cd /path/to/org-bot

# Add your org files repository as a submodule
git submodule add <your-org-files-repo-url> tests/fixtures/org-files

# Initialize and update the submodule
git submodule update --init --recursive

# Commit the submodule
git add .gitmodules tests/fixtures/org-files
git commit -m "Add test org files as git submodule"
```

**Option B: Create a New Test Repository**

```bash
# Create a new repository for test org files
mkdir temp-org-files
cd temp-org-files
git init

# Create test org files
cat > test_journal.org << 'EOF'
* Test Journal

This is a test journal file for unit tests.
EOF

cat > test_todo.org << 'EOF'
* Test TODO List

This is a test TODO file for unit tests.
EOF

# Commit and push to a new repository
git add .
git commit -m "Initial test org files"
git remote add origin <your-new-repo-url>
git push -u origin main

# Go back to org-bot and add as submodule
cd /path/to/org-bot
git submodule add <your-new-repo-url> tests/fixtures/org-files
git submodule update --init --recursive
```

### 3. Configure Environment Variables (Optional)

For integration tests that connect to real GitHub repositories:

```bash
# Copy dev.env and add test credentials
cp dev.env test.env

# Edit test.env and add:
export GITHUB_TOKEN="your_github_token_here"
export TEST_GITHUB_REPO="username/test-repo"
```

**Note**: The unit tests use mocks by default and don't require real credentials.

## Running Tests

### Quick Test Run

```bash
# Using taskfile (recommended)
task test

# Or directly with pytest
pytest tests/ -v

# Or use the test runner script (includes git submodule checks)
./run_tests.sh
```

### Test Options

```bash
# Run only journal tests
pytest tests/test_journal_posting.py -v

# Run only TODO tests
pytest tests/test_todo_posting.py -v

# Run only text message tests
pytest tests/ -v -m text

# Run only picture/photo tests
pytest tests/ -v -m picture

# Run only file/document tests
pytest tests/ -v -m file

# Run with specific log level
pytest tests/ -v --log-cli-level=INFO

# Run without output capture (see all print statements)
pytest tests/ -v -s
```

### Available Test Markers

- `unit`: Unit tests (all current tests)
- `integration`: Integration tests (future)
- `journal`: Journal posting tests
- `todo`: TODO posting tests
- `text`: Text message tests
- `picture`: Photo/picture message tests
- `file`: File/document message tests

## Verbose Logging

The tests are configured for maximum verbosity to help with debugging:

### Log Levels
- **DEBUG**: All application logs, function calls, variable values
- **INFO**: Test execution flow, major operations
- **WARNING**: Potential issues, missing configurations
- **ERROR**: Test failures, exceptions

### What Gets Logged

1. **Test Session Info**:
   - Python version
   - Working directory
   - Test environment

2. **Git Submodule Status**:
   - Git status
   - Git log (last 5 commits)
   - Current commit details

3. **Test Execution**:
   - Test start/end markers
   - Input parameters
   - Method calls
   - GitHub API interactions
   - Content verification

4. **Mock Objects**:
   - Created mock messages
   - Mock GitHub clients
   - Configuration values

### Log Output Examples

```
2025-12-15 10:30:45.123 [INFO    ] [tests.conftest              ] STARTING TEST SESSION
2025-12-15 10:30:45.124 [DEBUG   ] [tests.conftest              ] Fixtures directory: /path/to/tests/fixtures
2025-12-15 10:30:45.234 [INFO    ] [tests.test_journal_posting  ] TEST: Post text message to journal
2025-12-15 10:30:45.235 [DEBUG   ] [tests.test_journal_posting  ] Mock message created - ID: 12345, Chat ID: 1234567890
```

## CI/CD Integration

Tests run automatically on every push to:
- `main` branch
- `claude/**` branches
- `feature/**` branches
- `develop` branch

And on all pull requests to `main` and `develop`.

### GitHub Actions Workflow

The workflow (`.github/workflows/test.yml`):
1. Checks out code with submodules
2. Sets up Python (3.11 and 3.12)
3. Installs dependencies with uv
4. Checks git submodule status
5. Runs tests with verbose logging
6. Uploads test results as artifacts

### Required Secrets

Add these secrets to your GitHub repository for CI/CD:
- `TEST_GITHUB_TOKEN`: GitHub personal access token for tests (optional)
- `TEST_GITHUB_REPO`: Test repository name (optional, e.g., "username/test-repo")

**Note**: These are optional. Tests will use mocks if not provided.

## Test Coverage

Current test coverage:

| Module | Class | Method | Text | Photo | File | Total |
|--------|-------|--------|------|-------|------|-------|
| post_to_journal | PostToGitJournal | run() | ✅ | ✅ | ✅ | 3 |
| post_to_journal | PostToTodo | run() | ✅ | ✅ | ✅ | 3 |

**Total Tests**: 6 happy path tests

## Adding New Tests

### 1. Create a new test file

```python
# tests/test_new_feature.py
import logging
import pytest
from unittest.mock import Mock

logger = logging.getLogger(__name__)

class TestNewFeature:
    @pytest.mark.unit
    def test_new_functionality(self):
        logger.info("Testing new functionality")
        # Your test code here
        assert True
```

### 2. Use existing fixtures

Available fixtures in `conftest.py`:
- `fixtures_dir`: Path to fixtures directory
- `org_files_dir`: Path to org-files submodule
- `sample_image_path`: Path to test image
- `sample_file_path`: Path to test PDF
- `mock_telegram_message_text`: Mock text message
- `mock_telegram_message_photo`: Mock photo message
- `mock_telegram_message_document`: Mock document message
- `mock_github_token`: GitHub token (mock or from env)
- `mock_github_repo`: GitHub repository name
- `test_config`: Test configuration dictionary

### 3. Add appropriate markers

```python
@pytest.mark.unit           # For unit tests
@pytest.mark.integration    # For integration tests
@pytest.mark.journal        # For journal-related tests
@pytest.mark.todo           # For TODO-related tests
@pytest.mark.text           # For text message tests
@pytest.mark.picture        # For picture message tests
@pytest.mark.file           # For file message tests
```

## Troubleshooting

### Tests fail with "No module named 'src'"

Make sure you're running tests from the project root:
```bash
cd /path/to/org-bot
pytest tests/
```

### Git submodule not found warnings

Initialize the submodule:
```bash
git submodule update --init --recursive
```

### Import errors

Sync dependencies:
```bash
task sync_deps
```

### Mock objects not working

Check that you're using the fixtures:
```python
def test_something(self, mock_telegram_message_text):
    # Use mock_telegram_message_text, not creating your own
    message = mock_telegram_message_text
```

## Future Enhancements

Planned improvements:
- [ ] Integration tests with real GitHub API
- [ ] Tests for error handling and edge cases
- [ ] Performance benchmarks
- [ ] Code coverage reporting
- [ ] Mutation testing
- [ ] Contract tests for GitHub API

## Contributing

When adding tests:
1. Follow existing patterns in `test_journal_posting.py` and `test_todo_posting.py`
2. Add comprehensive logging
3. Use descriptive test names
4. Add docstrings explaining what the test does
5. Use appropriate markers
6. Update this README with new tests

## Questions?

For questions or issues with tests:
1. Check the test logs (very detailed)
2. Review this README
3. Check `conftest.py` for available fixtures
4. Open an issue in the repository
