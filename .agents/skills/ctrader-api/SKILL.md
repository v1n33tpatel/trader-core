---
name: ctrader-api
description: >-
  Use this skill whenever integrating, configuring, or testing cTrader AI Agent Connect
  (Remote MCP server at mcp.ctrader.com), cTrader Open API (Protobuf/JSON WebSockets),
  or writing mocked unit tests for forex/commodity trading.
---

# cTrader AI Agent Connect (Remote MCP) & Open API Integration Guide

This skill provides reference patterns, configurations, message structures, and invariants for integrating Spotware cTrader accounts via the **Model Context Protocol (MCP)** and the **cTrader Open API**.

---

## 1. cTrader AI Agent Connect & Remote MCP (`mcp.ctrader.com`)

Spotware's **AI Agent Connect** provides a standardized **Model Context Protocol (MCP)** interface for AI agents (Antigravity, Claude Code, Cursor, Windsurf, Codex, and Gemini CLI) to analyze markets, monitor accounts, and execute trades using natural language and structured tool calls.

### Architecture & Transports
* **Remote MCP Server Endpoint**: `https://mcp.ctrader.com/trading/mcp`
* **Transport**: Streamable HTTP (JSON-RPC over POST, or Server-Sent Events / SSE over GET)
* **Headers**:
  * `Authorization`: `Bearer <ACCOUNT_BEARER_TOKEN>`
  * `Content-Type`: `application/json`
  * `Accept`: `application/json, text/event-stream`

---

### Step-by-Step: Retrieving Your Per-Account Bearer Token
Reference: [help.ctrader.com](https://help.ctrader.com)

1. Open **cTrader Web** (`app.ctrader.com` or your broker-branded cTrader Web).
2. Log into your account using your **cTID** (cTrader ID).
3. Click the gear icon (**Settings**) in the bottom left, then select **Remote MCP** (or **AI Agent Connect**).
4. **MANDATORY**: From the account dropdown list, **select the specific Demo or Live trading account** you want the AI agent to access.
5. Copy the generated configuration snippet containing your unique, authenticated Bearer token.
6. *Active Session Invariant*: Remote MCP validation requires an active cTrader Web session under your cTID. Keep cTrader Web open in your browser during active sessions.

> [!WARNING]
> **Resolution of `"Invalid Authorization Bearer slug"`**:
> If you copy the template snippet without selecting an account, the bearer token will decode to:
> `{"plant":"ctrader","environment":"demo"}`
> This generic string lacks an account ID and cryptographic signature, causing `mcp.ctrader.com` to return:
> `HTTP/2 401 Unauthorized: {"error": "Invalid Authorization Bearer slug"}`
> Always ensure you choose an account from the dropdown before copying the token.

---

### Antigravity & AI Client Configuration (`mcp_config.json`)

To enable native cTrader MCP tools directly in Antigravity or your AI client, add the following to `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "ctrader": {
      "url": "https://mcp.ctrader.com/trading/mcp",
      "headers": {
        "Authorization": "Bearer <YOUR_ACCOUNT_SPECIFIC_BEARER_TOKEN>"
      }
    }
  }
}
```

---

### Remote MCP Tool Catalog

The cTrader Remote MCP server exposes the following tools:

| MCP Tool Name | Description | Key Parameters |
| :--- | :--- | :--- |
| `get_account_information` | Retrieves equity, balance, used margin, free margin, leverage, account currency. | None |
| `get_positions` | Returns list of open positions with live unrealized PnL, open price, volume, SL, and TP. | None |
| `place_order` | Places a market or pending order on a symbol. | `symbol`, `volume`, `side` (`BUY`/`SELL`), `stopLoss`, `takeProfit` |
| `modify_position` | Adjusts stop loss, take profit, or trailing stop on an active position. | `positionId`, `stopLoss`, `takeProfit` |
| `close_position` | Closes an active position partially or fully. | `positionId`, `volume` |
| `get_symbols` | Returns tradable symbols with pip size, digits, and leverage tiers. | `query` (optional) |
| `get_historical_prices` | Fetches historical candlestick bars for technical analysis. | `symbol`, `period` (`M1`, `M5`, `M15`, `H1`, `D1`), `count` |

---

### Python MCP Client Pattern (`brokers/ctrader_adapter.py`)

```python
import requests
import time
from typing import Any, Dict

def call_ctrader_mcp_tool(mcp_url: str, bearer_token: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Invokes a tool on the cTrader Remote MCP Server via JSON-RPC."""
    headers = {
        "Authorization": f"Bearer {bearer_token.strip()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }
    response = requests.post(mcp_url, json=payload, headers=headers, timeout=10.0)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise ValueError(f"cTrader MCP Error: {data['error']}")
    return data.get("result", {})
```

---

## 2. Classic cTrader Open API (Sockets & Protobuf)

For low-latency automated trading bots independent of web sessions, use the classic cTrader Open API.

### Hosts & Ports
* **Live Host**: `live.ctraderapi.com`
* **Demo Host**: `demo.ctraderapi.com`
* **Port 5035**: Protocol Buffers (TCP or WebSocket `wss://live.ctraderapi.com:5035`)
* **Port 5036**: JSON (TCP or WebSocket `wss://live.ctraderapi.com:5036`)

### Step 1: OAuth 2.0 Token Exchange (HTTP REST)
```python
import requests

def exchange_ctrader_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    url = "https://connect.spotware.com/apps/token"
    params = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    res = requests.post(url, data=params, timeout=5)
    res.raise_for_status()
    return res.json()  # Returns accessToken and refreshToken
```

### Step 2: Socket Authentication
1. **Application Auth** (`ProtoOAApplicationAuthReq`, payloadType 2100):
   ```json
   {
     "payloadType": 2100,
     "clientId": "YOUR_CLIENT_ID",
     "clientSecret": "YOUR_CLIENT_SECRET"
   }
   ```
2. **Account Auth** (`ProtoOAAccountAuthReq`, payloadType 2102):
   ```json
   {
     "payloadType": 2102,
     "ctidTraderAccountId": 1234567,
     "accessToken": "USER_ACCESS_TOKEN"
   }
   ```

---

## 3. Pytest Mocking Patterns

Never make live HTTP or WebSocket calls to `mcp.ctrader.com` or `ctraderapi.com` in tests. Always mock responses:

```python
def test_ctrader_mcp_account_info(monkeypatch):
    class MockMCPResponse:
        status_code = 200
        def json(self):
            return {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": '{"balance": 10000.0, "equity": 10250.0, "freeMargin": 9800.0, "currency": "USD"}'
                        }
                    ]
                }
            }
        def raise_for_status(self): pass

    monkeypatch.setattr("requests.post", lambda url, **kwargs: MockMCPResponse())
```
