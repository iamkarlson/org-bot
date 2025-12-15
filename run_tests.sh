#!/bin/bash

# Test runner for org-bot with verbose logging and git submodule checks
# This script:
# 1. Checks git submodule status
# 2. Displays git log for the submodule
# 3. Runs pytest with verbose output and detailed logging

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Print section header
print_header() {
    echo ""
    echo -e "${CYAN}================================================================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}================================================================================${NC}"
    echo ""
}

# Print info message
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Print success message
print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Print warning message
print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Print error message
print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Start of test run
print_header "ORG-BOT TEST RUNNER"

print_info "Starting test execution at $(date)"
print_info "Working directory: $(pwd)"
print_info "Python version: $(python --version 2>&1)"
print_info "Pytest version: $(pytest --version 2>&1 | head -n 1)"

# Check if tests/fixtures/org-files exists as a submodule
SUBMODULE_PATH="tests/fixtures/org-files"

print_header "GIT SUBMODULE STATUS CHECK"

if [ -d "$SUBMODULE_PATH/.git" ] || [ -f "$SUBMODULE_PATH/.git" ]; then
    print_success "Git submodule directory found at: $SUBMODULE_PATH"

    # Change to submodule directory
    print_info "Entering submodule directory: $SUBMODULE_PATH"
    cd "$SUBMODULE_PATH"

    # Display git status
    print_header "GIT STATUS (Submodule: $SUBMODULE_PATH)"
    git status

    # Display git log
    print_header "GIT LOG (Submodule: $SUBMODULE_PATH - Last 5 commits)"
    git log --oneline --decorate --graph -n 5 || print_warning "Unable to fetch git log"

    # Display current commit details
    print_header "CURRENT COMMIT DETAILS (Submodule)"
    git log -1 --stat || print_warning "Unable to fetch commit details"

    # Return to root directory
    cd - > /dev/null
    print_info "Returned to root directory"
else
    print_warning "Git submodule not found at: $SUBMODULE_PATH"
    print_warning "The submodule should be initialized with:"
    print_warning "  git submodule add <your-repo-url> $SUBMODULE_PATH"
    print_warning "  git submodule update --init --recursive"
    print_warning ""
    print_warning "Tests will continue but may fail if they depend on submodule fixtures"
fi

# Display main repository git status
print_header "MAIN REPOSITORY GIT STATUS"
git status

# Check if .env or test environment variables are set
print_header "ENVIRONMENT VARIABLES CHECK"

if [ -f "dev.env" ]; then
    print_info "Found dev.env file"
    print_info "Loading environment variables from dev.env"
    set -a
    source dev.env
    set +a
else
    print_warning "No dev.env file found"
fi

# Check for required test environment variables
if [ -n "$GITHUB_TOKEN" ]; then
    print_success "GITHUB_TOKEN is set"
else
    print_warning "GITHUB_TOKEN is not set (tests will use mock token)"
fi

if [ -n "$TEST_GITHUB_REPO" ]; then
    print_success "TEST_GITHUB_REPO is set to: $TEST_GITHUB_REPO"
else
    print_warning "TEST_GITHUB_REPO is not set (tests will use mock repo)"
fi

# Run pytest with verbose output
print_header "RUNNING PYTEST"

print_info "Test command: pytest tests/ -v"
print_info "Pytest will run with:"
print_info "  - Verbose output (-v)"
print_info "  - Live logging (--log-cli=true)"
print_info "  - Debug level logs (--log-cli-level=DEBUG)"
print_info "  - No output capture (--capture=no)"
print_info ""

# Run the tests
if pytest tests/ -v; then
    print_header "TEST RESULTS"
    print_success "All tests passed!"
    exit 0
else
    print_header "TEST RESULTS"
    print_error "Some tests failed!"
    exit 1
fi
