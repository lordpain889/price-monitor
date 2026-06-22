#!/usr/bin/env python3
"""Monitor product prices on books.toscrape.com and alert via Telegram."""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from urllib3.util import Retry

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
DEFAULT_CONFIG = {
    "product_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
    "price_threshold": 50.0,
    "check_interval_seconds": 60,
    "history_file": "price_history.json",
    "max_history_entries": 500,
    "telegram_bot_token": "YOUR_BOT_TOKEN",
    "telegram_chat_id": "YOUR_CHAT_ID",
}


def load_config(path: Path) -> dict:
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
        print(f"Created default config at {path}. Edit it before running.")
        sys.exit(1)

    with path.open(encoding="utf-8") as f:
        config = json.load(f)

    for key in ("product_url", "price_threshold", "check_interval_seconds", "history_file"):
        if key not in config:
            print(f"Missing required config key: {key}")
            sys.exit(1)

    return config


def parse_price(text: str) -> float:
    match = re.search(r"[\d.]+", text.replace(",", ""))
    if not match:
        raise ValueError(f"Could not parse price from: {text!r}")
    return float(match.group())


def build_retrying_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch_price(session: requests.Session, url: str) -> tuple[float, str]:
    response = session.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    price_el = soup.select_one("p.price_color")
    if price_el is None:
        raise ValueError("Price element not found on page")

    title_el = soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else "Unknown product"

    return parse_price(price_el.get_text(strip=True)), title


def load_history(path: Path) -> dict:
    if not path.exists():
        return {"entries": [], "alert_active": False}

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    data.setdefault("entries", [])
    data.setdefault("alert_active", False)
    return data


def save_history(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def send_telegram(session: requests.Session, token: str, chat_id: str, message: str) -> bool:
    if token in ("", "YOUR_BOT_TOKEN") or chat_id in ("", "YOUR_CHAT_ID"):
        print("Telegram not configured - skipping notification.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = session.post(
        url,
        json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
        timeout=30,
    )
    response.raise_for_status()
    return True


def format_timestamp(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def display_status(
    title: str,
    price: float,
    threshold: float,
    entries: list[dict],
    history_limit: int = 10,
) -> None:
    print("\n" + "=" * 60)
    print(f"Product:   {title}")
    print(f"Price:     GBP {price:.2f}")
    print(f"Threshold: GBP {threshold:.2f}")
    status = "BELOW THRESHOLD" if price < threshold else "above threshold"
    print(f"Status:    {status}")
    print("-" * 60)
    print("Price history (most recent first):")

    if not entries:
        print("  (no history yet)")
    else:
        for entry in reversed(entries[-history_limit:]):
            ts = format_timestamp(entry["timestamp"])
            print(f"  {ts}  GBP {entry['price']:.2f}")

    print("=" * 60)


def run_check(
    config: dict,
    history_path: Path,
    session: requests.Session,
    telegram_token: str,
    telegram_chat_id: str,
) -> None:
    history = load_history(history_path)
    entries = history["entries"]
    previous_price = entries[-1]["price"] if entries else None

    price, title = fetch_price(session, config["product_url"])
    threshold = float(config["price_threshold"])
    timestamp = datetime.now(timezone.utc).isoformat()

    entries.append({"timestamp": timestamp, "price": price})
    max_history_entries = int(config.get("max_history_entries", 500))
    if max_history_entries > 0 and len(entries) > max_history_entries:
        del entries[:-max_history_entries]
    history["entries"] = entries

    display_status(title, price, threshold, entries)

    below_threshold = price < threshold
    was_below = history.get("alert_active", False)

    if below_threshold and not was_below:
        message = (
            f"<b>Price alert!</b>\n\n"
            f"{title}\n"
            f"Current price: £{price:.2f}\n"
            f"Threshold: £{threshold:.2f}\n"
            f"{config['product_url']}"
        )
        if send_telegram(session, telegram_token, telegram_chat_id, message):
            print("Telegram notification sent.")
        history["alert_active"] = True
    elif not below_threshold and was_below:
        history["alert_active"] = False
        print("Price back above threshold - alert reset.")

    if previous_price is not None and price < previous_price:
        print(f"Price dropped by GBP {previous_price - price:.2f} since last check.")

    save_history(history_path, history)


def main() -> None:
    config = load_config(CONFIG_FILE)
    history_path = Path(config["history_file"])
    if not history_path.is_absolute():
        history_path = BASE_DIR / history_path
    history_path.parent.mkdir(parents=True, exist_ok=True)

    interval = int(config["check_interval_seconds"])
    if interval <= 0:
        print("check_interval_seconds must be a positive integer.")
        sys.exit(1)
    session = build_retrying_session()
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", config.get("telegram_bot_token", ""))
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", config.get("telegram_chat_id", ""))

    print(f"Price monitor started - checking every {interval}s")
    print(f"URL: {config['product_url']}")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            run_check(config, history_path, session, telegram_token, telegram_chat_id)
        except requests.RequestException as exc:
            print(f"Network error: {exc}")
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"Error: {exc}")

        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped.")
            break


if __name__ == "__main__":
    main()
