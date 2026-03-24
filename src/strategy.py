"""
Strategy Engine — Signal generation at configurable triggers, executing Limit FAK.
"""

import logging
import asyncio
import time
from datetime import datetime, timezone
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY
from src.reporter import log_trade
from src import config

log = logging.getLogger("polybot")

# Settings bound directly from environment
SIGNAL_TRIGGER_SECONDS = config.SIGNAL_TRIGGER_SECONDS
EXECUTION_TRIGGER_SECONDS = config.EXECUTION_TRIGGER_SECONDS
PRICE_GAP_THRESHOLD = config.PRICE_GAP_THRESHOLD
TRADE_SIZE = config.TRADE_SIZE

async def submit_fak_order(client: ClobClient, market_id: str, token_id: str, trade_usd: float, expected_price: float, dry_run: bool = False, portfolio=None) -> dict:
    """Submit a Limit FAK market order synchronously in an executor."""
    
    # 3-tick slippage simulation and limit bounds
    limit_price = min(0.99, expected_price + 0.03)
    shares = round(trade_usd / limit_price, 2)
    
    if dry_run:
        log.info("[SIMULATION] Virtual FAK BUY %s @ Limit $%.2f (Shares: %.2f)", token_id[-6:], limit_price, shares)
        await asyncio.sleep(0.05)
        
        if portfolio:
            portfolio.add_position(market_id, token_id, "BUY", shares, trade_usd)
            
        return {
            "success": True,
            "status": "SIM_FILLED",
            "order_id": f"sim_{int(time.time())}",
            "latency": 50.0,
            "raw_response": "sim"
        }
        
    try:
        loop = asyncio.get_event_loop()
        
        def _place():
            order_args = OrderArgs(
                price=limit_price,
                size=shares,
                side=BUY,
                token_id=token_id
            )
            signed = client.create_order(order_args)
            return client.post_order(signed, orderType=OrderType.FAK)

        t0 = time.time()
        resp = await loop.run_in_executor(None, _place)
        latency = (time.time() - t0) * 1000.0  # in ms
        
        status = resp.get("status", resp.get("orderStatus", "UNKNOWN")) if isinstance(resp, dict) else str(resp)
        order_id = resp.get("orderID", resp.get("id", "")) if isinstance(resp, dict) else ""
        
        return {
            "success": "reject" not in str(status).lower() and "fail" not in str(status).lower(),
            "status": status,
            "order_id": order_id,
            "latency": latency,
            "raw_response": resp
        }
    except Exception as e:
        log.error("FAK execution failed: %s", e)
        return {"success": False, "status": "ERROR", "order_id": "", "latency": 0.0, "raw_response": str(e)}

async def strategy_loop(state: dict, client: ClobClient, portfolio=None) -> None:
    """
    Main loop.
    Monitors `seconds_to_close`.
    Generates signal at configured signal trigger.
    Executes at configured execution trigger targeting `next_window`.
    """
    last_signal_window = None

    while True:
        active_window = state.get("active_window")
        next_window = state.get("next_window")
        
        if not active_window:
            await asyncio.sleep(0.5)
            continue
            
        now = datetime.now(timezone.utc)
        seconds_to_close = (active_window.end_date - now).total_seconds()
        state["seconds_to_close"] = seconds_to_close

        if last_signal_window == active_window.slug:
            await asyncio.sleep(0.1)
            continue

        if seconds_to_close <= SIGNAL_TRIGGER_SECONDS:
            log.info("T-%.1fs TRIGGER: Evaluating Momentum Signal for %s", SIGNAL_TRIGGER_SECONDS, active_window.slug)
            
            btc_price = state.get("btc_price", 0.0)
            up_odds = state.get("up_odds", 0.0)
            down_odds = state.get("down_odds", 0.0)
            price_to_beat = active_window.price_to_beat
            
            if btc_price <= 0 or up_odds <= 0 or down_odds <= 0 or price_to_beat <= 0:
                log.warning("SIGNAL FAILED: Missing data (btc_price=%s, ptb=%s, up=%s, down=%s)", btc_price, price_to_beat, up_odds, down_odds)
                last_signal_window = active_window.slug
                continue
                
            gap = abs(price_to_beat - btc_price)
            
            if up_odds > down_odds:
                signal_side = "UP"
                selected_odds = up_odds
                opposing_odds = down_odds
            else:
                signal_side = "DOWN"
                selected_odds = down_odds
                opposing_odds = up_odds
                
            log.info("SIGNAL: %s (Odds: %.2f) | Gap: $%.2f", signal_side, selected_odds, gap)
            
            if gap < PRICE_GAP_THRESHOLD:
                log.warning("SIGNAL FAILED: Price gap $%.2f < $%.2f threshold", gap, PRICE_GAP_THRESHOLD)
                last_signal_window = active_window.slug
                continue
                
            log.info("SIGNAL VALIDATED: Preparing execution for %s", next_window.slug if next_window else "UNKNOWN")

            last_signal_window = active_window.slug
            state["active_signal"] = signal_side
            
            if not next_window:
                log.error("FATAL: Next window not found in state before execution! Aborting.")
                continue
                
            target_token = next_window.up_token_id if signal_side == "UP" else next_window.down_token_id
            
            wait_time = seconds_to_close - EXECUTION_TRIGGER_SECONDS
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                
            log.info("T-%.1fs TRIGGER: Executing FAK order for %s on %s...", EXECUTION_TRIGGER_SECONDS, signal_side, next_window.slug)
            exec_ts = datetime.utcnow().isoformat()
            
            dry_run = state.get("dry_run", False)
            result = await submit_fak_order(
                client=client, 
                market_id=next_window.slug, 
                token_id=target_token, 
                trade_usd=TRADE_SIZE, 
                expected_price=selected_odds, 
                dry_run=dry_run, 
                portfolio=portfolio
            )
            
            log_trade({
                "timestamp_utc": exec_ts,
                "current_market_id": active_window.slug,
                "next_market_id": next_window.slug,
                "signal_side": signal_side,
                "selected_odds": selected_odds,
                "opposing_odds": opposing_odds,
                "price_to_beat": price_to_beat,
                "btc_price": btc_price,
                "price_gap": gap,
                "latency_ms": result["latency"],
                "order_size": TRADE_SIZE,
                "success": result["success"],
                "status": result["status"],
                "order_id": result["order_id"]
            })
            
            if result["success"]:
                log.info("FAK EXECUTED: %s | Latency: %.1fms", result["status"], result["latency"])
            else:
                log.warning("FAK REJECTED: %s | Latency: %.1fms", result["status"], result["latency"])
                
        await asyncio.sleep(0.05)
