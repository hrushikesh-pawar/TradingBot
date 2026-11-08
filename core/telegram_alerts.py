import os
import requests
import logging

logger = logging.getLogger("TelegramAlerts")

def send_telegram_message(message: str):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram skipped: TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if not r.ok:
            print(f"Telegram rejected the message ({r.status_code}): {r.text}")
    except Exception as e:
        logger.error(f"Telegram dispatch failed: {e}")