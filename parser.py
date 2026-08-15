import re
from datetime import datetime
from bs4 import BeautifulSoup


FULL_DATE_RE = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+(?:AM|PM))"
)


def parse_datetime(value: str) -> str | None:
    try:
        dt = datetime.strptime(value, "%m/%d/%Y %I:%M:%S %p")
        return dt.isoformat()
    except Exception:
        return None


def parse_date(value: str) -> str | None:
    """
    Extracts only the date from a full date/time string.
    """
    try:
        dt = datetime.strptime(value, "%m/%d/%Y %I:%M:%S %p")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def combine_date_time(date_value: str, time_value: str) -> str | None:
    """
    Combines a YYYY-MM-DD date with an HH:MM time.
    """
    try:
        dt = datetime.strptime(
            f"{date_value} {time_value}",
            "%Y-%m-%d %H:%M"
        )
        return dt.isoformat()
    except Exception:
        return None


def parse_remaining(item):

    badge = item.select_one(".spcial_message_bottom")

    if badge is None:
        return None

    m = re.search(r"\d+", badge.get_text())

    if not m:
        return None

    return int(m.group())


def get_flight_time(item, selector):
    """
    Extracts a flight time from the given selector.
    Example:
        .flight_go .from .flight_hourTime
    """

    element = item.select_one(selector)

    if not element:
        return None

    value = element.get_text(strip=True)

    if not re.fullmatch(r"\d{1,2}:\d{2}", value):
        return None

    return value


def parse_offers(html):

    soup = BeautifulSoup(html, "lxml")

    offers = {}

    for item in soup.select("div.show_item"):

        try:

            destination = item.get("data_ga_item_name")

            if not destination:
                name_element = item.select_one(".show_item_name")

                if not name_element:
                    continue

                destination = name_element.get_text(strip=True)

            # ---------------------------------------------------------
            # Price
            # ---------------------------------------------------------

            raw_price = item.get("data_number_ga_price")

            if raw_price:
                price = float(raw_price)
            else:
                price_element = item.select_one(".show_item_total_price")

                if not price_element:
                    continue

                text = price_element.get_text(strip=True)

                price = float(
                    text.replace("$", "").replace(",", "")
                )

            # ---------------------------------------------------------
            # Dates
            # ---------------------------------------------------------

            raw_dates = item.get("data_ga_item_brand", "")

            dates = FULL_DATE_RE.findall(raw_dates)

            departure_date = None
            return_date = None

            if len(dates) >= 2:
                # The site's data attribute is:
                #
                # return date/time - departure date/time
                #
                # We only use it for the DATE.
                return_date = parse_date(dates[0])
                departure_date = parse_date(dates[1])

            # ---------------------------------------------------------
            # Flight times
            # ---------------------------------------------------------

            departure_time = get_flight_time(
                item,
                ".flight_go .from .flight_hourTime"
            )

            return_time = get_flight_time(
                item,
                ".flight_back .from .flight_hourTime"
            )

            # ---------------------------------------------------------
            # Build complete datetimes
            # ---------------------------------------------------------

            departure = None
            returning = None

            if departure_date and departure_time:
                departure = combine_date_time(
                    departure_date,
                    departure_time
                )

            if return_date and return_time:
                returning = combine_date_time(
                    return_date,
                    return_time
                )

            # ---------------------------------------------------------
            # Fallback
            # ---------------------------------------------------------

            # If the detailed flight information is unavailable,
            # fall back to the old data attribute parsing.

            if departure is None and len(dates) >= 2:
                departure = parse_datetime(dates[1])

            if returning is None and len(dates) >= 2:
                returning = parse_datetime(dates[0])

            # ---------------------------------------------------------
            # Image
            # ---------------------------------------------------------

            image = None

            img = item.select_one("img")

            if img:
                image = img.get("src")

            # ---------------------------------------------------------
            # Remaining seats
            # ---------------------------------------------------------

            remaining = parse_remaining(item)

            # ---------------------------------------------------------
            # Unique offer key
            # ---------------------------------------------------------

            offer_key = f"{destination}|{departure}|{returning}"

            offers[offer_key] = {
                "destination": destination,
                "departure": departure,
                "return": returning,
                "price": price,
                "remaining": remaining,
                "image": image,
            }

        except Exception as ex:
            print("Parser error:", ex)

    return offers