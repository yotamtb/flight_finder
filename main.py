import argparse
import importlib
import os
import sys

from utils import git_sync
from utils.json_sync import merge_offers


MAX_PUSH_ATTEMPTS = 3


MONITORS = {
    "tustus": {
        "module": "tustus.monitor",
        "storage": "tustus.storage",
        "data_file": "tustus/offers.json",
    },
}


def is_github_actions():
    """
    Returns True when running inside GitHub Actions.
    """

    return os.environ.get("GITHUB_ACTIONS") == "true"


def get_monitor(name):
    """
    Load the monitor and its storage module.
    """

    if name not in MONITORS:
        raise ValueError(
            f"Unknown monitor '{name}'. "
            f"Available monitors: {', '.join(MONITORS)}"
        )

    config = MONITORS[name]

    monitor = importlib.import_module(
        config["module"]
    )

    storage = importlib.import_module(
        config["storage"]
    )

    return monitor, storage, config


def load_remote_offers(data_file):
    """
    Load the offers dictionary from origin/main.
    """

    raw = git_sync.read_file(data_file)

    data = __import__("json").loads(raw)

    if "offers" not in data:
        raise RuntimeError(
            f"Remote file '{data_file}' "
            "does not contain an 'offers' object."
        )

    return data["offers"]


def synchronize_data(storage, data_file):
    """
    Merge the local database with the remote database.
    """

    print("=" * 60)
    print("SYNCHRONIZING DATA")
    print("=" * 60)

    local_offers = storage.load_offers()

    try:
        remote_offers = load_remote_offers(
            data_file
        )

    except Exception as e:

        print(
            f"Could not read remote {data_file}: {e}"
        )

        print(
            "Continuing with local data."
        )

        remote_offers = {}

    print(
        f"Local offers : {len(local_offers)}"
    )

    print(
        f"Remote offers: {len(remote_offers)}"
    )

    merged_offers = merge_offers(
        remote_offers,
        local_offers,
    )

    print(
        f"Merged offers: {len(merged_offers)}"
    )

    storage.save_offers(
        merged_offers
    )


def run_monitor(monitor, name):
    """
    Run the selected monitor.
    """

    print("=" * 60)
    print(f"RUNNING MONITOR: {name}")
    print("=" * 60)

    monitor.scan()


def push_with_retry(
    storage,
    data_file,
    monitor_name,
):
    """
    Commit and push the monitor's data.

    If another process pushes first, fetch the new
    remote state, merge it with our local data,
    reset our branch to the remote branch, and
    create a new commit.
    """

    commit_message = (
        f"Update {monitor_name} offers"
    )

    for attempt in range(
        1,
        MAX_PUSH_ATTEMPTS + 1,
    ):

        print(
            f"Push attempt "
            f"{attempt}/{MAX_PUSH_ATTEMPTS}"
        )

        # --------------------------------------------------
        # Check for changes
        # --------------------------------------------------

        if not git_sync.has_changes(
            data_file
        ):

            print(
                f"{data_file} hasn't changed. "
                "Nothing to push."
            )

            return

        # --------------------------------------------------
        # Stage ONLY the data file
        # --------------------------------------------------

        git_sync.stage_file(
            data_file
        )

        staged_files = (
            git_sync.get_staged_files()
        )

        if staged_files != [data_file]:

            git_sync.reset_staging()

            raise RuntimeError(
                "Refusing to commit unexpected "
                f"files: {staged_files}"
            )

        # --------------------------------------------------
        # Commit
        # --------------------------------------------------

        git_sync.commit(
            commit_message
        )

        # --------------------------------------------------
        # Push
        # --------------------------------------------------

        if git_sync.push():

            print(
                "offers.json pushed successfully."
            )

            return

        # --------------------------------------------------
        # Push rejected
        # --------------------------------------------------

        if attempt == MAX_PUSH_ATTEMPTS:

            raise RuntimeError(
                "Git push failed after "
                f"{MAX_PUSH_ATTEMPTS} attempts."
            )

        print(
            "Remote branch changed while the "
            "monitor was running."
        )

        # --------------------------------------------------
        # Fetch latest remote state
        # --------------------------------------------------

        git_sync.fetch()

        remote_offers = (
            load_remote_offers(
                data_file
            )
        )

        local_offers = (
            storage.load_offers()
        )

        # --------------------------------------------------
        # Merge remote + local
        # --------------------------------------------------

        merged_offers = merge_offers(
            remote_offers,
            local_offers,
        )

        storage.save_offers(
            merged_offers
        )

        # --------------------------------------------------
        # Reset local branch to origin/main
        # --------------------------------------------------

        git_sync.reset_to_remote()

        print(
            "Local branch synchronized with remote. "
            "Retrying push..."
        )


def main():

    parser = argparse.ArgumentParser(
        description="Flight Finder monitor"
    )

    parser.add_argument(
        "monitor",
        choices=MONITORS.keys(),
        help="Monitor to run",
    )

    args = parser.parse_args()

    # ------------------------------------------------------
    # GitHub Actions concurrency check
    #
    # Only local executions perform this check.
    # A GitHub Actions run obviously must not block itself.
    # ------------------------------------------------------

    if not is_github_actions():

        try:

            if git_sync.github_action_is_running():

                print(
                    "GitHub Actions is currently running."
                )

                print(
                    "Skipping local run."
                )

                return

        except Exception as e:

            # Do NOT silently skip the local monitor if
            # GitHub's status cannot be determined.
            print(
                "WARNING: Could not determine whether "
                f"GitHub Actions is running: {e}"
            )

            print(
                "Continuing with local run."
            )

    monitor, storage, config = get_monitor(
        args.monitor
    )

    data_file = config["data_file"]

    try:

        # --------------------------------------------------
        # 1. Fetch latest GitHub state
        # --------------------------------------------------

        print("=" * 60)
        print("GIT FETCH")
        print("=" * 60)

        git_sync.fetch()

        # --------------------------------------------------
        # 2. Merge remote + local data
        # --------------------------------------------------

        synchronize_data(
            storage,
            data_file,
        )

        # --------------------------------------------------
        # 3. Run monitor
        # --------------------------------------------------

        run_monitor(
            monitor,
            args.monitor,
        )

        # --------------------------------------------------
        # 4. Commit + push
        # --------------------------------------------------

        print("=" * 60)
        print("GIT PUSH")
        print("=" * 60)

        push_with_retry(
            storage,
            data_file,
            args.monitor,
        )

    except Exception as e:

        print(
            f"\nERROR: {e}"
        )

        sys.exit(1)


if __name__ == "__main__":
    main()