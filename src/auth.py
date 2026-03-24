"""
Authentication — ClobClient setup for EOA wallets + token allowance approval.
"""

import logging
from py_clob_client.client import ClobClient
from src import config

log = logging.getLogger("polybot")


def create_client(wallet_config: dict) -> ClobClient:
    """Initialize and authenticate a ClobClient for a wallet."""
    log.info("Initializing ClobClient (chain=%d, addr=%s)", config.CHAIN_ID, wallet_config["funder_address"][:10])

    client = ClobClient(
        config.CLOB_HOST,
        key=wallet_config["private_key"],
        chain_id=config.CHAIN_ID,
        signature_type=wallet_config["signature_type"],
        funder=wallet_config["funder_address"],
    )

    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    client.creds = creds
    client.api_key = creds.api_key
    client.api_secret = creds.api_secret
    client.api_passphrase = creds.api_passphrase

    # Store wallet config for later use
    client.funder_address = wallet_config["funder_address"]
    client.signature_type_value = wallet_config["signature_type"]
    client.private_key = wallet_config["private_key"]

    log.info("API credentials set — ready to trade")
    return client

def create_clients() -> list[ClobClient]:
    """Initialize clients for all configured wallets."""
    wallets = config.parse_wallets()
    return [create_client(w) for w in wallets]


def approve_allowances() -> None:
    """
    One-time token allowance setup for all configured wallets.
    Approves USDC and ConditionalTokens for all three exchange contracts.
    Must be run before the first trade.
    """
    from web3 import Web3

    wallets = config.parse_wallets()
    if not wallets:
        log.error("No wallets configured in POLY_WALLETS")
        return

    log.info("Setting token allowances for %d wallet(s)...", len(wallets))

    rpcs = [config.POLYGON_RPC_URL] if config.POLYGON_RPC_URL else []
    rpcs.extend(config.POLYGON_RPC_FALLBACKS)

    w3 = None
    for url in rpcs:
        try:
            temp_w3 = Web3(Web3.HTTPProvider(url))
            if temp_w3.is_connected():
                w3 = temp_w3
                log.info("Connected to Polygon via %s", url)
                break
        except:
            continue

    if not w3:
        log.error("Could not connect to any Polygon RPC for approvals.")
        return

    for idx, wallet in enumerate(wallets):
        log.info("Processing wallet %d/%d: %s", idx+1, len(wallets), wallet["funder_address"][:10])
        account = w3.eth.account.from_key(wallet["private_key"])

        erc20_abi = [
            {
                "constant": False,
                "inputs": [
                    {"name": "spender", "type": "address"},
                    {"name": "amount", "type": "uint256"},
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function",
            }
        ]

        max_uint256 = 2**256 - 1
        tokens = [config.USDC_ADDRESS, config.CONDITIONAL_TOKENS_ADDRESS]
        spenders = [
            config.EXCHANGE_ADDRESS,
            config.NEG_RISK_EXCHANGE_ADDRESS,
            config.NEG_RISK_ADAPTER_ADDRESS,
        ]

        base_nonce = w3.eth.get_transaction_count(account.address)
        tx_index = 0

        for token_addr in tokens:
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(token_addr), abi=erc20_abi
            )
            for spender_addr in spenders:
                spender = Web3.to_checksum_address(spender_addr)
                tx = contract.functions.approve(spender, max_uint256).build_transaction(
                    {
                        "from": account.address,
                        "nonce": base_nonce + tx_index,
                        "gas": 60_000,
                        "gasPrice": w3.eth.gas_price,
                        "chainId": config.CHAIN_ID,
                    }
                )
                signed = account.sign_transaction(tx)
                tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
                log.info("  Sent approve(%s → %s) tx=%s", token_addr[:10], spender_addr[:10], tx_hash.hex())

                try:
                    w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
                except Exception as e:
                    log.warning("  Timeout or error waiting for receipt: %s", e)

                tx_index += 1

    log.info("All allowances set successfully!")
