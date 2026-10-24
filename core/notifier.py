import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("Notifier")

class TelegramNotifier:
    @staticmethod
    def send_trade_alert(plan) -> bool:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not token or not chat_id:
            logger.error("Telegram token or chat ID is missing in .env")
            return False

        currency_symbol = "$" if "USD" in plan.symbol or plan.symbol in ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL"] else "₹"

        message = (
            f"🎯 <b>TRADE SIGNAL DETECTED</b>\n\n"
            f"<b>Asset:</b> <code>{plan.symbol}</code>\n"
            f"<b>Action:</b> {'🟢 BUY' if plan.action == 'BUY' else '🔴 SELL'}\n"
            f"<b>Entry:</b> {currency_symbol}{plan.entry_price:,.2f}\n"
            f"<b>Stop Loss:</b> {currency_symbol}{plan.stop_loss:,.2f}\n"
            f"<b>Take Profit:</b> {currency_symbol}{plan.take_profit:,.2f}\n"
            f"<b>Position Size:</b> {plan.units}\n"
            f"<b>Max Risk:</b> ₹{plan.risk_amount:,.2f}\n"
            f"<b>Mode:</b> {plan.trade_type}"
        )

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        try:
            response = requests.post(url, json=payload, timeout=8)
            if response.status_code == 200:
                return True
            else:
                print(f"\n[Telegram Error {response.status_code}]: {response.text}")
                return False
        except Exception as e:
            print(f"\n[Telegram Network Exception]: {e}")
            return False