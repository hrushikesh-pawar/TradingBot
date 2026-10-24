import os
from typing import List, Literal
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

@dataclass
class SystemConfig:
    gemini_model: str = "gemini-3.5-flash"
    initial_capital: float = 10_000.0
    risk_per_trade_pct: float = 0.02
    atr_stop_multiplier: float = 1.5
    min_risk_reward: float = 2.0
    min_confidence: int = 7
    interactive_mode: bool = False
    
class GeminiForwardDecision(BaseModel):
    symbol: str
    asset_class: Literal["FOREX", "CRYPTO", "EQUITY_IN", "EQUITY_US"]
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