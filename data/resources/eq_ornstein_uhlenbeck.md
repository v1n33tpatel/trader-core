# [RESOURCE: EQUATION] Ornstein-Uhlenbeck Process & Mean-Reversion Half-Life

- **Resource ID**: `eq_ornstein_uhlenbeck`
- **Category**: `EQUATION`
- **Source**: Formula Standard / Quant Library
- **Last Updated**: 2026-10-17T15:32:26.945991+00:00
- **Tags**: #equation #ornstein_uhlenbeck #mean_reversion #equations #stochastic

## Executive Summary
Stochastic differential equation for estimating optimal statistical arbitrage and mean-reversion lookback windows.

---

## Full Content & Structured Data

### Continuous-Time Formulation
The Ornstein-Uhlenbeck (O-U) process models mean-reverting price action or spread deviations:
$$dX_t = \theta (\mu - X_t)dt + \sigma dW_t$$
Where:
- $\theta$ (or $\kappa$) = Speed of mean reversion.
- $\mu$ = Long-term structural mean (e.g. Value Area POC or 200-period SMA).
- $\sigma$ = Instantaneous volatility of the process.
- $W_t$ = Standard Wiener process (Brownian motion).

### Discrete Estimation via AR(1)
In discrete candle time-series, the process is estimated by regressing changes against lagged price:
$$\Delta X_t = \beta X_{t-1} + \alpha + \epsilon_t$$
Where $\beta = -\theta \Delta t$.

### Mean-Reversion Half-Life ($t_{1/2}$)
The half-life represents the expected time required for a price shock to decay halfway back to its structural mean:
$$t_{1/2} = -\frac{\ln(2)}{\beta} = \frac{\ln(2)}{\theta}$$

### Practical Strategy Rules
- **Half-Life $< 5$ Bars**: Rapid mean-reversion; ideal for intraday RSI-14 and Bollinger band mean-reversion scalps.
- **Half-Life $> 50$ Bars**: Structural trending regime; mean-reversion strategies fail; defer to FVG breakouts or trend following.
