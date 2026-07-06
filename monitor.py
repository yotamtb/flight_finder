from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

from parser import parse_offers
from storage import load_offers, save_offers
from telegram import send_message

URL = "https://www.tustus.co.il/Arkia/Home"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def merge_offers(previous, current):

    now = utc_now()

    merged = {}

    notifications = []

    # הצעות חדשות / קיימות
    for key, offer in current.items():

        if key not in previous:

            offer["first_seen"] = now
            offer["last_seen"] = now
            offer["active"] = True

            offer["price_history"] = [
                {
                    "date": now,
                    "price": offer["price"]
                }
            ]

            notifications.append(
                f"""🆕 הצעה חדשה!

📍 {offer['destination']}

🛫 {offer['departure']}
🛬 {offer['return']}

💰 ${offer['price']}"""
            )

        else:

            old = previous[key]

            offer["first_seen"] = old.get("first_seen", now)
            offer["last_seen"] = now
            offer["active"] = True

            history = old.get("price_history", [])

            old_price = old.get("price")

            if old_price != offer["price"]:

                history.append(
                    {
                        "date": now,
                        "price": offer["price"]
                    }
                )

                if offer["price"] < old_price:

                    notifications.append(
                        f"""📉 ירידת מחיר!

📍 {offer['destination']}

🛫 {offer['departure']}
🛬 {offer['return']}

💰 ${old_price} → ${offer['price']}"""
                    )

            offer["price_history"] = history

            old_remaining = old.get("remaining")
            new_remaining = offer.get("remaining")

            if (
                old_remaining is not None
                and new_remaining is not None
                and new_remaining < old_remaining
            ):

                notifications.append(
                    f"""⚠️ פחות מקומות זמינים

📍 {offer['destination']}

נותרו רק {new_remaining} מקומות"""
                )

        merged[key] = offer

    # הצעות שנעלמו
    for key, offer in previous.items():

        if key in merged:
            continue

        offer["active"] = False

        merged[key] = offer

        notifications.append(
            f"""❌ ההצעה ירדה מהאתר

📍 {offer['destination']}

🛫 {offer['departure']}
🛬 {offer['return']}"""
        )

    return merged, notifications


def check_offers():

    previous = load_offers()

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox"],
        )

        page = browser.new_page()

        page.goto(URL, wait_until="networkidle")

        page.wait_for_timeout(3000)

        html = page.content()

        browser.close()

    current = parse_offers(html)

    merged, notifications = merge_offers(previous, current)

    save_offers(merged)

    for message in notifications:
        send_message(message)

    print("=" * 60)
    print(f"Scan completed: {utc_now()}")
    print(f"Offers online : {len(current)}")
    print(f"Offers stored : {len(merged)}")
    print(f"Notifications : {len(notifications)}")
    print("=" * 60)


if __name__ == "__main__":
    check_offers()
