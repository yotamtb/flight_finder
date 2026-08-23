import os
import subprocess
import tempfile
from pathlib import Path

import requests


# ============================================================
# Repository configuration
# ============================================================

REPO_DIR = Path(__file__).resolve().parent.parent

GIT_REMOTE = "origin"
GIT_BRANCH = "main"


# ============================================================
# GitHub configuration
# ============================================================

GITHUB_OWNER = "yotamtb"
GITHUB_REPO = "flight_finder"

# Change this if your workflow has a different filename.
GITHUB_WORKFLOW = "monitor.yml"

GITHUB_API_URL = "https://api.github.com"


# ============================================================
# Git environment
# ============================================================

def _git_env():
    """
    Build the environment used for authenticated Git commands.

    Authentication is done using GITHUB_TOKEN through
    Git's GIT_ASKPASS mechanism.
    """

    token = os.environ.get("GITHUB_TOKEN")

    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN environment variable is not set."
        )

    askpass = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".sh",
        delete=False,
    )

    askpass.write(
        """#!/bin/sh
case "$1" in
    *Username*)
        printf '%s\\n' 'x-access-token'
        ;;
    *Password*)
        printf '%s\\n' "$GITHUB_TOKEN"
        ;;
esac
"""
    )

    askpass.close()

    os.chmod(
        askpass.name,
        0o700,
    )

    env = os.environ.copy()

    env["GIT_ASKPASS"] = askpass.name
    env["GIT_TERMINAL_PROMPT"] = "0"

    return env, askpass.name


# ============================================================
# Git command execution
# ============================================================

def _run_git(*args, check=True, print_stdout=True):
    """
    Execute a Git command inside the repository.

    Args:
        check:
            Raise an exception if Git returns a non-zero exit code.

        print_stdout:
            Whether to print stdout to the console.

            This is disabled for commands such as `git show`
            where stdout contains data that should not appear
            in the log.
    """

    env, askpass_path = _git_env()

    try:

        result = subprocess.run(
            ["git", *args],
            cwd=REPO_DIR,
            text=True,
            capture_output=True,
            env=env,
        )

    finally:

        try:
            os.unlink(askpass_path)
        except OSError:
            pass

    if print_stdout and result.stdout.strip():

        print(
            result.stdout.strip()
        )

    # Always print stderr.
    # This includes useful Git messages and errors.

    if result.stderr.strip():

        print(
            result.stderr.strip()
        )

    if check and result.returncode != 0:

        raise RuntimeError(
            f"Git command failed: git {' '.join(args)}"
        )

    return result


# ============================================================
# Git identity
# ============================================================

def configure_git_identity():
    """
    Configure the Git identity used for commits.

    The configuration is repository-local and does not
    modify the global Git configuration.
    """

    _run_git(
        "config",
        "user.name",
        "github-actions[bot]",
        print_stdout=False,
    )

    _run_git(
        "config",
        "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com",
        print_stdout=False,
    )


# ============================================================
# Git operations
# ============================================================

def fetch():
    """
    Fetch the latest remote branch.
    """

    _run_git(
        "fetch",
        GIT_REMOTE,
        GIT_BRANCH,
        print_stdout=False,
    )


def read_file(path):
    """
    Read a file directly from origin/main.

    This does not modify the working tree.

    stdout is intentionally suppressed so that the contents
    of files such as offers.json are not written to cron.log.
    """

    result = _run_git(
        "show",
        f"{GIT_REMOTE}/{GIT_BRANCH}:{path}",
        print_stdout=False,
    )

    return result.stdout


def has_changes(path):
    """
    Check whether a specific file has local changes.
    """

    result = _run_git(
        "status",
        "--porcelain",
        "--",
        path,
        print_stdout=False,
    )

    return bool(
        result.stdout.strip()
    )


def stage_file(path):
    """
    Stage exactly one file.

    First clears any existing staged changes so that
    an unrelated staged file cannot accidentally be
    included in our commit.
    """

    # Clear existing staging.

    _run_git(
        "reset",
        "HEAD",
        "--",
        print_stdout=False,
    )

    # Stage only the requested file.

    _run_git(
        "add",
        "--",
        path,
        print_stdout=False,
    )


def get_staged_files():
    """
    Return the files currently staged.
    """

    result = _run_git(
        "diff",
        "--cached",
        "--name-only",
        print_stdout=False,
    )

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def reset_staging():
    """
    Remove everything from the Git staging area.

    Does not modify working-tree files.
    """

    _run_git(
        "reset",
        "HEAD",
        "--",
        print_stdout=False,
    )


def commit(message):
    """
    Commit the currently staged changes.
    """

    configure_git_identity()

    _run_git(
        "commit",
        "-m",
        message,
        print_stdout=False,
    )


def push():
    """
    Push the current branch.

    Returns:
        True  - push succeeded
        False - push was rejected
    """

    result = _run_git(
        "push",
        GIT_REMOTE,
        GIT_BRANCH,
        check=False,
        print_stdout=False,
    )

    return result.returncode == 0


def reset_to_remote():
    """
    Reset the local branch to origin/main.

    Uses --mixed so working-tree changes are preserved
    while local commits are removed from the branch.
    """

    _run_git(
        "reset",
        "--mixed",
        f"{GIT_REMOTE}/{GIT_BRANCH}",
        print_stdout=False,
    )


# ============================================================
# GitHub Actions
# ============================================================

def github_action_is_running():
    """
    Check whether the configured GitHub Actions workflow
    currently has an active run on the main branch.

    Returns:
        True  - an active workflow run exists
        False - no active workflow run exists

    Raises:
        RuntimeError if the GitHub API request fails.
    """

    token = os.environ.get("GITHUB_TOKEN")

    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN environment variable is not set."
        )

    url = (
        f"{GITHUB_API_URL}/repos/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/"
        f"actions/workflows/"
        f"{GITHUB_WORKFLOW}/runs"
    )

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2026-03-10",
    }

    active_statuses = (
        "in_progress",
        "queued",
        "requested",
        "waiting",
        "pending",
    )

    for status in active_statuses:

        params = {
            "branch": GIT_BRANCH,
            "status": status,
            "per_page": 1,
        }

        try:

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=20,
            )

            response.raise_for_status()

        except requests.RequestException as e:

            raise RuntimeError(
                "GitHub API request failed: "
                f"{e}"
            ) from e

        data = response.json()

        if data.get("workflow_runs"):

            return True

    return False