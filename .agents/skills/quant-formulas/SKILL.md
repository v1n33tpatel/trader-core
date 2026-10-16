---
name: quant-formulas
description: >-
  Use this skill whenever implementing, analyzing, or debugging quantitative trading formulas,
  predictive signals (momentum, mean reversion, Ornstein-Uhlenbeck half-life), risk metrics
  (Sharpe, Sortino, Calmar, MaxDD), or position sizing models (volatility targeting, Kelly criterion).
---

# Quantitative Finance Formulas & Predictive Modeling Manual

Comprehensive mathematical definitions, Python implementations, and predictive modeling guidelines for algorithmic trading.

---

## 1. Returns & Compounding

### Simple vs. Log Returns:
* **Simple Return**: $R_t = \frac{P_t - P_{t-1}}{P_{t-1}} = \frac{P_t}{P_{t-1}} - 1$
* **Log Return**: $r_t = \ln\left(\frac{P_t}{P_{t-1}}\right) = \ln(P_t) - \ln(P_{t-1})$
* **Time-Additivity**: Log returns compound additively over $T$ periods: $r_{0, T} = \sum_{t=1}^T r_t$. Simple returns compound multiplicatively: $1 + R_{0, T} = \prod_{t=1}^T (1 + R_t)$.

```python
import numpy as np
import pandas as pd

def compute_returns(prices: pd.Series) -> tuple[pd.Series, pd.Series]:
    simple_ret = prices.pct_change().dropna()
    log_ret = np.log(prices / prices.shift(1)).dropna()
    return simple_ret, log_ret
```

---

## 2. Risk & Performance Metrics

### Sharpe Ratio:
$$\text{Sharpe} = \frac{\bar{R}_p - R_f}{\sigma_p} \cdot \sqrt{N}$$
*Measures excess return per unit of total risk (standard deviation).*

### Sortino Ratio:
$$\text{Sortino} = \frac{\bar{R}_p - R_f}{\sigma_{down}} \cdot \sqrt{N}, \quad \text{where } \sigma_{down} = \sqrt{\frac{1}{T}\sum_{t=1}^T \min(R_t - \tau, 0)^2}$$
*Penalizes only harmful downside volatility below minimum acceptable return $\tau$ (usually 0).*

### Maximum Drawdown (MDD) & Calmar:
$$\text{MDD} = \min_{t \in [0, T]} \left( \frac{W_t - \max_{s \le t} W_s}{\max_{s \le t} W_s} \right), \quad \text{Calmar} = \frac{\text{Annualized Return}}{|\text{MDD}|}$$

```python
def calculate_quant_metrics(returns: pd.Series, periods_per_year: int = 252, rf: float = 0.0) -> dict:
    wealth = (1.0 + returns).cumprod()
    total_ret = float(wealth.iloc[-1] - 1.0)
    ann_ret = float(wealth.iloc[-1] ** (periods_per_year / len(returns)) - 1.0)
    ann_vol = float(returns.std(ddof=1) * np.sqrt(periods_per_year))
    
    # Sharpe
    std = returns.std(ddof=1)
    sharpe = float(((returns.mean() - rf / periods_per_year) / (std or 1e-9)) * np.sqrt(periods_per_year))
    
    # Sortino (downside semi-deviation)
    neg_returns = returns[returns < 0]
    downside_std = float(np.sqrt((neg_returns ** 2).mean())) if len(neg_returns) > 0 else 1e-9
    sortino = float(((returns.mean() - rf / periods_per_year) / downside_std) * np.sqrt(periods_per_year))
    
    # Max Drawdown
    wealth_series = pd.concat([pd.Series([1.0]), wealth.reset_index(drop=True)], ignore_index=True)
    cummax = wealth_series.cummax()
    drawdown = (wealth_series - cummax) / cummax
    max_dd = float(drawdown.min())
    calmar = float(ann_ret / abs(max_dd)) if max_dd < 0 else 0.0
    
    return {
        "total_return": total_ret,
        "annualized_return": ann_ret,
        "annualized_volatility": ann_vol,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_dd,
        "calmar_ratio": calmar,
    }
```

