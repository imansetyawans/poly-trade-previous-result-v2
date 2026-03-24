"""
Token odds feed — continuously polls UP/DOWN midpoint prices from CLOB API.
"""
import logging
import asyncio
from src import config

log = logging.getLogger("polybot")

async def odds_feed_loop(state: dict, client) -> None:
    """
    Continuous loop that keeps state["up_odds"] and state["down_odds"]
    updated with live midpoint prices from the CLOB orderbook.
    """
    log.info("Starting Odds Monitor feed...")
    
    while True:
        sec = state.get("seconds_to_close", 999)
        force = state.get("force_odds_fetch", False)
        
        # Maximize RPC efficiency: Only fetch odds when within 10 seconds of market close
        if sec > 10.0 and not force:
            await asyncio.sleep(1.0)
            continue
            
        state["force_odds_fetch"] = False

        active_window = state.get("active_window")
        next_window = state.get("next_window")
        
        async def fetch_pair(win):
            if not win or not win.up_token_id or not win.down_token_id:
                return 0.0, 0.0
            try:
                from functools import partial
                loop = asyncio.get_event_loop()
                up_price_task = loop.run_in_executor(None, partial(client.get_price, win.up_token_id, side="BUY"))
                down_price_task = loop.run_in_executor(None, partial(client.get_price, win.down_token_id, side="BUY"))
                up_resp, down_resp = await asyncio.gather(up_price_task, down_price_task)
                
                up_p = float(up_resp.get("price", 0)) if isinstance(up_resp, dict) else float(up_resp or 0)
                down_p = float(down_resp.get("price", 0)) if isinstance(down_resp, dict) else float(down_resp or 0)
                return up_p, down_p
            except:
                return 0.0, 0.0

        # Update active window odds
        if active_window:
            au, ad = await fetch_pair(active_window)
            if au > 0: state["up_odds"] = au
            if ad > 0: state["down_odds"] = ad
            
        # Update NEXT window odds (critical for execution pricing)
        if sec < 15.0 and next_window:
            nu, nd = await fetch_pair(next_window)
            # Log for transparency in sim
            if nu > 0 or nd > 0:
                state["next_up_odds"] = nu if nu > 0 else 0.50
                state["next_down_odds"] = nd if nd > 0 else 0.50
            else:
                # Default to 0.50 if the orderbook is not yet populated
                state["next_up_odds"] = state.get("next_up_odds", 0.50)
                state["next_down_odds"] = state.get("next_down_odds", 0.50)

        # Polling frequency
        await asyncio.sleep(0.5)
