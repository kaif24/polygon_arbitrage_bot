# polygon_arbitrage_bot
# Polygon Arbitrage Detector Bot

A Python bot that monitors price differences of USDC-WETH across multiple decentralized exchanges (Uniswap, Quickswap, Sushiswap) on the Polygon blockchain. It detects and logs potential arbitrage opportunities by simulating trades considering fees and slippage, helping users identify profitable trades in real-time.

## Features

- Connects to Polygon RPC via Alchemy
- Fetches price quotes from Uniswap, Quickswap, and Sushiswap routers
- Calculates arbitrage opportunities based on price differences, fees, and slippage
- Logs profitable opportunities to a CSV file
- Prints detected arbitrage opportunities in the console

## Prerequisites

- Python 3.7+
- Web3.py
- pandas

## Installation

1. Clone the repo:

```bash
git clone https://github.com/yourusername/polygon-arbitrage-bot.git
cd polygon-arbitrage-bot

