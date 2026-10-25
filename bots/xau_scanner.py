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

def fetch_gold_data():
    gold_ticker = yf.Ticker("GC=F") 
    df = gold_ticker.history(period="2y", interval="1d") # 2 years needed for 200 SMA
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
    return df

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
    
    # Bullish condition: 20>50 crossover, Price > 200 SMA (Uptrend), RSI < 70 (Not overbought)
    bull_condition = (df['SMA_20'] > df['SMA_50']) & (df['Close'] > df['SMA_200']) & (df['RSI'] < 70)
    
    # Bearish condition: 20<50 crossover, Price < 200 SMA (Downtrend), RSI > 30 (Not oversold)
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
    df = fetch_gold_data()
    df = calculate_indicators(df)
    df = generate_signals(df)
    
    crossovers = df[df['Position_Change'] != 0]
    
    if not crossovers.empty:
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
            f"🚨 *XAU/USD ADVANCED SIGNAL*\n"
            f"Action: {dir_str}\n"
            f"Entry: ${price:.2f}\n"
            f"Stop Loss: ${sl:.2f}\n"
            f"Take Profit: ${tp:.2f}\n\n"
            f"📊 *SIMULATION DATA*\n"
            f"200 SMA Trend: Confirmed\n"
            f"RSI Momentum: {latest['RSI']:.1f}\n"
            f"Monte Carlo Win Prob: {win_prob:.1f}%\n"
            f"Final Call: {final_call}"
        )
        
        send_telegram_message(msg) 
        
        # Log to Google Sheets
        today = datetime.now().strftime("%Y-%m-%d")
        log_trade(today, dir_str, round(price, 2), round(sl, 2), round(tp, 2), f"{win_prob:.1f}%", final_call)
         
    else:
        print("No advanced XAU/USD setups detected today.")