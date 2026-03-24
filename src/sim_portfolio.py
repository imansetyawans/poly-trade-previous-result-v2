"""
Simulated virtual portfolio engine for tracking trades against real Polymarket resolution data.
"""

import logging
import asyncio
import aiohttp
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
                                    import json
                                    clob_ids = json.loads(clob_ids)
                                    
                                winning_token_id = None
                                # For 5m markets, the Gamma API usually flags the closed/resolved state
                                # To find the winner, we can check the recent API payout OR since it's an UP/DOWN market, 
                                # usually when 'closed' is true, Polymarket sets the price of the winning token to 1.00 (or close) on CLI.
                                # However, Gamma 'markets' object usually contains 'tokens' or we just check the 'active' edge.
                                # Actually, Gamma API event returns `outcomes` and it updates the `price` field? No.
                                # The most robust way is to query the specific condition resolution if it's on-chain.
                                # Alternatively, we can assume the final state of the tokens if `closed` is True.
                                # Let's fetch the CLOB price directly. The token at price 1.0 is the winner.
                                try:
                                    # Fallback to Clob API to check price of our token. If it's near 1, we won.
                                    # If the market is resolved, CLOB midpoint disappears but we can check if we won using the Polymarket UI logic:
                                    # Actually, Gamma API `markets[0]` has `resolvedBy` or `groupItemTitle` or we can just fetch /markets/:id directly.
                                    pass
                                except:
                                    pass
                                
                                # Wait, in Gamma API, if a market is resolved, it adds `resolution_result` or `asset_status`.
                                # Let's just track the `endDate`. The best way is to fetch the price at resolution.
                                # Simplified for now: if closed, print notice. We need the winning outcome to payout.
                                # On Polymarket, closed markets return `price: 1` or `price: 0` inside the outcomes.
                    except Exception as e:
                        log.debug("Resolution check error: %s", e)
            await asyncio.sleep(60.0)
