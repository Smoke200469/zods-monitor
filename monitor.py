import hashlib
import json
import os
import re
from pathlib import Path

import requests


URL = "https://zods.pro"
STATE_FILE = Path("state.json")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

LAUNCH_WORDS = [
    "connect wallet",
    "launch app",
    "enter app",
    "mint now",
    "buy now",
    "get started",
    "start trading",
    "open app",
    "claim",
]


def send_telegram(message: str) -> None:
    endpoint = (
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        endpoint,
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": False,
        },
        timeout=20,
    )

    response.raise_for_status()


def clean_html(html: str) -> str:
    html = re.sub(
        r"<script\b[^>]*>.*?</script>",
        "",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    html = re.sub(
        r"<style\b[^>]*>.*?</style>",
        "",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return re.sub(r"\s+", " ", html).strip()


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    response = requests.get(
        URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 ZODS Launch Monitor"
            )
        },
        timeout=30,
        allow_redirects=True,
    )

    raw_html = response.text
    cleaned_html = clean_html(raw_html)
    lowercase_html = cleaned_html.lower()

    current_hash = hashlib.sha256(
        cleaned_html.encode("utf-8")
    ).hexdigest()

    detected_words = [
        word
        for word in LAUNCH_WORDS
        if word in lowercase_html
    ]

    current_state = {
        "hash": current_hash,
        "status_code": response.status_code,
        "final_url": response.url,
        "detected_words": detected_words,
    }

    previous_state = load_state()

    # First run: create the baseline without a false alarm.
    if not previous_state:
        save_state(current_state)
        print("Initial website baseline created.")
        return

    content_changed = (
        current_state["hash"] != previous_state.get("hash")
    )

    status_changed = (
        current_state["status_code"]
        != previous_state.get("status_code")
    )

    previous_words = set(
        previous_state.get("detected_words", [])
    )

    new_launch_words = [
        word
        for word in detected_words
        if word not in previous_words
    ]

    if new_launch_words:
        send_telegram(
            "🚨 POSSIBLE ZODS LAUNCH!\n\n"
            "New launch-related text detected:\n"
            f"{', '.join(new_launch_words)}\n\n"
            f"Status: {response.status_code}\n"
            f"Open now: {response.url}"
        )

    elif content_changed or status_changed:
        send_telegram(
            "⚠️ ZODS.PRO HAS CHANGED\n\n"
            f"Status: {response.status_code}\n"
            f"Final address: {response.url}\n\n"
            "Check the website:\n"
            "https://zods.pro"
        )

    else:
        print("No change detected.")

    save_state(current_state)


if __name__ == "__main__":
    main()
