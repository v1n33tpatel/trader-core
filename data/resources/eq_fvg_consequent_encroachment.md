# [RESOURCE: EQUATION] Fair Value Gap & Consequent Encroachment (50% CE)

- **Resource ID**: `eq_fvg_consequent_encroachment`
- **Category**: `EQUATION`
- **Source**: Formula Standard / Price Action
- **Last Updated**: 2026-10-17T15:32:27.063369+00:00
- **Tags**: #equation #fvg #consequent_encroachment #price_action #geometry

## Executive Summary
Exact geometric formula for Fair Value Gap boundaries and high-probability limit order entry levels.

---

## Full Content & Structured Data

### Structural Geometry of Fair Value Gaps
A Fair Value Gap (FVG) is a 3-candle imbalance footprint where aggressive institutional buying or selling creates an unfilled pocket:
- **Bullish FVG**: Candle 3's Low is strictly greater than Candle 1's High: $\text{Low}_3 > \text{High}_1$.
- **Bearish FVG**: Candle 3's High is strictly lower than Candle 1's Low: $\text{High}_3 < \text{Low}_1$.

### Consequent Encroachment (CE)
The midpoint of the imbalance band represents the institutional equilibrium price where limit orders achieve maximum structural fill probability:
$$\text{CE} = \text{FVG}_{\text{low}} + 0.50 \times (\text{FVG}_{\text{high}} - \text{FVG}_{\text{low}})$$

### Execution Rule
Never enter at the outermost threshold of an FVG on market orders. Place standalone limit orders strictly at the **50% CE** with structural invalidation (stop-loss) resting below the Candle 1 pivot low.
