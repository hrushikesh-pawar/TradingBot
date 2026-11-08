import yfinance as yf
import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# Connect to your core modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.telegram_alerts import send_telegram_message 
from core.sheet_logger import log_trade

# COMEX/NYMEX futures used as price proxies for the matching MCX contracts
COMMODITY_TICKERS = {
    "GC=F": "Gold",
    "SI=F": "Silver",
    "CL=F": "Crude Oil",
    "NG=F": "Natural Gas",
    "HG=F": "Copper",
}

def fmt_price(x):
    # Copper (~$4.5) and Natural Gas (~$3) need more decimals than Gold (~$4000)
    return f"{x:.4f}" if abs(x) < 100 else f"{x:.2f}"

def calculate_indicators(df):
    # Trend: 20, 50, 200 SMAs
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df['SMA_200'] = df['Close'].rolling(200).mean()
    
    # Momentum: 14-day RSI
    delta = df['Close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -1 * delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Volatility: 14-day ATR
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - df['Close'].shift(1)).abs()
    tr3 = (df['Low'] - df['Close'].shift(1)).abs()
    df['ATR'] = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1).rolling(14).mean()
    
    # Daily Returns for Monte Carlo Volatility
    df['Log_Returns'] = np.log(df['Close'] / df['Close'].shift(1))
    return df.dropna()

def generate_signals(df):
    df['Signal'] = 0
    
    # EXACT CROSSOVER: 20 SMA crosses OVER 50 SMA exactly today (t) and was below/equal yesterday (t-1)
    bull_cross = (df['SMA_20'] > df['SMA_50']) & (df['SMA_20'].shift(1) <= df['SMA_50'].shift(1))
    bull_macro = (df['Close'] > df['SMA_200']) & (df['RSI'] < 70)
    bull_condition = bull_cross & bull_macro
    
    # EXACT CROSSOVER: 20 SMA crosses UNDER 50 SMA exactly today (t) and was above/equal yesterday (t-1)
    bear_cross = (df['SMA_20'] < df['SMA_50']) & (df['SMA_20'].shift(1) >= df['SMA_50'].shift(1))
    bear_macro = (df['Close'] < df['SMA_200']) & (df['RSI'] > 30)
    bear_condition = bear_cross & bear_macro
    
    df.loc[bull_condition, 'Signal'] = 1
    df.loc[bear_condition, 'Signal'] = -1
    
    return df

def run_monte_carlo(current_price, log_returns, tp, sl, action, days=21, sims=10000):
    mu = log_returns.mean()
    sigma = log_returns.std()
    
    wins = 0
    for _ in range(sims):
        path = current_price
        for _ in range(days):
            shock = np.random.normal(mu, sigma)
            path = path * np.exp(shock)
            
            if action == 1: # Long
                if path >= tp:
                    wins += 1
                    break
                elif path <= sl:
                    break
            else: # Short
                if path <= tp:
                    wins += 1
                    break
                elif path >= sl:
                    break
                    
    return (wins / sims) * 100

if __name__ == "__main__":
    print(f"Starting Commodity Scan for {len(COMMODITY_TICKERS)} tickers...")
    signals_found = 0

    for ticker, name in COMMODITY_TICKERS.items():
        print(f"Scanning {name} ({ticker})...")
        try:
            df = yf.Ticker(ticker).history(period="2y", interval="1d")
            if df.empty:
                print(f"⚠️ No data returned for {ticker}")
                continue

            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            print(f"   Last candle used: {df.index[-1].date()} | Close: {fmt_price(df['Close'].iloc[-1])}")
            df = calculate_indicators(df)
            df = generate_signals(df)

            crossovers = df[df['Signal'] != 0]

            # Only alert if the crossover happened on the latest candle (not some old one)
            if not crossovers.empty and crossovers.index[-1] == df.index[-1]:
                signals_found += 1
                latest = crossovers.iloc[-1]
                action = latest['Signal']
                price = latest['Close']
                atr = latest['ATR']

                # Calculate Volatility-Based Exits (1.5x Risk, 3.0x Reward)
                if action == 1:
                    sl = price - (1.5 * atr)
                    tp = price + (3.0 * atr)
                    dir_str = "🟢 BUY"
                else:
                    sl = price + (1.5 * atr)
                    tp = price - (3.0 * atr)
                    dir_str = "🔴 SELL"

                # Run 10,000 Simulations
                win_prob = run_monte_carlo(price, df['Log_Returns'], tp, sl, action)
                final_call = "✅ EXECUTE TRADE" if win_prob >= 55.0 else "❌ SKIP TRADE (Low Probability)"

                msg = (
                    f"🚨 *COMMODITY SIGNAL: {name} ({ticker})*\n"
                    f"Action: {dir_str}\n"
                    f"Entry: ${fmt_price(price)}\n"
                    f"Stop Loss: ${fmt_price(sl)}\n"
                    f"Take Profit: ${fmt_price(tp)}\n\n"
                    f"📊 *SIMULATION DATA*\n"
                    f"200 SMA Trend: Confirmed\n"
                    f"RSI Momentum: {latest['RSI']:.1f}\n"
                    f"Monte Carlo Win Prob: {win_prob:.1f}%\n"
                    f"Final Call: {final_call}"
                )

                print(f"Triggering Telegram alert for {name}...")
                send_telegram_message(msg)

                # Log to Google Sheets (new sheet, because it has an extra Ticker column)
                today = datetime.now().strftime("%Y-%m-%d")
                headers = ["Ticker", "Commodity", "Date", "Action", "Entry", "Stop Loss", "Take Profit", "Win Probability", "Final Call"]
                row_data = [ticker, name, today, dir_str, float(fmt_price(price)), float(fmt_price(sl)), float(fmt_price(tp)), f"{win_prob:.1f}%", final_call]
                log_trade("Commodity_Trade_Log", headers, row_data)

        except Exception as e:
            print(f"Error processing {ticker}: {e}")

    if signals_found == 0:
        print("No advanced commodity setups detected today.")
