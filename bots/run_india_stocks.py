import time
from dotenv import load_dotenv

from core.models import SystemConfig, TradePlan
from core.macro_engine import ForwardMacroEngine
from core.market_data import MarketDataEngine
from core.paper_broker import PersistentPaperBroker
from core.risk_math import RiskEngine
from core.ai_analyst import GeminiForwardAnalyst
from core.notifier import TelegramNotifier
from core.ui import silence_third_party_noise, display_banner, print_status, render_summary_table, console

load_dotenv()
silence_third_party_noise()

def run_india_scanner():
    config = SystemConfig()
    config.interactive_mode = False  # Set to False so it runs hands-free
    config.portfolio_file = "portfolios/india_portfolio.json"
    config.watchlist = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "SBIN.NS", "ITC.NS", "BEL.NS", "FEDERALBNK.NS", "NTPC.NS"
    ]

    broker = PersistentPaperBroker(config)
    risk_engine = RiskEngine(config)
    analyst = GeminiForwardAnalyst(config)

    display_banner("NSE EQUITIES SCANNER", broker.get_available_capital(), config.risk_per_trade_pct)

    # Manage Open Positions
    live_prices = {}
    market_data = {}
    for sym in config.watchlist:
        df = MarketDataEngine.fetch_daily_ohlcv(sym)
        if df is not None and not df.empty:
            live_prices[sym] = float(df.iloc[-1]["close"])
            market_data[sym] = df

    broker.manage_open_trades(live_prices)

    console.print("\n[bold cyan]Scanning Watchlist...[/bold cyan]")
    upcoming_events = ForwardMacroEngine.get_upcoming_events(["INR", "USD"], hours_ahead=48)
    summary_records = []

    for symbol, df in market_data.items():
        latest_close = float(df.iloc[-1]["close"])
        latest_atr = float(df.iloc[-1]["atr_14"])

        try:
            decision = analyst.evaluate_forward_setup(symbol, "EQUITY", df, upcoming_events)
            
            if not decision.execute_order:
                print_status(symbol, f"No setup identified ({decision.bias})", "skip")
                summary_records.append({
                    "symbol": symbol, "price": f"₹{latest_close:,.2f}",
                    "action": "HOLD", "units": "0", "risk": "₹0.00",
                    "status": f"[dim]{decision.bias} (No clear catalyst)[/dim]"
                })
                continue

            plan = risk_engine.evaluate_and_size(
                symbol=symbol,
                capital=broker.get_available_capital(),
                current_price=latest_close,
                atr=latest_atr,
                decision=decision
            )

            if plan and plan.units > 0:
                print_status(symbol, f"{plan.action} signal! Sizing: {plan.units} shares (Risk: ₹{plan.risk_amount:.2f})", "success")
                broker.submit_bracket_order(plan)
                
                # Send Instant Telegram Notification
                if TelegramNotifier.send_trade_alert(plan):
                    print_status(symbol, "Telegram alert dispatched to your phone", "info")

                summary_records.append({
                    "symbol": symbol, "price": f"₹{latest_close:,.2f}",
                    "action": f"[bold green]{plan.action}[/bold green]",
                    "units": f"{plan.units}", "risk": f"₹{plan.risk_amount:,.2f}",
                    "status": "[green]Order Dispatched[/green]"
                })
            else:
                print_status(symbol, "Skipped: Share sizing calculated to 0 (Protects Capital)", "wait")
                summary_records.append({
                    "symbol": symbol, "price": f"₹{latest_close:,.2f}",
                    "action": "SKIP", "units": "0", "risk": "₹0.00",
                    "status": "[yellow]Capital protection (0 shares)[/yellow]"
                })

        except Exception as e:
            err_msg = str(e)
            if "503" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
                print_status(symbol, "Google API limit reached. Skipped safely.", "error")
            else:
                print_status(symbol, f"Analysis error: {err_msg[:45]}...", "error")
            
            summary_records.append({
                "symbol": symbol, "price": f"₹{latest_close:,.2f}",
                "action": "--", "units": "--", "risk": "--",
                "status": "[red]API Server Busy[/red]"
            })

        time.sleep(1.5)

    render_summary_table("NSE SCAN RESULTS", summary_records)

if __name__ == "__main__":
    run_india_scanner()