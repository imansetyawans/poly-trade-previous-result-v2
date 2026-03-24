"""
Main entry point — async orchestrator for the Polymarket Momentum Bot.
"""

import sys
import asyncio
import argparse
import logging

from src.logger import setup_logging
from src.auth import create_clients, approve_allowances
from src.market_scanner import market_discovery_loop
from src.price_feed import price_feed_loop
from src.odds_monitor import odds_feed_loop
from src.strategy import strategy_loop
from src.reporter import init_csv
from src import config

async def print_state_loop(state: dict):
    """Simple loop to print out state for visibility since we don't have a dashboard yet."""
    log = logging.getLogger("polybot")
    while True:
        act = state.get("active_window")
        nxt = state.get("next_window")
        sec = state.get("seconds_to_close", 0)
        btc = state.get("btc_price", 0.0)
        ptb = act.price_to_beat if act else 0.0
        gap = abs(ptb - btc) if ptb > 0 and btc > 0 else 0.0
        up = state.get("up_odds", 0.0)
        dn = state.get("down_odds", 0.0)
        
        info_str = []
        info_str.append(f"BTC: ${btc:,.2f}")
        if act:
            info_str.append(f"Act: {act.slug[-4:]} (T-{sec:.1f}s, PTB=${ptb:,.2f}, Gap=${gap:.2f})")
            info_str.append(f"Odds: UP {up:.2f} / DN {dn:.2f}")
        if nxt:
            n_up = state.get("next_up_odds", 0.0)
            n_dn = state.get("next_down_odds", 0.0)
            info_str.append(f"Nxt: {nxt.slug[-4:]} (Odds: {n_up:.2f}/{n_dn:.2f})")
            
        log.info(" | ".join(info_str))
        
        if sec < 10.0:
            await asyncio.sleep(1.0)
        elif sec < 60.0:
            await asyncio.sleep(5.0)
        else:
            await asyncio.sleep(15.0)

async def run_bot(dry_run: bool = False):
    log = logging.getLogger("polybot")
    init_csv()

    state = {
        "btc_price": 0.0,
        "up_odds": 0.0,
        "down_odds": 0.0,
        "next_up_odds": 0.50,
        "next_down_odds": 0.50,
        "seconds_to_close": 999.0,
        "active_window": None,
        "next_window": None,
        "active_signal": None,
        "dry_run": dry_run
    }

    if dry_run:
        log.info("Starting DRY-RUN mode. (Virtual execution)")
        from py_clob_client.client import ClobClient
        from src.sim_portfolio import SimPortfolio, sim_resolution_loop
        
        client = ClobClient(config.CLOB_HOST, key="0"*64, chain_id=config.CHAIN_ID)
        portfolio = SimPortfolio(config.SIM_STARTING_BALANCE)
        
        tasks = [
            asyncio.create_task(market_discovery_loop(state)),
            asyncio.create_task(price_feed_loop(state)),
            asyncio.create_task(odds_feed_loop(state, client)),
            asyncio.create_task(strategy_loop(state, client, portfolio)),
            asyncio.create_task(print_state_loop(state)),
            asyncio.create_task(sim_resolution_loop(portfolio))
        ]
    else:
        config.validate_trading_config()
        log.info("Initializing Polymarket client...")
        clients = create_clients()
        if not clients:
            log.error("No clients configured!")
            return
        
        client = clients[0]
        log.info("Client connected!")
        
        tasks = [
            asyncio.create_task(market_discovery_loop(state)),
            asyncio.create_task(price_feed_loop(state)),
            asyncio.create_task(odds_feed_loop(state, client)),
            asyncio.create_task(strategy_loop(state, client)),
            asyncio.create_task(print_state_loop(state))
        ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        for t in tasks: t.cancel()

def main():
    parser = argparse.ArgumentParser("Polymarket Momentum Bot")
    parser.add_argument("--approve", action="store_true", help="Set token allowances")
    parser.add_argument("--dry-run", action="store_true", help="Run without auth and trading")
    args = parser.parse_args()
    
    setup_logging(headless=True)
    log = logging.getLogger("polybot")
    
    if args.approve:
        log.info("Setting up allowances...")
        approve_allowances()
        return
        
    log.info("Starting Polymarket Momentum Bot...")
    try:
        asyncio.run(run_bot(dry_run=args.dry_run))
    except KeyboardInterrupt:
        log.info("Shutdown complete.")

if __name__ == "__main__":
    main()
