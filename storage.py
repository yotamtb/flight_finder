import json
from pathlib import Path

OFFERS_FILE = Path("offers.json")


def load_offers():
    """
    מחזיר את כל ההצעות שנשמרו.
    """

    if not OFFERS_FILE.exists():
        return {}

    try:
        with OFFERS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_offers(offers):
    """
    שומר את כל ההצעות לקובץ.
    """

    with OFFERS_FILE.open("w", encoding="utf-8") as f:
        json.dump(
            offers,
            f,
            indent=2,
            ensure_ascii=False,
            sort_keys=True
        )
