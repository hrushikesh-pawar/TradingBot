"""
=============================================================================
FORWARD-LOOKING AUTONOMOUS CROSS-ASSET SWING SCANNER (INTERACTIVE)
=============================================================================
1. Forward Macro Engine: Live Economic Calendar (Strictly High Impact)
2. Technical Ingestion: Real Candlesticks & ATR Volatility (yfinance)
3. AI Expectation Engine: Ultra-precise reasoning and outcome mapping
4. Interactive Live Trade Tracking: Prompts user for actual execution data
5. Flawless Trade Manager: Break-Even trailing stops & real PnL math
6. Paper Broker & State Persistence: JSON portfolio tracking
7. Instant Telegram Alerts: Segregates LIVE vs PAPER trades
=============================================================================
"""

import os
import sys
import json
import math
import time
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Literal, Optional
from dataclasses import dataclass, field

import pandas as pd
import pandas_ta as ta
import yfinance as yf
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()


# =====================================================================
# 1. LOGGING & NOTIFICATIONS
# =====================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("trading_bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("CrossAssetBot")


def send_telegram_message(message: str):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Telegram dispatch failed: {e}")


# =====================================================================
# 2. SYSTEM CONFIGURATION & SCHEMAS
# =====================================================================

@dataclass
class SystemConfig:
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    initial_capital: float = 1_000_000.0  
    risk_per_trade_pct: float = 0.01      
    atr_stop_multiplier: float = 1.5      
    min_risk_reward: float = 2.0          
    min_confidence: int = 7               
    interactive_mode: bool = True  # Set to False if running completely unattended via Task Scheduler
    watchlist: List[str] = field(
        default_factory=lambda: os.getenv("WATCHLIST", "USDINR=X,EURUSD=X,GBPUSD=X,BTC-USD,ETH-USD").split(",")
    )
    portfolio_file: str = "paper_portfolio.json"


class GeminiForwardDecision(BaseModel):
    symbol: str
    asset_class: Literal["FOREX", "CRYPTO"]
    bias: Literal["LONG", "SHORT", "NO_TRADE"]
    confidence: int = Field(ge=1, le=10)
    structural_invalidation: float 
    execute_order: bool 
    forward_catalyst: str 
    thesis: str 
    possible_outcome: str 


class TradePlan(BaseModel):
    symbol: str
    action: Literal["BUY", "SELL"]
    entry_price: float
    stop_loss: float
    take_profit: float
    units: float  
    risk_amount: float
    reward_to_risk: float
    reasons_why: str
    possible_outcome: str
    trade_type: Literal["PAPER", "LIVE"] = "PAPER"
    conversion_factor: float = 1.0


# =====================================================================
# 3. FORWARD MACRO CALENDAR ENGINE (Tier-1 Only)
# =====================================================================

class ForwardMacroEngine:
    CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

    @classmethod
    def get_upcoming_events(cls, currency_list: List[str], hours_ahead: int = 72) -> List[Dict]:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = requests.get(cls.CALENDAR_URL, headers=headers, timeout=10)
            if resp.status_code != 200:
                return []

            raw_events = resp.json()
            now = datetime.now(timezone.utc)
            cutoff = now + timedelta(hours=hours_ahead)

            relevant = []
            for ev in raw_events:
                c = ev.get("country", "")
                impact = ev.get("impact", "")
                
                if c in currency_list and impact == "High":
                    try:
                        ev_time = datetime.fromisoformat(ev["date"])
                        if now <= ev_time <= cutoff:
                            hours_until = round((ev_time - now).total_seconds() / 3600, 1)
                            relevant.append({
                                "currency": c,
                                "event": ev.get("title"),
                                "impact": impact,
                                "hours_until": hours_until,
                                "forecast": ev.get("forecast", "N/A"),
                                "previous": ev.get("previous", "N/A")
                            })
                    except Exception:
                        continue
            return relevant
        except Exception as e:
            logger.error(f"Error fetching economic calendar: {e}")
            return []


# =====================================================================
# 4. MARKET DATA ENGINE 
# =====================================================================

