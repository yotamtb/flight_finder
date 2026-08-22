import json
from pathlib import Path


DATA_FILE = Path(__file__).resolve().parent / "offers.json"


def load_data():
    """
    Loads the entire database.

    Returns:
    {
        "offers": { ... }
    }
    """

    if not DATA_FILE.exists():
        return {
            "offers": {}
        }

    try:

        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if "offers" not in data:
            data["offers"] = {}

        return data

    except Exception:

        return {
            "offers": {}
        }


def load_offers():
    """
    Returns only the offers dictionary.
    """

    return load_data()["offers"]


def save_offers(offers):
    """
    Saves offers.
    """

    data = {
        "offers": offers
    }

    with DATA_FILE.open("w", encoding="utf-8") as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
            sort_keys=True
        )


def get_offer(offer_key):
    """
    Returns a single offer or None.
    """

    return load_offers().get(offer_key)


def offer_exists(offer_key):
    """
    Checks if an offer already exists.
    """

    return offer_key in load_offers()