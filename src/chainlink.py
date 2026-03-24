"""
Chainlink Price Fetcher — Retrieves exact historical BTC/USD start-of-window prices via binary search.
"""
import logging
from web3 import Web3
from src import config

log = logging.getLogger("polybot")

CHAINLINK_BTC_USD = "0xc907E116054Ad103354f2D350FD2514433D57F6f"
CHAINLINK_ABI = [
    {"inputs": [],"name": "latestRoundData","outputs": [{"name": "roundId", "type": "uint80"},{"name": "answer", "type": "int256"},{"name": "startedAt", "type": "uint256"},{"name": "updatedAt", "type": "uint256"},{"name": "answeredInRound", "type": "uint80"}],"stateMutability": "view","type": "function"},
    {"inputs": [{"name": "_roundId", "type": "uint80"}],"name": "getRoundData","outputs": [{"name": "roundId", "type": "uint80"},{"name": "answer", "type": "int256"},{"name": "startedAt", "type": "uint256"},{"name": "updatedAt", "type": "uint256"},{"name": "answeredInRound", "type": "uint80"}],"stateMutability": "view","type": "function"},
    {"inputs": [],"name": "decimals","outputs": [{"name": "", "type": "uint8"}],"stateMutability": "view","type": "function"},
]

_historical_price_cache = {}

def fetch_historical_chainlink_btc_sync(target_ts: int) -> float:
    """
    Synchronously fetches the exact Chainlink BTC/USD price at or immediately preceding target_ts.
    Uses binary search over the blockchain data for API efficiency.
    """
    if target_ts in _historical_price_cache:
        return _historical_price_cache[target_ts]

    rpcs = [config.POLYGON_RPC_URL] if config.POLYGON_RPC_URL else []
    rpcs.extend(config.POLYGON_RPC_FALLBACKS)

    for rpc in rpcs:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 5}))
            if not w3.is_connected():
                continue
                
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(CHAINLINK_BTC_USD),
                abi=CHAINLINK_ABI,
            )
            decimals = contract.functions.decimals().call()
            latest = contract.functions.latestRoundData().call()
            round_id = latest[0]

            left, right = 0, 300
            found_price = 0.0

            while left <= right:
                mid = (left + right) // 2
                data = contract.functions.getRoundData(round_id - mid).call()
                ts = data[3]
                price = data[1] / (10 ** decimals)

                if ts == target_ts:
                    found_price = price
                    break
                elif ts > target_ts:
                    left = mid + 1
                    found_price = price
                else:
                    right = mid - 1

            if found_price > 0:
                _historical_price_cache[target_ts] = found_price
                log.info("CHAINLINK: Fetched historical start-of-window proxy PTB: $%.2f", found_price)
                return found_price
                
        except Exception as e:
            log.debug("Historical Chainlink RPC %s failed: %s", rpc, e)
            
    return 0.0
