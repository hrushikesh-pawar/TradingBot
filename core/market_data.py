import pandas as pd
import pandas_ta as ta
import yfinance as yf
import logging
from typing import Optional

logger = logging.getLogger("MarketData")

class MarketDataEngine:
    @staticmethod
    def fetch_daily_ohlcv(symbol: str) -> Optional[pd.DataFrame]:
        try:
            # Fetch 1 year of daily data silently
            df = yf.download(symbol, period="365d", interval="1d", progress=False)
            
            if df.empty or len(df) < 50:
                return None
                
            # Clean up Yahoo Finance multi-index formatting issues
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [str(col).lower() for col in df.columns]

            # Calculate our core indicators
            df["ema_50"] = ta.ema(df["close"], length=50)
            df["ema_200"] = ta.ema(df["close"], length=200)
            df["atr_14"] = ta.atr(df["high"], df["low"], df["close"], length=14)
            
            return df.dropna()
            
        except Exception as e:
            logger.error(f"Failed to fetch {symbol}: {e}")
            return None