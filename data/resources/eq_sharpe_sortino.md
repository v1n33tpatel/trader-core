# [RESOURCE: EQUATION] Sharpe & Sortino Risk-Adjusted Return Metrics

- **Resource ID**: `eq_sharpe_sortino`
- **Category**: `EQUATION`
- **Source**: Formula Standard / Quant Metrics
- **Last Updated**: 2026-10-17T15:32:27.184901+00:00
- **Tags**: #equation #sharpe #sortino #metrics #quant

## Executive Summary
Formulas for evaluating risk-adjusted return and downside volatility asymmetry across daily and crypto intervals.

---

## Full Content & Structured Data

### Sharpe Ratio
Measures excess return per unit of total standard deviation:
$$\text{Sharpe} = \frac{\mu - R_f}{\sigma} \times \sqrt{N}$$

### Sortino Ratio (Downside Risk Focus)
Penalizes only negative volatility below the minimum acceptable return (MAR or $R_f$):
$$\text{Sortino} = \frac{\mu - R_f}{\sigma_{\text{down}}} \times \sqrt{N}$$
Where downside deviation is:
$$\sigma_{\text{down}} = \sqrt{\frac{1}{T} \sum_{t=1}^T \min(0, R_t - R_f)^2}$$

### Annualization Multipliers ($N$)
- Daily Equities (252 trading days): $\sqrt{252} \approx 15.87$
- 24/7 Daily Crypto (365 days): $\sqrt{365} \approx 19.10$
- Hourly Crypto ($365 \times 24$): $\sqrt{8,760} \approx 93.59$
