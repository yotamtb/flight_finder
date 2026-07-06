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


def parse_remaining(item):

    badge = item.select_one(".spcial_message_bottom")

    if badge is None:
        return None

    m = re.search(r"\d+", badge.get_text())

    if not m:
        return None

    return int(m.group())


def parse_offers(html):

    soup = BeautifulSoup(html, "lxml")

    offers = {}

    for item in soup.select("div.show_item"):

        try:

            destination = item.get("data_ga_item_name")

            if not destination:
                destination = item.select_one(".show_item_name").get_text(strip=True)

            raw_price = item.get("data_number_ga_price")

            if raw_price:
                price = float(raw_price)
            else:
                text = item.select_one(".show_item_total_price").get_text(strip=True)
                price = float(text.replace("$", "").replace(",", ""))

            raw_dates = item.get("data_ga_item_brand", "")

            dates = FULL_DATE_RE.findall(raw_dates)

            departure = None
            returning = None

            if len(dates) == 2:
                returning = parse_datetime(dates[0])
                departure = parse_datetime(dates[1])

            image = None

            img = item.select_one("img")

            if img:
                image = img.get("src")

            remaining = parse_remaining(item)

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
