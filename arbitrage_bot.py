import time
from web3 import Web3
import pandas as pd
from datetime import datetime

# ----------------------------------------------------------
# 1. CONNECT TO POLYGON NETWORK
# ----------------------------------------------------------

# This is my Polygon Mainnet link from Alchemy
# It's like the "address" where our bot sends requests
POLYGON_RPC = "https://polygon-mainnet.g.alchemy.com/v2/t7BD_4UZiRVFBwnkvFbBw"

# Connect to Polygon network using Web3
# The timeout just means: "If we don’t get a response in 10 seconds, stop waiting"
web3 = Web3(Web3.HTTPProvider(POLYGON_RPC, request_kwargs={"timeout": 10}))

# ----------------------------------------------------------
# 2. DEX (EXCHANGES) WE WILL CHECK
# ----------------------------------------------------------
# These are the big decentralized exchanges (DEX) on Polygon
# We store their "router contract addresses" which let us check prices
DEXES = {
    "Uniswap": {
        "router": Web3.to_checksum_address("0xedf6066a2b290C185783862C7F4776A2C8077AD1")
    },
    "Quickswap": {
        "router": Web3.to_checksum_address("0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff")
    },
    "Sushiswap": {
        "router": Web3.to_checksum_address("0x1b02da8cb0d097eb8d57a175b88c7d8b47997506")
    }
}

# ----------------------------------------------------------
# 3. TOKENS WE ARE TRADING
# ----------------------------------------------------------
# We will check prices between USDC and WETH
# USDC = stablecoin (1 USDC ~ $1)
# WETH = Wrapped Ethereum
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

# ----------------------------------------------------------
# 4. CONTRACT FUNCTION WE NEED
# ----------------------------------------------------------
# We only need one function: getAmountsOut
# It tells us: "If I give you X USDC, how much WETH will I get?"
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

# ----------------------------------------------------------
# 5. TRADING SIMULATION SETTINGS
# ----------------------------------------------------------
START_AMOUNT = 100 * (10 ** TOKEN0["decimals"])  # Start with 100 USDC (scaled to blockchain decimals)
TRADING_PAIR = [TOKEN0["address"], TOKEN1["address"]]  # We go from USDC → WETH
FEE_RATE = 0.003    # 0.3% DEX fee
SLIPPAGE = 0.001    # 0.1% price movement allowed
MIN_PROFIT = 1      # We only care if profit is more than $1

# ----------------------------------------------------------
# FUNCTION: Get price from one DEX
# ----------------------------------------------------------
def get_amount_out(router_address, amount_in, path):
    """
    Talks to a DEX and asks:
    "If I give you X amount of token A, how much token B will you give me?"
    """
    print(f"[DEBUG] Asking {router_address} for {amount_in} via {path}")
    router = web3.eth.contract(address=router_address, abi=ROUTER_ABI)
    try:
        amounts = router.functions.getAmountsOut(amount_in, path).call()
        return amounts[-1]  # Last number is the final amount we’d get
    except Exception as e:
        print(f"[ERROR] Could not get price: {e}")
        return None

# ----------------------------------------------------------
# FUNCTION: Get prices from all DEXes
# ----------------------------------------------------------
def fetch_prices():
    """
    Checks price of WETH (in USDC) on each DEX.
    """
    prices = {}
    for dex, data in DEXES.items():
        out_weth = get_amount_out(data["router"], START_AMOUNT, TRADING_PAIR)
        if out_weth:
            # Convert to USDC price per WETH
            price = (START_AMOUNT / out_weth) * (10 ** (TOKEN1["decimals"] - TOKEN0["decimals"]))
            prices[dex] = price
        else:
            prices[dex] = None
    return prices

# ----------------------------------------------------------
# FUNCTION: Find arbitrage opportunities
# ----------------------------------------------------------
def find_arbitrage(prices):
    """
    Finds where we can buy cheap on one DEX and sell high on another.
    Returns a list of trades that give profit.
    """
    opps = []
    dexes = list(prices.keys())

    for i in range(len(dexes)):
        for j in range(len(dexes)):
            if i == j or prices[dexes[i]] is None or prices[dexes[j]] is None:
                continue

            buy_dex = dexes[i]
            sell_dex = dexes[j]
            buy_price = prices[buy_dex]
            sell_price = prices[sell_dex]

            # If buying price is cheaper than selling price → possible profit
            if buy_price < sell_price:
                usdc_start = START_AMOUNT

                # Step 1: Buy WETH
                amount_weth = (usdc_start * (1 - FEE_RATE)) / buy_price
                amount_weth *= (1 - SLIPPAGE)

                # Step 2: Sell WETH
                usdc_final = amount_weth * sell_price * (1 - FEE_RATE)
                usdc_final *= (1 - SLIPPAGE)

                profit = usdc_final - usdc_start

                # Only store if profit > $1
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

# ----------------------------------------------------------
# DATA STORAGE FOR LOGGING
# ----------------------------------------------------------
df_log = pd.DataFrame(columns=["timestamp", "buy_on", "sell_on", "buy_price", "sell_price", "profit"])

# ----------------------------------------------------------
# MAIN LOOP
# ----------------------------------------------------------
def main_loop(interval_seconds=20):
    """
    Runs forever: check prices → find arbitrage → log profit opportunities.
    """
    global df_log
    print("--- Polygon Arbitrage Detector Bot Started ---")

    while True:
        prices = fetch_prices()
        print(f"[INFO] Current Prices: {prices}")

        opportunities = find_arbitrage(prices)

        if opportunities:
            for opp in opportunities:
                print(f"[ARBITRAGE] Buy on {opp['buy_on']} at {opp['buy_price']:.4f}, "
                      f"Sell on {opp['sell_on']} at {opp['sell_price']:.4f} → "
                      f"Profit: ${opp['profit']:.2f}")

            df_log = pd.concat([df_log, pd.DataFrame(opportunities)], ignore_index=True)
            df_log.to_csv("arbitrage_log.csv", index=False)

        time.sleep(interval_seconds)

# ----------------------------------------------------------
# START PROGRAM
# ----------------------------------------------------------
if __name__ == "__main__":
    print("Starting Web3 connection...")
    if web3.is_connected():
        print("✅ Connected to Polygon!")
        main_loop(interval_seconds=6)
    else:
        print("❌ Could not connect. Check your RPC URL.")
