import yfinance as yf
import pandas as pd

def fetch_gold_data():
    # GC=F is the highly reliable Gold Futures ticker on Yahoo Finance
    print("Fetching 6 months of daily Gold data...")
    gold_ticker = yf.Ticker("GC=F") 
    df = gold_ticker.history(period="6mo", interval="1d")
    
    # Clean up the dataframe to focus on price action
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    df.dropna(inplace=True)
    
    print(f"Successfully loaded {len(df)} days of price action.")
    return df

if __name__ == "__main__":
    gold_data = fetch_gold_data()
    print(gold_data.tail())