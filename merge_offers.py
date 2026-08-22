import json
import sys
from datetime import datetime
from pathlib import Path


IGNORED_OFFER_KEYS = {
    "_site_empty",
}


def parse_datetime(value):
    """Convert an ISO datetime string to datetime."""
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except (ValueError, TypeError):
        return None


def earliest_datetime(*values):
    """Return the earliest valid datetime string."""
    parsed = [
        (parse_datetime(value), value)
        for value in values
        if value
    ]

    parsed = [
        item for item in parsed
        if item[0] is not None
    ]

    if not parsed:
        return None

    return min(parsed, key=lambda x: x[0])[1]


def latest_datetime(*values):
    """Return the latest valid datetime string."""
    parsed = [
        (parse_datetime(value), value)
        for value in values
        if value
    ]

    parsed = [
        item for item in parsed
        if item[0] is not None
    ]

    if not parsed:
        return None

    return max(parsed, key=lambda x: x[0])[1]


def get_newer_offer(offer1, offer2):
    """
    Return the offer that represents the newer snapshot,
    based on last_seen.
    """

    last_seen_1 = parse_datetime(
        offer1.get("last_seen")
    )

    last_seen_2 = parse_datetime(
        offer2.get("last_seen")
    )

    if last_seen_1 is None and last_seen_2 is None:
        return offer1

    if last_seen_1 is None:
        return offer2

    if last_seen_2 is None:
        return offer1

    if last_seen_1 >= last_seen_2:
        return offer1

    return offer2


def price_history_key(item):
    """
    Create a stable key for a price-history entry.

    Normally the date is enough. If there is no date,
    serialize the complete item.
    """

    if isinstance(item, dict):
        if item.get("date"):
            return ("date", item["date"])

        return (
            "dict",
            json.dumps(
                item,
                sort_keys=True,
                ensure_ascii=False,
            ),
        )

    return (
        "value",
        json.dumps(
            item,
            sort_keys=True,
            ensure_ascii=False,
        ),
    )


def merge_price_history(history1, history2):
    """
    Merge price histories from both sources.

    Duplicate entries are removed.
    Entries are sorted chronologically when possible.
    """

    history1 = history1 or []
    history2 = history2 or []

    merged = {}

    for item in history1 + history2:
        key = price_history_key(item)

        # If exactly the same history entry appears
        # in both files, keep only one.
        merged[key] = item

    result = list(merged.values())

    def sort_key(item):
        if isinstance(item, dict):
            parsed = parse_datetime(item.get("date"))

            if parsed:
                return (0, parsed)

        return (1, str(item))

    result.sort(key=sort_key)

    return result


def merge_offer(offer1, offer2):
    """
    Merge two versions of the same offer.
    """

    # Start with the newer snapshot.
    newer = get_newer_offer(
        offer1,
        offer2,
    )

    merged = newer.copy()

    # ---------------------------------------------------------
    # first_seen
    # ---------------------------------------------------------

    merged_first_seen = earliest_datetime(
        offer1.get("first_seen"),
        offer2.get("first_seen"),
    )

    if merged_first_seen:
        merged["first_seen"] = merged_first_seen

    # ---------------------------------------------------------
    # last_seen
    # ---------------------------------------------------------

    merged_last_seen = latest_datetime(
        offer1.get("last_seen"),
        offer2.get("last_seen"),
    )

    if merged_last_seen:
        merged["last_seen"] = merged_last_seen

    # ---------------------------------------------------------
    # price_history
    # ---------------------------------------------------------

    merged["price_history"] = merge_price_history(
        offer1.get("price_history"),
        offer2.get("price_history"),
    )

    return merged


def get_offers(data):
    """
    Extract actual flight offers.

    Metadata such as _site_empty is excluded.
    """

    offers = data.get("offers", {})

    if not isinstance(offers, dict):
        raise ValueError(
            "'offers' must be a JSON object"
        )

    return {
        key: value
        for key, value in offers.items()
        if key not in IGNORED_OFFER_KEYS
    }


