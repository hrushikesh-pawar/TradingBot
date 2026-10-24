import os
import json
import logging
from datetime import datetime

# Import our custom models and telegram alerts
from core.models import SystemConfig, TradePlan
from core.telegram_alerts import send_telegram_message

logger = logging.getLogger("PaperBroker")

class PersistentPaperBroker:
    def __init__(self, config: SystemConfig):
        self.filepath = config.portfolio_file
        self.capital = config.initial_capital
        self._load_state()

    def _load_state(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.capital = data.get("capital", self.capital)
                    self.orders = data.get("orders", [])
            except Exception: self.orders = []
        else:
            self.orders = []
            self._save_state()

    def _save_state(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump({"capital": self.capital, "orders": self.orders}, f, indent=2)

    def manage_open_trades(self, live_prices: dict):
        for order in self.orders:
            if order["status"] != "OPEN":
                continue
            symbol = order["symbol"]
            current_price = live_prices.get(symbol)
            if not current_price: continue

            closed, pnl, reason = False, 0.0, ""
            conv_factor = order.get("conversion_factor", 1.0)
            t_type = order.get("trade_type", "PAPER")
            badge = "🔴 LIVE" if t_type == "LIVE" else "📝 PAPER"

            # BREAK-EVEN TRAILING STOP & EXACT PNL MATH
            if order["action"] == "BUY":
                halfway = order["entry_price"] + ((order["take_profit"] - order["entry_price"]) / 2)
                
                # Trail Stop to Entry if Halfway to Target
                if current_price >= halfway and order["stop_loss"] < order["entry_price"]:
                    order["stop_loss"] = order["entry_price"]
                    msg = f"🛡️ <b>RISK FREE ({badge}): {symbol}</b>\nPrice reached 50% target. SL moved to Break Even (<code>{order['entry_price']}</code>)."
                    logger.info(msg.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
                    send_telegram_message(msg)
                    self._save_state()

                if current_price <= order["stop_loss"]:
                    closed, reason = True, ("BREAK EVEN HIT" if order["stop_loss"] >= order["entry_price"] else "STOP LOSS")
                    pnl = (order["stop_loss"] - order["entry_price"]) * order["units"] * conv_factor
                elif current_price >= order["take_profit"]:
                    closed, reason = True, "TAKE PROFIT HIT"
                    pnl = (order["take_profit"] - order["entry_price"]) * order["units"] * conv_factor

            elif order["action"] == "SELL":
                halfway = order["entry_price"] - ((order["entry_price"] - order["take_profit"]) / 2)
                
                if current_price <= halfway and order["stop_loss"] > order["entry_price"]:
                    order["stop_loss"] = order["entry_price"]
                    msg = f"🛡️ <b>RISK FREE ({badge}): {symbol}</b>\nPrice reached 50% target. SL moved to Break Even (<code>{order['entry_price']}</code>)."
                    logger.info(msg.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
                    send_telegram_message(msg)
                    self._save_state()

                if current_price >= order["stop_loss"]:
                    closed, reason = True, ("BREAK EVEN HIT" if order["stop_loss"] <= order["entry_price"] else "STOP LOSS")
                    pnl = (order["entry_price"] - order["stop_loss"]) * order["units"] * conv_factor
                elif current_price <= order["take_profit"]:
                    closed, reason = True, "TAKE PROFIT HIT"
                    pnl = (order["entry_price"] - order["take_profit"]) * order["units"] * conv_factor

            if closed:
                order["status"] = "CLOSED"
                order["exit_price"] = current_price
                order["pnl"] = round(pnl, 2)
                
                # Only add PnL to capital if it's a PAPER trade
                if t_type == "PAPER":
                    self.capital += order["pnl"]
                    cap_str = f"\nNew Paper Balance: ₹{self.capital:,.2f}"
                else:
                    cap_str = ""

                msg = f"🔔 <b>{badge} TRADE CLOSED: {symbol}</b>\nResult: {reason}\nRealized PnL: ₹{order['pnl']:,.2f}{cap_str}"
                logger.info(msg.replace("<b>", "").replace("</b>", ""))
                send_telegram_message(msg)

        self._save_state()

    def submit_bracket_order(self, plan: TradePlan):
        if any(o["symbol"] == plan.symbol and o["status"] == "OPEN" and o.get("trade_type") == plan.trade_type for o in self.orders):
            logger.info(f"[{plan.symbol}] {plan.trade_type} position already open. Skipping duplicate.")
            return

        order_record = {
            "order_id": f"{plan.trade_type[:3]}-{int(datetime.now().timestamp())}",
            "status": "OPEN",
            "symbol": plan.symbol,
            "action": plan.action,
            "units": plan.units,
            "entry_price": plan.entry_price,
            "stop_loss": plan.stop_loss,
            "take_profit": plan.take_profit,
            "risk_amount": plan.risk_amount,
            "trade_type": plan.trade_type,
            "conversion_factor": plan.conversion_factor
        }
        self.orders.append(order_record)
        self._save_state()

        action_icon = "🟢" if plan.action == "BUY" else "🔴"
        type_badge = "🚨 LIVE" if plan.trade_type == "LIVE" else "📝 PAPER"
        
        msg = (
            f"<b>{type_badge} ALERT: {plan.symbol}</b> {action_icon}\n\n"
            f"🎯 <b>Entry:</b> <code>{plan.entry_price}</code>\n"
            f"✅ <b>Target (Exit):</b> <code>{plan.take_profit}</code>\n"
            f"🛑 <b>Stop Loss:</b> <code>{plan.stop_loss}</code>\n"
            f"⚖️ <b>Size:</b> {plan.units} units | <b>Risk:</b> ₹{plan.risk_amount:,.2f}\n\n"
            f"🧠 <b>Reasons Why:</b>\n<i>{plan.reasons_why}</i>\n\n"
            f"🔮 <b>Outcome Matrix:</b>\n<i>{plan.possible_outcome}</i>"
        )
        
        clean_log_msg = msg.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "").replace("<i>", "").replace("</i>", "")
        logger.info(clean_log_msg)
        send_telegram_message(msg)

    def get_available_capital(self) -> float:
        return self.capital