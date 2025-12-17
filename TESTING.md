# Testing Guide for Org-Bot

## Quick Start

```bash
# 1. Install dependencies
task sync_deps

# 2. Set up test org files submodule (see below)
git submodule add <your-org-repo-url> tests/fixtures/org-files

# 3. Run tests
task test

# Or run tests quickly without submodule checks
task test-quick
```

## Setting Up Test Org Files as Git Submodule

The tests expect your org files to be available as a git submodule in `tests/fixtures/org-files/`.

### Step 1: Prepare Your Org Files Repository

If you already have an org files repository, skip to Step 2.

If you need to create one:

```bash
# Create a new directory for your test org files
mkdir ~/test-org-files
cd ~/test-org-files

# Initialize as git repository
git init

# Create the expected org files
cat > test_journal.org << 'EOF'
#+TITLE: Test Journal
#+AUTHOR: Your Name

* Test Journal Entries

This file is used for testing journal posting functionality.
EOF

cat > test_todo.org << 'EOF'
#+TITLE: Test TODO List
#+AUTHOR: Your Name

* Active TODOs

This file is used for testing TODO posting functionality.
EOF

# Commit the files
git add .
git commit -m "Initial test org files for org-bot tests"

# Create a GitHub repository and push
# (Create the repo on GitHub first, then:)
git remote add origin https://github.com/yourusername/test-org-files.git
git branch -M main
git push -u origin main
```

### Step 2: Add as Submodule to org-bot

```bash
# Navigate to your org-bot directory
cd /path/to/org-bot

# Add the org files repository as a submodule
git submodule add https://github.com/yourusername/test-org-files.git tests/fixtures/org-files

# Initialize and update the submodule
git submodule update --init --recursive

# Verify the submodule was added
git status

# You should see:
# - Modified .gitmodules file
# - New directory tests/fixtures/org-files
```

### Step 3: Commit the Submodule

```bash
# Stage the submodule changes
git add .gitmodules tests/fixtures/org-files

# Commit
git commit -m "Add test org files as git submodule"

# Push
git push
```

### Step 4: Verify Submodule Setup

```bash
# Check submodule status
git submodule status

# Should show something like:
# +a1b2c3d4e5f6... tests/fixtures/org-files (heads/main)

# Verify the org files are present
ls -la tests/fixtures/org-files/

# Should show:
# test_journal.org
# test_todo.org
```

## Cloning the Repository with Submodules

When someone else clones your repository, they need to initialize submodules:

```bash
# Option 1: Clone with submodules
git clone --recursive https://github.com/yourusername/org-bot.git

# Option 2: Clone normally, then initialize submodules
git clone https://github.com/yourusername/org-bot.git
cd org-bot
git submodule update --init --recursive
```

## Running Tests

### Using Taskfile (Recommended)

```bash
# Full test run with git submodule checks and verbose logging
task test

# Quick test run (faster, skips submodule checks)
task test-quick

# Watch mode (requires pytest-watch)
task test-watch
```

### Using the Test Runner Script

```bash
# Run the comprehensive test runner
./run_tests.sh
```

This script will:
1. Display git submodule status
2. Show git log from the submodule
3. Check environment variables
4. Run pytest with verbose logging

### Using Pytest Directly

```bash
# All tests with verbose output
pytest tests/ -v

# Specific test file
pytest tests/test_journal_posting.py -v

# Specific test
pytest tests/test_journal_posting.py::TestPostToGitJournal::test_post_text_message_to_journal -v

# Filter by marker
pytest tests/ -v -m journal  # Only journal tests
pytest tests/ -v -m text     # Only text message tests
pytest tests/ -v -m "journal and text"  # Journal text tests
```

## Test Output

The tests are configured for maximum verbosity. You'll see:

### Git Submodule Information
```
================================================================================
GIT SUBMODULE STATUS CHECK
================================================================================
✓ Git submodule directory found at: tests/fixtures/org-files

================================================================================
GIT STATUS (Submodule: tests/fixtures/org-files)
================================================================================
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean

================================================================================
GIT LOG (Submodule: tests/fixtures/org-files - Last 5 commits)
================================================================================
* a1b2c3d (HEAD -> main, origin/main) Initial test org files
```

### Test Execution Logs
```
2025-12-15 10:30:45.123 [INFO    ] [tests.conftest    ] STARTING TEST SESSION
2025-12-15 10:30:45.234 [INFO    ] [test_journal_posting] TEST: Post text message to journal
2025-12-15 10:30:45.235 [DEBUG   ] [test_journal_posting] Mock message created - ID: 12345
2025-12-15 10:30:45.345 [INFO    ] [test_journal_posting] Executing journal_instance.run()
2025-12-15 10:30:45.456 [DEBUG   ] [test_journal_posting] update_file called with args: ...
2025-12-15 10:30:45.567 [INFO    ] [test_journal_posting] Text message test PASSED
```

## CI/CD

Tests run automatically on:
- Push to `main`, `develop`, `claude/**`, `feature/**` branches
- Pull requests to `main` or `develop`

The GitHub Actions workflow:
- Checks out code with submodules
- Runs tests on Python 3.11 and 3.12
- Displays git submodule status and logs
- Uploads test results as artifacts

See `.github/workflows/test.yml` for details.

## Updating Test Org Files

When you need to update the test org files:

```bash
# Navigate to the submodule
cd tests/fixtures/org-files

# Make changes to the org files
vim test_journal.org

# Commit and push changes
git add .
git commit -m "Update test journal format"
git push

# Go back to org-bot root
cd ../../..

# Update the submodule reference
git add tests/fixtures/org-files
git commit -m "Update test org files submodule"
git push
```

## Environment Variables

Optional environment variables for integration tests:

```bash
# GitHub token for API access (optional - tests use mocks by default)
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"

# Test repository name (optional)
export TEST_GITHUB_REPO="yourusername/test-repo"
```

Add these to `dev.env` or set them in your CI/CD secrets.

## Troubleshooting

### "Submodule not found" warning

```bash
# Initialize the submodule
git submodule update --init --recursive

# Verify
ls -la tests/fixtures/org-files/
```

### Tests fail with import errors

```bash
# Reinstall dependencies
task sync_deps

# Or
uv sync
```

### Submodule shows uncommitted changes

```bash
# Check what changed
cd tests/fixtures/org-files
git status

# If you want to keep changes:
git add .
git commit -m "Update test files"
git push

# Then update parent repo
cd ../../..
git add tests/fixtures/org-files
git commit -m "Update submodule reference"
```

### Submodule is detached HEAD

```bash
cd tests/fixtures/org-files
git checkout main
git pull
cd ../../..
git add tests/fixtures/org-files
git commit -m "Update submodule to latest main"
```

## Test Coverage

Current test coverage:
- ✅ PostToGitJournal - text messages
- ✅ PostToGitJournal - photo messages
- ✅ PostToGitJournal - file messages
- ✅ PostToTodo - text messages
- ✅ PostToTodo - photo messages
- ✅ PostToTodo - file messages

Total: **6 tests** covering all main functionality paths.

## Next Steps

After setting up tests:

1. ✅ Set up git submodule for test org files
2. ✅ Run tests locally to verify setup
3. ✅ Push changes to trigger CI/CD
4. ✅ Verify tests pass in GitHub Actions
5. Configure GitHub secrets (optional, for integration tests):
   - `TEST_GITHUB_TOKEN`
   - `TEST_GITHUB_REPO`

For more details, see [tests/README.md](tests/README.md).