def merge_offers(data1, data2):
    """
    Merge two complete offers.json structures.
    """

    offers1 = get_offers(data1)
    offers2 = get_offers(data2)

    all_keys = sorted(
        set(offers1) | set(offers2)
    )

    merged_offers = {}

    only_first = 0
    only_second = 0
    merged_count = 0

    for key in all_keys:

        if key in offers1 and key in offers2:
            merged_offers[key] = merge_offer(
                offers1[key],
                offers2[key],
            )

            merged_count += 1

        elif key in offers1:
            merged_offers[key] = offers1[key]
            only_first += 1

        else:
            merged_offers[key] = offers2[key]
            only_second += 1

    # ---------------------------------------------------------
    # Metadata
    # ---------------------------------------------------------

    # last_scan has no meaning for deciding which offer
    # is newer. We simply preserve the latest scan timestamp
    # as metadata for the resulting file.
    merged_last_scan = latest_datetime(
        data1.get("last_scan"),
        data2.get("last_scan"),
    )

    result = {
        "last_scan": merged_last_scan,
        "offers": merged_offers,
    }

    stats = {
        "first_file_offers": len(offers1),
        "second_file_offers": len(offers2),
        "merged_offers": merged_count,
        "only_first": only_first,
        "only_second": only_second,
        "total_offers": len(merged_offers),
    }

    return result, stats


def load_json(path):
    """Load JSON file."""

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_json(data, path):
    """Save JSON file."""

    path = Path(path)

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")


def validate_result(data):
    """
    Basic validation of the resulting JSON structure.
    """

    if not isinstance(data, dict):
        raise ValueError(
            "Result must be a JSON object"
        )

    if "offers" not in data:
        raise ValueError(
            "Result is missing 'offers'"
        )

    if not isinstance(data["offers"], dict):
        raise ValueError(
            "'offers' must be a JSON object"
        )

    for key, offer in data["offers"].items():

        if not isinstance(offer, dict):
            raise ValueError(
                f"Offer '{key}' is not an object"
            )

        price_history = offer.get(
            "price_history",
            [],
        )

        if not isinstance(price_history, list):
            raise ValueError(
                f"Offer '{key}' has invalid "
                f"price_history"
            )


def main():

    # if len(sys.argv) != 4:
    #     print(
    #         "\nUsage:\n"
    #         "  python merge_offers.py "
    #         "<github.json> <local.json> <output.json>\n"
    #     )
	#
    #     print(
    #         "Example:\n"
    #         "  python merge_offers.py "
    #         "github_offers.json "
    #         "local_offers.json "
    #         "merged_offers.json\n"
    #     )
	#
    #     sys.exit(1)

    github_file = '/Users/yotam.tayeb/workspace/myProjects/flight_finder/github_offers.json'
    local_file = '/Users/yotam.tayeb/workspace/myProjects/flight_finder/local_merged_offers.json'
    output_file = '/Users/yotam.tayeb/workspace/myProjects/flight_finder/github_merged_offers.json'

    print("Loading files...")

    github_data = load_json(github_file)
    local_data = load_json(local_file)

    print(
        f"GitHub file: {github_file}"
    )

    print(
        f"Local file:  {local_file}"
    )

    print()

    merged_data, stats = merge_offers(
        github_data,
        local_data,
    )

    validate_result(merged_data)

    save_json(
        merged_data,
        output_file,
    )

    print("Merge completed successfully.")
    print()

    print(
        f"Offers in GitHub:       "
        f"{stats['first_file_offers']}"
    )

    print(
        f"Offers in local file:   "
        f"{stats['second_file_offers']}"
    )

    print(
        f"Present in both:        "
        f"{stats['merged_offers']}"
    )

    print(
        f"Only in GitHub:         "
        f"{stats['only_first']}"
    )

    print(
        f"Only locally:           "
        f"{stats['only_second']}"
    )

    print(
        f"Total after merge:      "
        f"{stats['total_offers']}"
    )

    print()

    print(
        f"Output written to: {output_file}"
    )


if __name__ == "__main__":
    main()