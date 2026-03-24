"""
Simulated virtual portfolio engine for tracking trades against real Polymarket resolution data.
"""

import logging
import asyncio
import aiohttp
import json
from src import config

log = logging.getLogger("polybot")

class SimPortfolio:
    def __init__(self, start_balance: float):
        self.balance = start_balance
        self.positions = []  # list of dicts

    def add_position(self, market_id: str, token_id: str, side: str, shares: float, cost: float):
        self.positions.append({
            "market_id": market_id,
            "token_id": token_id,
            "side": side,
            "shares": shares,
            "cost": cost,
            "resolved": False
        })
        self.balance -= cost
        log.info("[SIM] Virtual Position Opened. Invested: $%.2f. Current Balance: $%.2f", cost, self.balance)

async def sim_resolution_loop(portfolio: SimPortfolio) -> None:
    """
    Periodically checks the Polymarket Gamma events API for closed status
    on unresolved virtual positions, and allocates real payouts.
    """
    log.info("[SIM] Resolution Tracker Started.")
    async with aiohttp.ClientSession() as session:
        while True:
            for pos in portfolio.positions:
                if not pos["resolved"]:
                    try:
                        url = f"{config.GAMMA_API_HOST}/events"
                        async with session.get(url, params={"slug": pos["market_id"]}) as resp:
                            if resp.status != 200:
                                continue
                            events = await resp.json()
                            if not events:
                                continue
                            
                            event = events[0]
                            markets = event.get("markets", [])
                            if not markets:
                                continue
                            
                            mkt = markets[0]
                            if mkt.get("closed", False):
                                # Market is resolved. Find which token won.
                                clob_ids = mkt.get("clobTokenIds", [])
                                if isinstance(clob_ids, str):
                                    clob_ids = json.loads(clob_ids)
                                    
                                prices_raw = mkt.get("outcomePrices", "[]")
                                if isinstance(prices_raw, str):
                                    prices = json.loads(prices_raw)
                                else:
                                    prices = prices_raw
                                    
                                if not prices or len(prices) != len(clob_ids):
                                    continue
                                
                                try:
                                    idx = clob_ids.index(pos["token_id"])
                                    win_prob = float(prices[idx])
                                    
                                    if win_prob >= 0.99:
                                        payout = pos["shares"] * 1.0
                                        profit = payout - pos["cost"]
                                        portfolio.balance += payout
                                        log.info("=========== [SIM PAYOUT] ===========")
                                        log.info("[SIM] Market %s RESOLVED YES!", pos["market_id"][-4:])
                                        log.info("[SIM] WON +$%.2f! New Balance: $%.2f", profit, portfolio.balance)
                                        log.info("====================================")
                                    else:
                                        profit = -pos["cost"]
                                        log.info("=========== [SIM PAYOUT] ===========")
                                        log.info("[SIM] Market %s RESOLVED NO!", pos["market_id"][-4:])
                                        log.info("[SIM] LOST -$%.2f. New Balance: $%.2f", abs(profit), portfolio.balance)
                                        log.info("====================================")
                                        
                                    pos["resolved"] = True
                                    pos["pnl"] = profit
                                except ValueError:
                                    log.error("[SIM] Token ID not found in market %s", pos["market_id"])
                    except Exception as e:
                        log.debug("Resolution check error: %s", e)
            await asyncio.sleep(60.0)
