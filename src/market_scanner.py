"""
Market discovery — find the active and next BTC btc-updown-5m windows via Gamma API.
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional
import json
import aiohttp
from src import config

log = logging.getLogger("polybot")

WINDOW_DURATION = 300  # 5 minutes in seconds

class MarketWindow:
    def __init__(self, condition_id, question_id, slug, start_date, end_date, price_to_beat, up_token_id, down_token_id):
        self.condition_id = condition_id
        self.question_id = question_id
        self.slug = slug
        self.start_date = start_date
        self.end_date = end_date
        self.price_to_beat = price_to_beat
        self.up_token_id = up_token_id
        self.down_token_id = down_token_id

def _parse_event_to_window(event: dict) -> Optional[MarketWindow]:
    """Parse a Gamma API event response into a MarketWindow."""
    try:
        markets = event.get("markets", [])
        if not markets:
            return None

        mkt = markets[0]

        end_str = mkt.get("endDate", "")
        if not end_str:
            return None
        end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

        start_str = mkt.get("eventStartTime", event.get("startTime", ""))
        if start_str:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        else:
            from datetime import timedelta
            start_dt = end_dt - timedelta(seconds=WINDOW_DURATION)

        event_metadata = event.get("eventMetadata", {})
        price_to_beat = float(event_metadata.get("priceToBeat", 0))

        clob_ids_raw = mkt.get("clobTokenIds", "[]")
        clob_ids = json.loads(clob_ids_raw) if isinstance(clob_ids_raw, str) else clob_ids_raw

        if len(clob_ids) < 2:
            return None

        outcomes_raw = mkt.get("outcomes", "[]")
        outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw

        up_token = clob_ids[0]
        down_token = clob_ids[1]

        for i, outcome in enumerate(outcomes):
            name = outcome.lower() if isinstance(outcome, str) else ""
            if "up" in name and i < len(clob_ids):
                up_token = clob_ids[i]
            elif "down" in name and i < len(clob_ids):
                down_token = clob_ids[i]

        return MarketWindow(
            condition_id=mkt.get("conditionId", ""),
            question_id=mkt.get("questionID", ""),
            slug=mkt.get("slug", event.get("slug", "")),
            start_date=start_dt,
            end_date=end_dt,
            price_to_beat=price_to_beat,
            up_token_id=up_token,
            down_token_id=down_token
        )

    except Exception as e:
        log.error("Failed to parse event: %s", e)
        return None

async def fetch_window(session: aiohttp.ClientSession, slug: str) -> Optional[MarketWindow]:
    try:
        # Gamma API uses /events endpoint
        url = f"{config.GAMMA_API_HOST}/events"
        async with session.get(url, params={"slug": slug}) as resp:
            if resp.status != 200:
                return None
            events = await resp.json()
            if not events:
                return None
            return _parse_event_to_window(events[0])
    except Exception as e:
        log.debug("Error fetching slug %s: %s", slug, e)
        return None

async def market_discovery_loop(state: dict) -> None:
    """
    Continuous loop that keeps state["active_window"] and state["next_window"] updated.
    """
    async with aiohttp.ClientSession() as session:
        while True:
            now = datetime.now(timezone.utc)
            now_ts = int(now.timestamp())
            
            # 5-minute alignment
            current_start = (now_ts // WINDOW_DURATION) * WINDOW_DURATION
            next_start = current_start + WINDOW_DURATION
            
            active_slug = f"btc-updown-5m-{current_start}"
            next_slug = f"btc-updown-5m-{next_start}"
            
            active_window = await fetch_window(session, active_slug)
            next_window = await fetch_window(session, next_slug)
            
            # --- CHAINLINK PRICE TO BEAT FIX ---
            if active_window and active_window.price_to_beat == 0.0:
                if now_ts >= active_window.start_date.timestamp():
                    target_ts = int(active_window.start_date.timestamp())
                    loop = asyncio.get_event_loop()
                    from src.chainlink import fetch_historical_chainlink_btc_sync
                    
                    oracle_price = await loop.run_in_executor(None, fetch_historical_chainlink_btc_sync, target_ts)
                    if oracle_price > 0:
                        active_window.price_to_beat = oracle_price
            
            old_active = state.get("active_window")
            if active_window and (not old_active or old_active.slug != active_window.slug):
                log.info("Discovered active window: %s | closes %s UTC", 
                         active_window.slug, active_window.end_date.strftime("%H:%M:%S"))
                state["up_odds"] = 0.0
                state["down_odds"] = 0.0
                state["force_odds_fetch"] = True
                
            old_next = state.get("next_window")
            if next_window and (not old_next or old_next.slug != next_window.slug):
                log.info("Discovered next window: %s", next_window.slug)
                state["next_up_odds"] = 0.50
                state["next_down_odds"] = 0.50
            
            # Preserve found PTB aggressively across passes for the SAME market
            if active_window and active_window.price_to_beat == 0.0 and old_active and old_active.slug == active_window.slug and old_active.price_to_beat > 0:
                active_window.price_to_beat = old_active.price_to_beat
                
            # Update state safely
            state["active_window"] = active_window
            state["next_window"] = next_window
            
            # When we are near the end of the window (T-10s), we poll faster to ensure 
            # we capture the next_window and priceToBeat updates.
            seconds_to_close = (current_start + WINDOW_DURATION) - now_ts
            
            if seconds_to_close <= 10.0:
                await asyncio.sleep(0.5)
            elif active_window is None:
                await asyncio.sleep(2.0)
            else:
                await asyncio.sleep(5.0)
