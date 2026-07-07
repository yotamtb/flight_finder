from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

from parser import parse_offers
from storage import load_offers, save_offers
from telegram import send_message

URL = "https://www.tustus.co.il/Arkia/Home"


def local_now():
    return datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat()


def date_range_text(departure, return_date):
    try:
        start = datetime.fromisoformat(departure)
        end = datetime.fromisoformat(return_date)

        weekdays = [
            "שני",
            "שלישי",
            "רביעי",
            "חמישי",
            "שישי",
            "שבת",
            "ראשון",
        ]

        return f"{weekdays[start.weekday()]} עד {weekdays[end.weekday()]}"

    except Exception:
        return ""


def merge_offers(previous, current):
    now = local_now()

    merged = {}
    notifications = []

    # New / existing offers
    for key, offer in current.items():

        if key not in previous:

            offer["first_seen"] = now
            offer["last_seen"] = now
            offer["active"] = True

            offer["price_history"] = [
                {
                    "date": now,
                    "price": offer["price"],
                }
            ]

            notifications.append(
                f"""🆕 {offer['destination']}
🛫 {offer['departure']}
🛬 {offer['return']}
📅 {date_range_text(offer['departure'], offer['return'])}
💰 ${offer['price']}"""
            )

        else:

            old = previous[key]

            # הצעה שחזרה אחרי שנעלמה
            if not old.get("active", True):

                notifications.append(
                    f"""🔄 חזרה לאתר

📍 {offer['destination']}
🛫 {offer['departure']}
🛬 {offer['return']}
📅 {date_range_text(offer['departure'], offer['return'])}
💰 ${offer['price']}"""
                )

            offer["first_seen"] = old.get("first_seen", now)
            offer["last_seen"] = now
            offer["active"] = True

            history = old.get("price_history", [])

            old_price = old.get("price")
            new_price = offer.get("price")

            if (
                old_price is not None
                and new_price is not None
                and old_price != new_price
            ):

                history.append(
                    {
                        "date": now,
                        "price": new_price,
                    }
                )

                if new_price < old_price:

                    notifications.append(
                        f"""📉 {offer['destination']}

🛫 {offer['departure']}
🛬 {offer['return']}
📅 {date_range_text(offer['departure'], offer['return'])}
💰 ${old_price} → ${new_price}"""
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
                    f"""⚠️ {offer['destination']}

📅 {date_range_text(offer['departure'], offer['return'])}
נותרו רק {new_remaining} מקומות"""
                )

        merged[key] = offer

    # Offers that disappeared
    for key, offer in previous.items():

        # עדיין קיימת באתר
        if key in merged:
            continue

        # כבר סימנו אותה בעבר כלא פעילה
        if not offer.get("active", True):
            merged[key] = offer
            continue

        # זו הפעם הראשונה שהיא נעלמה
        offer["active"] = False
        offer["last_seen"] = now

        merged[key] = offer

        notifications.append(
            f"""❌ ירדה מהאתר

📍 {offer['destination']}
🛫 {offer['departure']}
🛬 {offer['return']}
📅 {date_range_text(offer['departure'], offer['return'])}"""
        )

    return merged, notifications


def scan():

    previous = load_offers()

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox"],
        )

        try:

            page = browser.new_page()

            page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            page.wait_for_selector(
                "div.show_item",
                timeout=30000,
            )

            html = page.content()

        finally:
            browser.close()

    current = parse_offers(html)

    merged, notifications = merge_offers(previous, current)

    save_offers(merged)

    if notifications:

        message = (
            f"📢 Tustus Monitor\n\n"
            f"נמצאו {len(notifications)} עדכונים:\n\n"
            + "\n\n--------------------\n\n".join(notifications)
        )

        # Telegram מגביל ל-4096 תווים
        if len(message) > 3900:

            chunks = [
                message[i:i + 3900]
                for i in range(0, len(message), 3900)
            ]

            for chunk in chunks:
                send_message(chunk)

        else:
            send_message(message)

    print("=" * 60)
    print(f"Scan time     : {local_now()}")
    print(f"Offers online : {len(current)}")
    print(f"Offers stored : {len(merged)}")
    print(f"Notifications : {len(notifications)}")
    print("=" * 60)


if __name__ == "__main__":
    scan()
