# [RESOURCE: WEBSITE] Binance Spot & Futures Liquidity Clustering Framework

- **Resource ID**: `web_binance_liquidity_guide`
- **Category**: `WEBSITE`
- **Source**: https://binance.com/research/liquidity-clustering
- **Last Updated**: 2026-10-17T15:32:27.884273+00:00
- **Tags**: #website #web #liquidity #binance #orderbook

## Executive Summary
Guide on how institutional algorithms utilize Equal Highs and Lows on Binance orderbooks to sweep liquidity.

---

## Full Content & Structured Data

### Liquidity Cluster Dynamics
In crypto spot and derivative markets, retail limit orders and stop-loss pools congregate at distinct psychological numbers and visible chart swing points (Equal Highs / Equal Lows).

### The Sweep Mechanics
1. **Engineered Drive**: Smart money pushes price into an obvious cluster of resting liquidity.
2. **Trigger Cascade**: Retail stops execute as market orders into institutional limit absorption books.
3. **Sharp Reversal**: Once liquidity is filled, the price immediately snaps back inside the Value Area, printing a long rejection shadow (pinbar).

### Strategy Rule
Never enter breakout market orders as price touches an unswept liquidity pool. Wait for the sweep candle to close, verify wick ratio $\ge 50\%$, and enter on the structural confirmation.
