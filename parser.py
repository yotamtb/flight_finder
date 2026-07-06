import re
from bs4 import BeautifulSoup


PRICE_RE = re.compile(r"\$(\d+)")
DATE_RE = re.compile(r"(\d{2}/\d{2})")


def clean(text):
    return " ".join(text.split())


def parse_price(text):
    m = PRICE_RE.search(text)
    return int(m.group(1)) if m else None


def parse_dates(text):

    dates = DATE_RE.findall(text)

    if len(dates) >= 2:
        return dates[0], dates[1]

    return None, None


def parse_remaining(item):

    badge = item.select_one(".spcial_message_bottom")

    if not badge:
        return None

    m = re.search(r"(\d+)", badge.get_text())

    if not m:
        return None

    return int(m.group(1))


def parse_offers(html):

    soup = BeautifulSoup(html, "html.parser")

    offers = {}

    for item in soup.select("div.show_item"):

        try:

            offer_id = item["ite_item"]

            destination = clean(
                item.select_one(".show_item_name").get_text()
            )

            price = parse_price(
                item.select_one(".show_item_total_price").get_text()
            )

            details = clean(
                item.select_one(".show_item_details").get_text(" ")
            )

            departure, ret = parse_dates(details)

            remaining = parse_remaining(item)

            offers[offer_id] = {
                "destination": destination,
                "departure": departure,
                "return": ret,
                "price": price,
                "remaining": remaining,
            }

        except Exception as e:

            print("Could not parse offer:", e)

    return offers
