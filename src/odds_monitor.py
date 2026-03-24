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

        window = state.get("active_window")
        if window and window.up_token_id and window.down_token_id:
            try:
                loop = asyncio.get_event_loop()
                from functools import partial
                
                # Fetch live lowest ask (BUY side price) for exactly what we would pay
                up_price_task = loop.run_in_executor(None, partial(client.get_price, window.up_token_id, side="BUY"))
                down_price_task = loop.run_in_executor(None, partial(client.get_price, window.down_token_id, side="BUY"))
                
                up_price, down_price = await asyncio.gather(up_price_task, down_price_task)

                # Parse response
                up_price = float(up_price.get("price", 0)) if isinstance(up_price, dict) else float(up_price or 0)
                down_price = float(down_price.get("price", 0)) if isinstance(down_price, dict) else float(down_price or 0)

                if up_price > 0:
                    state["up_odds"] = up_price
                if down_price > 0:
                    state["down_odds"] = down_price

            except Exception as e:
                log.warning("Odds fetch error: %s", e)
                
        # High frequency polling during the final 10 seconds
        await asyncio.sleep(0.5)
