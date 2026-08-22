from copy import deepcopy


SITE_EMPTY_KEY = "_site_empty"


def merge_offer_records(remote, local):
    """
    Merge two versions of the same offer.

    The flight identity is already represented by the dictionary key:
        destination|departure|return

    Metadata is merged rather than blindly overwritten.
    """

    merged = deepcopy(remote)

    # ---------------------------------------------------------
    # Basic offer data
    # ---------------------------------------------------------

    for field in (
        "destination",
        "departure",
        "return",
        "image",
        "price",
        "remaining",
    ):
        if field not in merged and field in local:
            merged[field] = local[field]

    # ---------------------------------------------------------
    # first_seen
    #
    # Keep the earliest known timestamp.
    # ---------------------------------------------------------

    remote_first = remote.get("first_seen")
    local_first = local.get("first_seen")

    if remote_first and local_first:
        merged["first_seen"] = min(
            remote_first,
            local_first,
        )

    elif local_first:
        merged["first_seen"] = local_first

    elif remote_first:
        merged["first_seen"] = remote_first

    # ---------------------------------------------------------
    # last_seen
    #
    # Keep the latest known timestamp.
    # ---------------------------------------------------------

    remote_last = remote.get("last_seen")
    local_last = local.get("last_seen")

    if remote_last and local_last:
        merged["last_seen"] = max(
            remote_last,
            local_last,
        )

    elif local_last:
        merged["last_seen"] = local_last

    elif remote_last:
        merged["last_seen"] = remote_last

    # ---------------------------------------------------------
    # active
    #
    # If either copy currently knows the offer is active,
    # preserve active=True.
    #
    # This is important when local and GitHub runs happened
    # at slightly different times.
    # ---------------------------------------------------------

    merged["active"] = (
        remote.get("active", False)
        or local.get("active", False)
    )

    # ---------------------------------------------------------
    # Price history
    # ---------------------------------------------------------

    history = []

    for entry in (
        remote.get("price_history", [])
        + local.get("price_history", [])
    ):

        if entry not in history:
            history.append(entry)

    history.sort(
        key=lambda x: x.get("date", "")
    )

    merged["price_history"] = history

    # ---------------------------------------------------------
    # Current price
    #
    # If both copies have different prices, use the price
    # from the copy with the latest last_seen.
    # ---------------------------------------------------------

    if remote_last and local_last:

        if local_last >= remote_last:
            merged["price"] = local.get(
                "price",
                remote.get("price"),
            )
        else:
            merged["price"] = remote.get(
                "price",
                local.get("price"),
            )

    elif local.get("price") is not None:
        merged["price"] = local["price"]

    # ---------------------------------------------------------
    # Remaining seats
    #
    # Same principle: use the value from the most recently
    # observed copy.
    # ---------------------------------------------------------

    if remote_last and local_last:

        if local_last >= remote_last:
            merged["remaining"] = local.get(
                "remaining",
                remote.get("remaining"),
            )
        else:
            merged["remaining"] = remote.get(
                "remaining",
                local.get("remaining"),
            )

    elif "remaining" in local:
        merged["remaining"] = local["remaining"]

    return merged


def merge_offers(remote_offers, local_offers):
    """
    Merge two offers dictionaries.

    Returns:
        merged offers dictionary
    """

    merged = {}

    all_keys = (
        set(remote_offers)
        | set(local_offers)
    )

    for key in all_keys:

        # -----------------------------------------------------
        # Special metadata key
        # -----------------------------------------------------

        if key == SITE_EMPTY_KEY:

            merged[key] = (
                remote_offers.get(key, False)
                and local_offers.get(key, False)
            )

            continue

        # -----------------------------------------------------
        # Only remote
        # -----------------------------------------------------

        if key not in local_offers:

            merged[key] = deepcopy(
                remote_offers[key]
            )

            continue

        # -----------------------------------------------------
        # Only local
        # -----------------------------------------------------

        if key not in remote_offers:

            merged[key] = deepcopy(
                local_offers[key]
            )

            continue

        # -----------------------------------------------------
        # Exists in both
        # -----------------------------------------------------

        merged[key] = merge_offer_records(
            remote_offers[key],
            local_offers[key],
        )

    return merged