import math
from typing import Optional

# Notice how we easily import the schemas we created in Step 2!
from core.models import SystemConfig, GeminiForwardDecision, TradePlan

class RiskEngine:
    def __init__(self, config: SystemConfig):
        self.cfg = config

    def evaluate_and_size(
        self, 
        symbol: str, 
        capital: float, 
        current_price: float, 
        atr: float, 
        decision: GeminiForwardDecision, 
        exchange_rate: float = 1.0
    ) -> Optional[TradePlan]:
        
        if not decision.execute_order or decision.confidence < self.cfg.min_confidence:
            return None

        risk_budget = capital * self.cfg.risk_per_trade_pct
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

        raw_units = risk_budget / (distance * exchange_rate)
        
        # Determine if the asset allows fractional sizing (like BTC) or requires whole numbers (like Stocks/Forex)
        if decision.asset_class == "CRYPTO":
            units = round(raw_units, 4)
        else:
            units = math.floor(raw_units)

        if units <= 0: return None

        return TradePlan(
            symbol=symbol, 
            action=action, 
            entry_price=round(current_price, 4),
            stop_loss=round(stop_loss, 4), 
            take_profit=round(take_profit, 4),
            units=units, 
            risk_amount=round(units * distance * exchange_rate, 2),
            reward_to_risk=self.cfg.min_risk_reward,
            reasons_why=f"Macro: {decision.forward_catalyst} | Tech: {decision.thesis}",
            possible_outcome=decision.possible_outcome
        )