# Polymarket 5m BTC Momentum Bot

A low-latency trading proxy for Polymarket 5-minute Up/Down BTC markets that triggers momentum-based trades leveraging live limit orders mathematically bounded against Binance data.

## Features
- **Low Latency Price Feeds**: Uses Binance WebSocket directly for sub-millisecond BTC price updates to bypass oracle delays completely.
- **RPC Bandwidth Throttling**: API polling aggressively throttles until exactly `T-10s` before market close to preserve Polymarket rate limits naturally.
- **Simulation Engine**: Risk-free localized paper trading environment that tracks a $60 virtual bankroll against true live orderbooks and resolutions.
- **Limit Execution & Slippage Tracking**: Generates FAK Limit orders scaled 3-ticks (+0.03c) above the currently quoted midline to enforce strict precision inside unpredictable market bursts.
- **CSV Reporter**: Persists all quantitative metrics (latencies, signals, and price-gaps) directly into `trades.csv` for data analysis.

## Prerequisites

- Python 3.9+
- A funded Polygon EOA Wallet (or just execution privileges to run purely in Dry-Run mode)

## Setup

1. **Create and Activate a Virtual Environment**
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On MacOS/Linux:
source venv/bin/activate
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure Environment Variables**
Copy the example environment file and add your active Polymarket credentials:
```bash
cp .env.example .env
```
Inside `.env`, configure `POLY_WALLETS` and adjust strategy parameters if necessary. Keep your private keys perfectly local.

4. **Approve Token Allowances (First Time Only)**
To authorize Polymarket contracts to transact inherently with your wallet's USDC balance:
```bash
python -m src.main --approve
```

## Running the Bot

**Live Trading Mode:**
Executes securely via the native Polymarket Gamma API and CLOB. FAK Limit orders will spend directly off the mapped `TRADE_SIZE`.
```bash
python -m src.main
```

**Simulation (Dry Run) Mode:**
Initializes a $60.00 isolated virtual bankroll that simulates trades, tests limit slippages, and pulls resolutions organically.
```bash
python -m src.main --dry-run
```
