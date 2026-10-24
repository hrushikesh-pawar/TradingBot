import requests
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List

logger = logging.getLogger("MacroEngine")

class ForwardMacroEngine:
    CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

    @classmethod
    def get_upcoming_events(cls, currency_list: List[str], hours_ahead: int = 72) -> List[Dict]:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = requests.get(cls.CALENDAR_URL, headers=headers, timeout=10)
            if resp.status_code != 200: return []

            raw_events = resp.json()
            now = datetime.now(timezone.utc)
            cutoff = now + timedelta(hours=hours_ahead)

            relevant = []
            for ev in raw_events:
                c = ev.get("country", "")
                impact = ev.get("impact", "")
                
                if c in currency_list and impact == "High":
                    try:
                        ev_time = datetime.fromisoformat(ev["date"])
                        if now <= ev_time <= cutoff:
                            hours_until = round((ev_time - now).total_seconds() / 3600, 1)
                            relevant.append({
                                "currency": c, "event": ev.get("title"),
                                "impact": impact, "hours_until": hours_until,
                                "forecast": ev.get("forecast", "N/A"), "previous": ev.get("previous", "N/A")
                            })
                    except Exception:
                        continue
            return relevant
        except Exception as e:
            logger.error(f"Error fetching economic calendar: {e}")
            return []