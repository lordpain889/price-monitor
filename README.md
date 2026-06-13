# Price Monitor

A Python script that monitors product prices on [books.toscrape.com](https://books.toscrape.com), stores price history, and sends Telegram alerts when the price drops below a threshold.

## Features

- Checks a product page every 60 seconds (configurable)
- Saves price history with UTC timestamps to a JSON file
- Prints current price and recent history in the terminal
- Sends a Telegram notification when the price crosses below your threshold
- Resets the alert if the price goes back above the threshold

## Setup

1. **Create a virtual environment (recommended)**

   ```bash
   python -m venv venv
   venv\Scripts\activate        # Windows
   # source venv/bin/activate   # macOS/Linux
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the monitor**

   Edit `config.json`:

   | Key | Description |
   | --- | --- |
   | `product_url` | Full URL of the book product page |
   | `price_threshold` | Alert when price drops below this value (GBP) |
   | `check_interval_seconds` | Seconds between checks (default: 60) |
   | `history_file` | Path to the JSON history file |
   | `telegram_bot_token` | Token from [@BotFather](https://t.me/BotFather) |
   | `telegram_chat_id` | Your Telegram chat ID |

   **Finding a product URL:** Browse [books.toscrape.com](https://books.toscrape.com), open a book, and copy the URL from the address bar.

   **Telegram setup:**
   1. Message [@BotFather](https://t.me/BotFather) and create a bot to get a token.
   2. Message [@userinfobot](https://t.me/userinfobot) or your bot to get your chat ID.
   3. Start a chat with your bot before running the script.

## Usage

```bash
python price_monitor.py
```

The script runs until you press `Ctrl+C`. Each check prints the current price and the last 10 history entries.

### Example output

```
============================================================
Product:   A Light in the Attic
Price:     £51.77
Threshold: £50.00
Status:    above threshold
------------------------------------------------------------
Price history (most recent first):
  2026-06-13 12:00:00 UTC  £51.77
============================================================
```

## Price history file

History is stored in `price_history.json` (or the path set in config):

```json
{
  "entries": [
    {
      "timestamp": "2026-06-13T12:00:00+00:00",
      "price": 51.77
    }
  ],
  "alert_active": false
}
```

## Notes

- books.toscrape.com is a demo scraping site; prices are static and won't change in practice. Use it to verify the script works, then point `product_url` at any site with a similar HTML structure (adjust the scraper if needed).
- Telegram notifications are skipped if the token or chat ID are left as placeholders.
