import os
from datetime import datetime
from playwright.sync_api import sync_playwright

from parser import parse_offers
from storage import load_offers, save_offers
from telegram import send_message

URL = "https://www.tustus.co.il/Arkia/Home"


def check_offers():

    previous = load_offers()

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )

        page = browser.new_page()

        page.goto(URL, wait_until="networkidle")

        page.wait_for_timeout(5000)

        html = page.content()

        browser.close()

    current = parse_offers(html)

    notifications = []

    for offer_id, offer in current.items():

        if offer_id not in previous:

            notifications.append(
                f"""🆕 הצעה חדשה!

📍 {offer['destination']}

🛫 {offer['departure']}
🛬 {offer['return']}

💰 ${offer['price']}"""
            )

        else:

            old = previous[offer_id]

            if offer["price"] < old["price"]:

                notifications.append(
                    f"""📉 ירידת מחיר!

📍 {offer['destination']}

🛫 {offer['departure']}
🛬 {offer['return']}

💰 ${old['price']} ➜ ${offer['price']}"""
                )

            if offer["remaining"] < old["remaining"]:

                notifications.append(
                    f"""⚠️ נשארו פחות מקומות

📍 {offer['destination']}

נותרו רק {offer['remaining']} מקומות"""
                )

        offer["last_seen"] = datetime.utcnow().isoformat()

    save_offers(current)

    for msg in notifications:
        send_message(msg)

    print(
        f"[{datetime.now()}] "
        f"Offers: {len(current)} "
        f"Notifications: {len(notifications)}"
    )


if __name__ == "__main__":
    check_offers()