class MarketDataEngine:
    @staticmethod
    def fetch_daily_ohlcv(symbol: str) -> Optional[pd.DataFrame]:
        try:
            df = yf.download(symbol, period="365d", interval="1d", progress=False)
            if df.empty or len(df) < 50: return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [str(col).lower() for col in df.columns]

            df["ema_50"] = ta.ema(df["close"], length=50)
            df["ema_200"] = ta.ema(df["close"], length=200)
            df["atr_14"] = ta.atr(df["high"], df["low"], df["close"], length=14)
            return df.dropna()
        except Exception:
            return None


# =====================================================================
# 5. PERSISTENT BROKER & PORTFOLIO MANAGER
# =====================================================================

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
                
                # Only add PnL to capital if it's a PAPER trade (live capital is handled by your real broker)
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


# =====================================================================
# 6. RISK SIZING ENGINE & INTERACTIVE PROMPT
# =====================================================================

class RiskEngine:
    def __init__(self, config: SystemConfig):
        self.cfg = config

    def evaluate_and_size(self, symbol: str, capital: float, current_price: float, atr: float, decision: GeminiForwardDecision, usdinr_rate: float) -> Optional[TradePlan]:
        if not decision.execute_order or decision.confidence < self.cfg.min_confidence: return None

        risk_budget_inr = capital * self.cfg.risk_per_trade_pct
        atr_buffer = atr * self.cfg.atr_stop_multiplier

        if decision.bias == "LONG":
            action = "BUY"
            stop_loss = min(current_price - atr_buffer, decision.structural_invalidation)
            distance = current_price - stop_loss
            if distance <= 0: return None
            take_profit = current_price + (distance * self.cfg.min_risk_reward)
        else:
            action = "SELL"
            stop_loss = max(current_price + atr_buffer, decision.structural_invalidation)
            distance = stop_loss - current_price
            if distance <= 0: return None
            take_profit = current_price - (distance * self.cfg.min_risk_reward)

        conversion_factor = usdinr_rate if ("USD" in symbol and "INR" not in symbol) else 1.0
        raw_units = risk_budget_inr / (distance * conversion_factor)
        units = round(raw_units, 4) if decision.asset_class == "CRYPTO" else math.floor(raw_units)

        if units <= 0: return None

        actual_risk_inr = round(units * distance * conversion_factor, 2)

        return TradePlan(
            symbol=symbol, action=action, entry_price=round(current_price, 4),
            stop_loss=round(stop_loss, 4), take_profit=round(take_profit, 4),
            units=units, risk_amount=actual_risk_inr, reward_to_risk=self.cfg.min_risk_reward,
            reasons_why=f"Macro: {decision.forward_catalyst} | Tech: {decision.thesis}",
            possible_outcome=decision.possible_outcome, trade_type="PAPER", conversion_factor=conversion_factor
        )

def process_interactive_trade(plan: TradePlan, usdinr_rate: float) -> Optional[TradePlan]:
    """Interrupts execution to ask the user for actual real-world trade data."""
    print("\n" + "="*50)
    print(f"🤖 BOT SIGNAL: {plan.action} {plan.symbol}")
    print(f"Suggested Entry: {plan.entry_price} | SL: {plan.stop_loss} | TP: {plan.take_profit} | Size: {plan.units}")
    print("="*50)
    
    choice = input("Did you execute this trade on your live broker? (y/n): ").strip().lower()
    if choice == 'y':
        try:
            print("--- Enter Real Broker Execution Details ---")
            actual_entry = float(input("Actual Filled Entry Price: "))
            actual_sl = float(input("Actual Stop Loss Set: "))
            actual_tp = float(input("Actual Take Profit Set: "))
            actual_units = float(input("Actual Units/Lot Size: "))
            
            distance = abs(actual_entry - actual_sl)
            conversion = usdinr_rate if ("USD" in plan.symbol and "INR" not in plan.symbol) else 1.0
            actual_risk = round(actual_units * distance * conversion, 2)
            
            plan.entry_price = actual_entry
            plan.stop_loss = actual_sl
            plan.take_profit = actual_tp
            plan.units = actual_units
            plan.risk_amount = actual_risk
            plan.trade_type = "LIVE"
            plan.conversion_factor = conversion
            print(">> Tracking Live Trade parameters <<")
            return plan
        except ValueError:
            print("Invalid input detected. Reverting to automated Paper tracking.")
            plan.trade_type = "PAPER"
            return plan
    else:
        track = input("Track as a simulated PAPER trade instead? (y/n): ").strip().lower()
        if track == 'y':
            plan.trade_type = "PAPER"
            return plan
        print(">> Setup Ignored <<")
        return None


