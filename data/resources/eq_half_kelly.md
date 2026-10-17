# [RESOURCE: EQUATION] Half-Kelly Capital Allocation Formula

- **Resource ID**: `eq_half_kelly`
- **Category**: `EQUATION`
- **Source**: Formula Standard / RiskSentinel
- **Last Updated**: 2026-10-17T15:32:26.813262+00:00
- **Tags**: #equation #kelly #sizing #equations #risk

## Executive Summary
Mathematical formula and boundary constraints for fractional Half-Kelly position sizing.

---

## Full Content & Structured Data

### Mathematical Formulation
The full Kelly Criterion determines the optimal fraction $f^*$ of capital to allocate to maximize the expected logarithm of wealth:
$$f^* = \frac{p \cdot b - q}{b}$$
Where:
- $p$ = Probability of a winning trade (Win Rate).
- $q = 1 - p$ = Probability of a losing trade.
- $b$ = Payoff ratio (Net Profit / Loss per trade, with $b \ge 2.0$ for mandatory 1:2 R:R setups).

### The Half-Kelly Invariant ($f^*_{\text{half}}$)
Full Kelly maximizes logarithmic growth but subjects capital to severe drawdowns (frequently exceeding 50%). In institutional systematic trading, we apply **Half-Kelly**:
$$f^*_{\text{half}} = 0.50 \times \left(\frac{p \cdot b - q}{b}\right)$$

### Execution Guardrails in RiskSentinel
1. If $f^* \le 0$, the mathematical expectation is negative ($E[R] < 0$); **ZERO** capital may be allocated.
2. The computed dollar allocation is clipped strictly at the RiskSentinel hard cap: $\min(f^*_{\text{half}} \cdot \text{Equity}, \$50.00)$.
3. Stop loss distance cannot exceed $2.0\%$ of entry price.
