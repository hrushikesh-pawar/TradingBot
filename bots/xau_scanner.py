import yfinance as yf
import pandas as pd
import sys
import os

# Connect to your core telegram module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.telegram_alerts import send_telegram_message 

def fetch_gold_data():
    print("Fetching 6 months of daily Gold data...")
    gold_ticker = yf.Ticker("GC=F") 
    df = gold_ticker.history(period="6mo", interval="1d")
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    df.dropna(inplace=True)
    print(f"Successfully loaded {len(df)} days of price action.")
    return df

def calculate_moving_averages(df):
    print("Calculating 20-day and 50-day SMAs...")
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    return df

def generate_signals(df):
    print("Analyzing moving average crossovers...")
    # 1 = Long (Bullish), -1 = Short (Bearish), 0 = Neutral
    df['Signal'] = 0
    df.loc[df['SMA_20'] > df['SMA_50'], 'Signal'] = 1
    df.loc[df['SMA_20'] < df['SMA_50'], 'Signal'] = -1
    
    # Identify the exact day the crossover happens
    df['Position_Change'] = df['Signal'].diff()
    return df

if __name__ == "__main__":
    gold_data = fetch_gold_data()
    gold_data = calculate_moving_averages(gold_data)
    gold_data = generate_signals(gold_data)
    
    crossovers = gold_data[gold_data['Position_Change'] != 0].dropna()
    
    if not crossovers.empty:
        latest = crossovers.iloc[-1]
        action = "🟢 BUY" if latest['Signal'] == 1 else "🔴 SELL"
        price = round(latest['Close'], 2)
        
        msg = f"🚨 *XAU/USD SIGNAL*\nAction: {action}\nEntry: ${price}\nStrategy: 20/50 SMA Crossover"
        
        print(f"Triggering Devil's Trading Bot for {action} at ${price}...")
        send_telegram_message(msg) 
    else:
        print("No XAU/USD crossovers detected today.")