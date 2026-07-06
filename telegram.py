import os
import requests

BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_message(message: str) -> bool:
    """
    Sends a Telegram message.

    Returns True on success, False otherwise.
    """

    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram is not configured.")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:

        response = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": message,
                "disable_web_page_preview": True,
            },
            timeout=20,
        )

        response.raise_for_status()

        return True

    except Exception as e:
        print("Telegram error:", e)
        return False
