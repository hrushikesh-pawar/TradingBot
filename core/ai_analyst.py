import os
import json
import time
import random
import logging
import pandas as pd
from google import genai
from google.genai import types

# Import the models we created in Step 2
from core.models import SystemConfig, GeminiForwardDecision

logger = logging.getLogger("AIAnalyst")

class GeminiForwardAnalyst:
    def __init__(self, config: SystemConfig):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key: raise ValueError("GEMINI_API_KEY not found in .env")
        self.client = genai.Client(api_key=api_key)
        self.model = config.gemini_model

    def evaluate_forward_setup(self, symbol: str, asset_type: str, df: pd.DataFrame, upcoming_events: list) -> GeminiForwardDecision:
        latest = df.iloc[-1]
        events_formatted = json.dumps(upcoming_events, indent=2)

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
3. OUTPUT: Provide direct, bullet-point style reasoning and explicitly define the probable outcome.
"""
        max_retries = 4
        base_delay = 4
        current_model = self.model
        fallback_model = "gemini-3.5-flash-lite"
        # The Exponential Backoff & Fallback Loop
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=current_model, contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", 
                        response_schema=GeminiForwardDecision, 
                        temperature=0.0
                    )
                )
                return GeminiForwardDecision.model_validate_json(response.text)
                
            except Exception as e:
                error_str = str(e)
                # If Google is overloaded (503) or rate-limiting us (429), pause and retry
                if "503" in error_str or "UNAVAILABLE" in error_str or "429" in error_str:
                    if attempt == 1 and current_model != fallback_model:
                        # Switch to fallback model on second retry to skip congestion
                        logger.warning(f"[{symbol}] Switching to fallback model ({fallback_model}) due to traffic...")
                        current_model = fallback_model
                        time.sleep(2)
                        continue

                    if attempt < max_retries - 1:
                        # Calculate wait time: 4s, 8s, 16s... plus random jitter
                        sleep_time = (base_delay * (2 ** attempt)) + random.uniform(0.5, 2.0)
                        logger.warning(f"[{symbol}] Gemini API High Demand (503). Retrying in {sleep_time:.1f}s (Attempt {attempt+1}/{max_retries})...")
                        time.sleep(sleep_time)
                    else:
                        logger.error(f"[{symbol}] Google API failed after {max_retries} attempts.")
                        raise e
                else:
                    # If it is a real code error, crash normally
                    raise e