---

## 3. Predictive Signals & Market Modeling

### A. Time Series Momentum (TSMOM)
$$S_t = \text{sign}(P_t - P_{t-k}), \quad w_t = \frac{\sigma_{\text{target}}}{\hat{\sigma}_t} \cdot S_t$$
*Predictive premise: Price changes over lookback $k$ persist over medium horizons due to investor underreaction and capital flows.*

### B. Mean Reversion Z-Score
$$Z_t = \frac{P_t - \mu_k}{\sigma_k}$$
*Predictive premise: When $|Z_t| \ge 2.0$, price is statistically stretched ($>2\sigma$) relative to rolling equilibrium and exhibits negative autocorrelation (high probability of reversion toward $\mu_k$).*

### C. Ornstein-Uhlenbeck Mean Reversion Half-Life
Continuous mean-reverting process:
$$dX_t = \theta(\mu - X_t)dt + \sigma dW_t$$
Discretized OLS regression on lagged spread:
$$\Delta X_t = \alpha + \beta X_{t-1} + \epsilon_t$$
* **Speed of Reversion**: $\theta = -\ln(1 + \beta) \approx -\beta$
* **Half-Life ($t_{1/2}$)**:
$$t_{1/2} = \frac{\ln(2)}{\theta} = -\frac{\ln(2)}{\beta}$$
*Significance: Tells the quant exactly how many bars a mean-reverting trade takes to close 50% of the price divergence.*

```python
import numpy as np
import pandas as pd

def calculate_half_life(series: pd.Series) -> float:
    lag = series.shift(1).dropna()
    delta = (series - lag).dropna()
    lag = lag.loc[delta.index]
    
    # Simple linear regression delta = alpha + beta * lag
    cov = np.cov(lag, delta)
    beta = cov[0, 1] / (cov[0, 0] or 1e-9)
    
    if beta >= 0:
        return float("inf")  # Non-mean reverting (trending or random walk)
    half_life = -np.log(2) / beta
    return float(half_life)
```

---

## 4. Position Sizing & Capital Preservation

### A. Volatility Targeting
Modulates portfolio exposure so dollar risk remains constant across high-volatility and low-volatility regimes:
$$w_t = \text{clip}\left(\frac{\sigma_{\text{target}}}{\hat{\sigma}_t} \cdot \text{signal}_t, -L_{\max}, L_{\max}\right)$$

### B. The Kelly Criterion & Payoff Ratio
Calculates the mathematically optimal fraction of wealth to allocate to maximize long-term compound geometric growth:
$$f^* = \frac{p \cdot b - (1 - p)}{b} = p - \frac{q}{b}$$
* $p$: Historical win rate ($0.0 \le p \le 1.0$)
* $q = 1 - p$: Loss rate
* $b$: Payoff ratio ($\frac{\text{Average Win \$}}{\text{Average Loss \$}}$)
* **Half-Kelly Rule**: Full Kelly generates severe drawdowns ($>50\%$). Real-world quantitative trading systems use $\frac{1}{2} f^*$ or $\frac{1}{4} f^*$ to safeguard against parameter uncertainty and non-Gaussian fat tails.

```python
def kelly_position_fraction(win_rate: float, avg_win: float, avg_loss: float, fraction: float = 0.5) -> float:
    if avg_loss <= 0 or win_rate <= 0:
        return 0.0
    b = avg_win / avg_loss
    f_star = win_rate - ((1.0 - win_rate) / b)
    if f_star <= 0:
        return 0.0
    return float(f_star * fraction)
```

---

## 5. Friction & Turnover Invariant
Turnover cost deduction per rebalance:
$$\text{Turnover}_t = |w_t - w_{t-1}|$$
$$\text{Cost}_t = \text{Turnover}_t \times \text{one\_way\_cost\_bps} \times 10^{-4}$$
$$\text{Net Return}_t = R_t - \text{Cost}_t$$
