import json
import os
import subprocess
import tempfile
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parent.parent

GIT_REMOTE = "origin"
GIT_BRANCH = "main"


def _git_env():
    """Create Git environment using GITHUB_TOKEN."""

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

    os.chmod(askpass.name, 0o700)

    env = os.environ.copy()
    env["GIT_ASKPASS"] = askpass.name
    env["GIT_TERMINAL_PROMPT"] = "0"

    return env, askpass.name


def _run_git(*args):
    """Run a Git command."""

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

    if result.returncode != 0:
        raise RuntimeError(
            f"Git command failed: git {' '.join(args)}"
        )

    return result


def fetch():
    """Fetch latest remote branch."""

    print("Fetching latest GitHub state...")

    _run_git(
        "fetch",
        GIT_REMOTE,
        GIT_BRANCH,
    )


def read_file(path):
    """
    Return the content of a file from origin/main.

    The working tree is not modified.
    """

    result = _run_git(
        "show",
        f"{GIT_REMOTE}/{GIT_BRANCH}:{path}",
    )

    return result.stdout


def commit_and_push(path, message):
    """
    Commit and push exactly one file.
    """

    result = _run_git(
        "status",
        "--porcelain",
        "--",
        path,
    )

    if not result.stdout.strip():
        print(f"{path} hasn't changed.")
        return False

    _run_git(
        "add",
        "--",
        path,
    )

    result = _run_git(
        "diff",
        "--cached",
        "--name-only",
    )

    staged = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    if staged != [path]:
        raise RuntimeError(
            f"Refusing to commit unexpected files: {staged}"
        )

    _run_git(
        "commit",
        "-m",
        message,
    )

    _run_git(
        "push",
        GIT_REMOTE,
        GIT_BRANCH,
    )

    print(f"{path} pushed successfully.")

    return True