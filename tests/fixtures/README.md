# Test Fixtures

This directory contains test fixtures for the org-bot tests.

## Structure

- `org-files/` - Org-mode files used as test repositories (git submodule)
- `images/` - Sample images for testing picture message handling
- `files/` - Sample files for testing file attachment handling

## Git Submodule

The `org-files/` directory should be set up as a git submodule pointing to your test org files repository.

To add the submodule:
```bash
git submodule add <your-repo-url> tests/fixtures/org-files
git submodule update --init --recursive
```

## Expected Org Files

The tests expect the following org files in the `org-files/` directory:
- `test_journal.org` - For journal entry tests
- `test_todo.org` - For TODO item tests
