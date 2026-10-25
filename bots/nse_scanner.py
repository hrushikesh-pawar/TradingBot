import yfinance as yf
import pandas as pd
import numpy as np
import sys
import os

# Connect to your core telegram module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.telegram_alerts import send_telegram_message 

# Basket of top Indian Equities (Add any .NS tickers here)
NIFTY_TICKERS = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", 
    "INFY.NS", "TCS.NS", "ITC.NS", "LT.NS", "SBI.NS", "BHARTIARTL.NS"
]

def calculate_indicators(df):
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df['SMA_200'] = df['Close'].rolling(200).mean()
    
    delta = df['Close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -1 * delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - df['Close'].shift(1)).abs()
    tr3 = (df['Low'] - df['Close'].shift(1)).abs()
    df['ATR'] = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1).rolling(14).mean()
    
    df['Log_Returns'] = np.log(df['Close'] / df['Close'].shift(1))
    return df.dropna()

def generate_signals(df):
    df['Signal'] = 0
    bull_condition = (df['SMA_20'] > df['SMA_50']) & (df['Close'] > df['SMA_200']) & (df['RSI'] < 70)
    bear_condition = (df['SMA_20'] < df['SMA_50']) & (df['Close'] < df['SMA_200']) & (df['RSI'] > 30)
    
    df.loc[bull_condition, 'Signal'] = 1
    df.loc[bear_condition, 'Signal'] = -1
    df['Position_Change'] = df['Signal'].diff()
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
            if action == 1: 
                if path >= tp:
                    wins += 1
                    break
                elif path <= sl:
                    break
            else: 
                if path <= tp:
                    wins += 1
                    break
                elif path >= sl:
                    break
    return (wins / sims) * 100

if __name__ == "__main__":
    print(f"Starting NSE Scan for {len(NIFTY_TICKERS)} tickers...")
    signals_found = 0
    
    for ticker in NIFTY_TICKERS:
        print(f"Scanning {ticker}...")
        try:
            df = yf.Ticker(ticker).history(period="2y", interval="1d")
            if df.empty:
                continue
                
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            df = calculate_indicators(df)
            df = generate_signals(df)
            
            crossovers = df[df['Position_Change'] != 0]
            if not crossovers.empty:
                # STRICT FILTER: Only alert if the crossover happened exactly today
                if crossovers.index[-1] == df.index[-1]:
                    signals_found += 1
                    latest = crossovers.iloc[-1]
                    action = latest['Signal']
                    price = latest['Close']
                    atr = latest['ATR']
                    
                    if action == 1:
                        sl = price - (1.5 * atr)
                        tp = price + (3.0 * atr)
                        dir_str = "🟢 BUY"
                    else:
                        sl = price + (1.5 * atr)
                        tp = price - (3.0 * atr)
                        dir_str = "🔴 SELL"
                        
                    win_prob = run_monte_carlo(price, df['Log_Returns'], tp, sl, action)
                    final_call = "✅ EXECUTE TRADE" if win_prob >= 55.0 else "❌ SKIP TRADE"
                    
                    # Output formatting uses INR symbol (₹)
                    msg = (
                        f"🚨 *NSE SIGNAL: {ticker}*\n"
                        f"Action: {dir_str}\n"
                        f"Entry: ₹{price:.2f}\n"
                        f"Stop Loss: ₹{sl:.2f}\n"
                        f"Take Profit: ₹{tp:.2f}\n\n"
                        f"📊 *SIMULATION DATA*\n"
                        f"200 SMA Trend: Confirmed\n"
                        f"RSI Momentum: {latest['RSI']:.1f}\n"
                        f"Monte Carlo Win Prob: {win_prob:.1f}%\n"
                        f"Final Call: {final_call}"
                    )
                    
                    print(f"Triggering Telegram alert for {ticker}...")
                    send_telegram_message(msg)
                    
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            
    if signals_found == 0:
        print("No advanced NSE setups detected today.")