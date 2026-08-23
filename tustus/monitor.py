from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

from tustus.parser import parse_offers
from tustus.storage import load_offers, save_offers
from utils.telegram import send_message

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


def format_offer(offer, prefix="🆕"):
    message = f"""{prefix} {offer['destination']}
🛫 {offer['departure']}
🛬 {offer['return']}
📅 {date_range_text(offer['departure'], offer['return'])}
💰 ${offer['price']}"""

    if offer.get("remaining") is not None:
        message += f"\n🎟️ נותרו {offer['remaining']} מקומות"

    return message

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
                format_offer(offer)
            )

        else:

            old = previous[key]

            # הצעה שחזרה אחרי שנעלמה
            if not old.get("active", True):

                notifications.append(
                    format_offer(offer, "🔄")
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

        # שדה פנימי שאינו הצעה
        if key == "_site_empty":
            continue

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


def send_notifications(notifications):
    if not notifications:
        return

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

            # המתנה קצרה כדי לתת ל-JavaScript של האתר להיטען
            page.wait_for_timeout(5000)

            html = page.content()

        finally:
            browser.close()

    current = parse_offers(html)

    # ---------------------------------------------------------
    # No offers
    # ---------------------------------------------------------

    if not current:

        # אם כבר ידענו שהאתר ריק בסריקה הקודמת,
        # לא שולחים שוב התראה.
        site_was_empty = previous.get("_site_empty", False)

        previous["_site_empty"] = True

        if not site_was_empty:

            send_message(
                """📭 Tustus Monitor

כרגע אין כלל הצעות באתר."""
            )

        # לא מעדכנים active של אף הצעה
        save_offers(previous)

        print("=" * 60)
        print(f"Scan time     : {local_now()}")
        print("Offers online : 0")
        print(f"Offers stored : {len(previous) - 1}")
        print("Notifications : 0")
        print("Status        : Site is empty")
        print("=" * 60)

        return

    # ---------------------------------------------------------
    # Site was empty and offers returned
    # ---------------------------------------------------------

    site_was_empty = previous.pop("_site_empty", False)

    # ---------------------------------------------------------
    # Normal merge
    # ---------------------------------------------------------

    merged, notifications = merge_offers(previous, current)

    save_offers(merged)

    # ---------------------------------------------------------
    # Site returned
    #
    # במקרה שהאתר היה ריק, אנחנו רוצים הודעה מפורטת
    # עם ההצעות שחזרו.
    #
    # אם ההצעות כבר היו קיימות ב-previous, הן לא ייחשבו
    # "חדשות" על ידי merge_offers. לכן כאן אנחנו מוסיפים
    # הודעה נפרדת עם ההצעות הנוכחיות.
    # ---------------------------------------------------------

    if site_was_empty:

        returned_offers = list(current.values())

        returned_notifications = [
            format_offer(offer)
            for offer in returned_offers
        ]

        message = (
            f"🟢 Tustus Monitor\n\n"
            f"חזרו הצעות לאתר!\n\n"
            f"נמצאו {len(returned_offers)} "
            f"{'הצעה' if len(returned_offers) == 1 else 'הצעות'}:\n\n"
            + "\n\n--------------------\n\n".join(
                returned_notifications
            )
        )

        if len(message) > 3900:

            chunks = [
                message[i:i + 3900]
                for i in range(0, len(message), 3900)
            ]

            for chunk in chunks:
                send_message(chunk)

        else:
            send_message(message)

    # ---------------------------------------------------------
    # Other notifications
    # ---------------------------------------------------------

    if not site_was_empty:
        send_notifications(notifications)

    print("=" * 60)
    print(f"Scan time     : {local_now()}")
    print(f"Offers online : {len(current)}")
    print(f"Offers stored : {len(merged)}")
    print(f"Notifications : {len(notifications)}")
    print("=" * 60)