# =====================================================================
# 7. AI FORWARD-LOOKING REASONING AGENT
# =====================================================================

class GeminiForwardAnalyst:
    def __init__(self, config: SystemConfig):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key: raise ValueError("GEMINI_API_KEY not found in .env")
        self.client = genai.Client(api_key=api_key)
        self.model = config.gemini_model

    def evaluate_forward_setup(self, symbol: str, df: pd.DataFrame, upcoming_events: List[Dict]) -> GeminiForwardDecision:
        latest = df.iloc[-1]
        events_formatted = json.dumps(upcoming_events, indent=2)
        asset_type = "Cryptocurrency" if "BTC" in symbol or "ETH" in symbol else "Fiat Currency Pair"

        prompt = f"""
You are an elite quantitative strategist analyzing {symbol} (Asset Class: {asset_type}). 
Your analysis MUST be precise, straight to the point, with zero fluff.

UPCOMING RELEVANT TIER-1 MACRO CALENDAR (NEXT 72 HOURS):
{events_formatted}

CURRENT MARKET TECHNICAL SNAPSHOT:
- Close: {latest['close']:.4f}
- 50 EMA: {latest['ema_50']:.4f} | 200 EMA: {latest['ema_200']:.4f}

STRICT INSTRUCTIONS:
1. EVENT RISK: If a HIGH-impact release is scheduled in < 12 hours, execute_order = false. 
2. EXPECTATIONS DRIVER: Determine market expectations based on forecast vs previous data.
3. OUTPUT: Provide direct, bullet-point style reasoning. State exactly why the trade is valid, and explicitly define the most probable outcome path over the next 3 to 5 days.
"""
        response = self.client.models.generate_content(
            model=self.model, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=GeminiForwardDecision, temperature=0.0)
        )
        return GeminiForwardDecision.model_validate_json(response.text)


# =====================================================================
# 8. PIPELINE ORCHESTRATOR
# =====================================================================

def run_forward_bot():
    config = SystemConfig()
    logger.info("=" * 65)
    logger.info("STARTING CROSS-ASSET EXPECTATION SCANNER (FOREX & CRYPTO)")
    logger.info("=" * 65)

    broker = PersistentPaperBroker(config)
    risk_engine = RiskEngine(config)
    analyst = GeminiForwardAnalyst(config)

    currencies_to_watch = ["USD", "EUR", "GBP", "INR", "JPY", "AUD", "CAD", "CHF"]
    upcoming_events = ForwardMacroEngine.get_upcoming_events(currencies_to_watch, hours_ahead=72)

    live_prices = {}
    market_data = {}
    for sym in config.watchlist:
        s = sym.strip()
        df = MarketDataEngine.fetch_daily_ohlcv(s)
        if df is not None:
            live_prices[s] = float(df.iloc[-1]["close"])
            market_data[s] = df

    usdinr_rate = live_prices.get("USDINR=X", 84.0)
    broker.manage_open_trades(live_prices)

    for symbol, df in market_data.items():
        logger.info(f"\n>>> ANALYZING EXPECTATIONS FOR: {symbol} <<<")
        latest_close = float(df.iloc[-1]["close"])
        latest_atr = float(df.iloc[-1]["atr_14"])

        pair_currencies = [c for c in currencies_to_watch if c in symbol]
        pair_events = [ev for ev in upcoming_events if ev["currency"] in pair_currencies]

        try:
            decision = analyst.evaluate_forward_setup(symbol, df, pair_events)
            plan = risk_engine.evaluate_and_size(symbol, broker.get_available_capital(), latest_close, latest_atr, decision, usdinr_rate)

            if plan:
                if config.interactive_mode:
                    plan = process_interactive_trade(plan, usdinr_rate)
                
                if plan:
                    broker.submit_bracket_order(plan)
            else:
                logger.info(f"[{symbol}] No order dispatched (Filter gate active or No edge).")

        except Exception as e:
            logger.error(f"[{symbol}] Analysis failed: {e}")
            
        time.sleep(4) 

    logger.info("\n" + "=" * 65)
    logger.info("SCAN COMPLETED.")
    logger.info("=" * 65)


if __name__ == "__main__":
    run_forward_bot()