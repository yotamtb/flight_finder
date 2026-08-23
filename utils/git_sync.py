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
GITHUB_WORKFLOW = "monitor_3.yml"

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

def _run_git(*args, check=True):
    """
    Execute a Git command inside the repository.
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

    if result.stdout.strip():
        print(result.stdout.strip())

    if result.stderr.strip():
        print(result.stderr.strip())

    if check and result.returncode != 0:

        raise RuntimeError(
            f"Git command failed: git {' '.join(args)}"
        )

    return result


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
    )


def read_file(path):
    """
    Read a file directly from origin/main.

    This does not modify the working tree.
    """

    result = _run_git(
        "show",
        f"{GIT_REMOTE}/{GIT_BRANCH}:{path}",
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

    _run_git(
        "reset",
        "HEAD",
        "--",
    )

    _run_git(
        "add",
        "--",
        path,
    )


def get_staged_files():
    """
    Return the files currently staged.
    """

    result = _run_git(
        "diff",
        "--cached",
        "--name-only",
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
    )


def commit(message):
    """
    Commit the currently staged changes.
    """

    _run_git(
        "commit",
        "-m",
        message,
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
    )

    return result.returncode == 0


def reset_to_remote():
    """
    Reset the local branch to origin/main.

    Uses --mixed so the working-tree changes are preserved
    while local commits are removed from the branch.
    """

    _run_git(
        "reset",
        "--mixed",
        f"{GIT_REMOTE}/{GIT_BRANCH}",
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

    # These are all states in which the workflow
    # has not completed yet.
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