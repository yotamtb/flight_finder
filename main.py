import argparse
import importlib
import json
from pathlib import Path

from utils import git_sync
from utils.json_sync import merge_offers


REPO_DIR = Path(__file__).resolve().parent


MONITORS = {
    "tustus": {
        "module": "tustus.monitor",
        "data_file": "tustus/offers.json",
    },
}


def get_monitor(name):
    if name not in MONITORS:
        raise ValueError(
            f"Unknown monitor: {name}"
        )

    config = MONITORS[name]

    module = importlib.import_module(
        config["module"]
    )

    return module, config


def load_remote_offers(data_file):
    """
    Read offers from GitHub.
    """

    raw = git_sync.read_file(data_file)

    data = json.loads(raw)

    return data.get("offers", {})


def sync_data(data_file):
    """
    Merge GitHub's JSON with the local JSON.
    """

    from importlib import import_module

    # For now storage is site-owned, so derive it from
    # the monitor configuration.
    if data_file == "tustus/offers.json":
        storage = import_module(
            "tustus.storage"
        )
    else:
        raise RuntimeError(
            f"No storage module configured for {data_file}"
        )

    local_offers = storage.load_offers()
    remote_offers = load_remote_offers(data_file)

    merged = merge_offers(
        remote_offers,
        local_offers,
    )

    storage.save_offers(merged)

    print(
        f"Synchronized {len(merged)} offers."
    )


def run_monitor(module):
    print("=" * 60)
    print("RUNNING MONITOR")
    print("=" * 60)

    module.scan()


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "monitor",
        choices=MONITORS.keys(),
    )

    args = parser.parse_args()

    monitor, config = get_monitor(
        args.monitor
    )

    data_file = config["data_file"]

    try:

        # --------------------------------------------------
        # 1. Git fetch
        # --------------------------------------------------

        git_sync.fetch()

        # --------------------------------------------------
        # 2. Merge remote + local data
        # --------------------------------------------------

        sync_data(data_file)

        # --------------------------------------------------
        # 3. Run site monitor
        # --------------------------------------------------

        run_monitor(monitor)

        # --------------------------------------------------
        # 4. Push only this monitor's data file
        # --------------------------------------------------

        git_sync.commit_and_push(
            data_file,
            f"Update {args.monitor} offers",
        )

    except Exception as e:

        print(f"ERROR: {e}")
        raise


if __name__ == "__main__":
    main()