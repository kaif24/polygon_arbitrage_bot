import time
from web3 import Web3
import pandas as pd
from datetime import datetime

# ---------------------- CONFIGURATION ---------------------- #

POLYGON_RPC = "https://polygon-mainnet.g.alchemy.com/v2/t7BD_4UZiRVFBwnkvFbBw"

print("Starting arbitrage bot...")

# Initialize web3 with timeout
web3 = Web3(Web3.HTTPProvider(POLYGON_RPC, request_kwargs={"timeout": 10}))

print("Start Initializing Web3 Connection")
if web3.is_connected():
    print("Success Connected to Polygon RPC")
else:
    print("Failed to connect to Polygon RPC")
    exit(1)

# DEX routers (Polygon addresses)
DEXES = {
    "Uniswap": {
        "router": Web3.to_checksum_address("0xedf6066a2b290C185783862C7F4776A2C8077AD1")  # Uniswap V2 Router02 on Polygon
    },
    "Quickswap": {
        "router": Web3.to_checksum_address("0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff")  # Quickswap Router
    },
    "Sushiswap": {
        "router": Web3.to_checksum_address("0x1b02da8cb0d097eb8d57a175b88c7d8b47997506")  # Sushiswap Router
    }
}

# Tokens: USDC-WETH
TOKEN0 = {
    "symbol": "USDC",
    "address": Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"),
    "decimals": 6
}
TOKEN1 = {
    "symbol": "WETH",
    "address": Web3.to_checksum_address("0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"),
    "decimals": 18
}

# Router ABI (only methods needed)
ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [
            {"internalType": "uint256[]", "name": "", "type": "uint256[]"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

# Trading settings
START_AMOUNT = 100 * (10 ** TOKEN0["decimals"])  # Starting with 100 USDC
TRADING_PAIR = [TOKEN0["address"], TOKEN1["address"]]
FEE_RATE = 0.003   # 0.3% per swap
SLIPPAGE = 0.001   # 0.1% slippage
MIN_PROFIT = 1     # USD profit threshold

# ---------------------- BOT MAIN LOGIC ---------------------- #

def get_amount_out(router_address, amount_in, path):
    print(f"[DEBUG] Querying router: {router_address} for path {path}...")
    router = web3.eth.contract(address=router_address, abi=ROUTER_ABI)
    try:
        amounts = router.functions.getAmountsOut(amount_in, path).call()
        print(f"[DEBUG] Got amounts: {amounts}")
        return amounts[-1]
    except Exception as e:
        print(f"[ERROR] Query failed for {router_address}: {e}")
        return None


def fetch_prices():
    """Returns {DEX: price (USDC per WETH)}"""
    prices = {}
    for dex, data in DEXES.items():
        out_weth = get_amount_out(data["router"], START_AMOUNT, TRADING_PAIR)
        if out_weth:
            prices[dex] = (START_AMOUNT / out_weth) * (10 ** (TOKEN1["decimals"] - TOKEN0["decimals"]))
        else:
            prices[dex] = None
    return prices


def find_arbitrage(prices):
    """Find arbitrage opportunities"""
    opps = []
    dexes = list(prices.keys())
    for i in range(len(dexes)):
        for j in range(len(dexes)):
            if i == j or prices[dexes[i]] is None or prices[dexes[j]] is None:
                continue
            buy_dex, sell_dex = dexes[i], dexes[j]
            buy_price = prices[buy_dex]
            sell_price = prices[sell_dex]
            if buy_price < sell_price:
                usdc_start = START_AMOUNT
                # Buy WETH
                amount_weth = (usdc_start * (1 - FEE_RATE)) / buy_price
                amount_weth *= (1 - SLIPPAGE)
                # Sell WETH
                usdc_final = amount_weth * sell_price * (1 - FEE_RATE)
                usdc_final *= (1 - SLIPPAGE)
                profit = usdc_final - usdc_start
                if profit > MIN_PROFIT:
                    opps.append({
                        "timestamp": datetime.utcnow().isoformat(),
                        "buy_on": buy_dex,
                        "sell_on": sell_dex,
                        "buy_price": buy_price,
                        "sell_price": sell_price,
                        "profit": profit / (10 ** TOKEN0["decimals"]),
                    })
    return opps


# Logging setup
df_log = pd.DataFrame(columns=["timestamp", "buy_on", "sell_on", "buy_price", "sell_price", "profit"])


def main_loop(interval_seconds=20):
    global df_log
    print("--- Polygon Arbitrage Detector Bot ---")
    while True:
        prices = fetch_prices()
        print(f"[INFO] Prices @ {datetime.utcnow().isoformat()} : {prices}")
        opps = find_arbitrage(prices)
        if opps:
            for opp in opps:
                print(f"[ARBITRAGE] BUY {opp['buy_on']} @ {opp['buy_price']:.4f}, "
                      f"SELL {opp['sell_on']} @ {opp['sell_price']:.4f} | Profit: ${opp['profit']:.2f}")
            # Log opportunities
            df_log = pd.concat([df_log, pd.DataFrame(opps)], ignore_index=True)
            df_log.to_csv("arbitrage_log.csv", index=False)
        else:
            print("[INFO] No arbitrage opportunity found.")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main_loop(interval_seconds=6)
