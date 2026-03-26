"""
Configuration loader — reads .env and provides typed settings.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# ── Polymarket Auth ──────────────────────────────────────────────
POLY_WALLETS: str = os.getenv("POLY_WALLETS", "")
CHAIN_ID: int = 137  # Polygon Mainnet

def parse_wallets() -> list[dict]:
    """Parse POLY_WALLETS env var into list of wallet configs."""
    if not POLY_WALLETS:
        return []
    wallets = []
    for entry in POLY_WALLETS.split(","):
        parts = entry.strip().split(":")
        if len(parts) == 3:
            wallets.append({
                "private_key": parts[0],
                "funder_address": parts[1],
                "signature_type": int(parts[2])
            })
    return wallets

# ── API Hosts ────────────────────────────────────────────────────
CLOB_HOST: str = "https://clob.polymarket.com"
GAMMA_API_HOST: str = "https://gamma-api.polymarket.com"
POLYGON_RPC_URL: str = os.getenv("POLYGON_RPC_URL", "")

POLYGON_RPC_FALLBACKS: list[str] = [
    "https://polygon-rpc.com",
    "https://rpc-mainnet.matic.network",
    "https://polygon.drpc.org"
]

# ── Quantitative Strategy Settings ───────────────────────────────
TRADE_SIZE: float = float(os.getenv("TRADE_SIZE", "1.0"))
SIGNAL_TRIGGER_SECONDS: float = float(os.getenv("SIGNAL_TRIGGER_SECONDS", "3.0"))
EXECUTION_TRIGGER_SECONDS: float = float(os.getenv("EXECUTION_TRIGGER_SECONDS", "1.0"))
PRICE_GAP_THRESHOLD: float = float(os.getenv("PRICE_GAP_THRESHOLD", "50.0"))
SIM_STARTING_BALANCE: float = float(os.getenv("SIM_STARTING_BALANCE", "60.0"))

# === Advanced V2 Strategy Filters ===
USE_SESSION_SHIELD: bool = os.getenv("USE_SESSION_SHIELD", "true").lower() == "true"
TRADE_TIMEZONE: str = os.getenv("TRADE_TIMEZONE", "Asia/Bangkok")
TRADE_START_TIME: str = os.getenv("TRADE_START_TIME", "07:00")
TRADE_END_TIME: str = os.getenv("TRADE_END_TIME", "18:00")

USE_CONFIRMATION_FILTER: bool = os.getenv("USE_CONFIRMATION_FILTER", "true").lower() == "true"

# ── Contract Addresses (Polygon) required for Approvals ─────────
USDC_ADDRESS: str = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CONDITIONAL_TOKENS_ADDRESS: str = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
EXCHANGE_ADDRESS: str = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_EXCHANGE_ADDRESS: str = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
NEG_RISK_ADAPTER_ADDRESS: str = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"

POSITION_POLL_INTERVAL: int = int(os.getenv("POSITION_POLL_INTERVAL", "60"))
REDEEM_LOSSES: bool = os.getenv("REDEEM_LOSSES", "false").lower() == "true"

def validate_trading_config() -> None:
    """Validate that required credentials are present."""
    wallets = parse_wallets()
    if not wallets:
        print(f"[ERROR] Missing required env var: POLY_WALLETS")
        print(f"        Format: key1:address1:sigtype1,key2:address2:sigtype2")
        sys.exit(1)
