import re

with open("/home/vineet/trader-core/web_app.py", "r") as f:
    code = f.read()

# Update the PnL extraction block in get_portfolio()
old_block = '''                # Extract netProfit map across positions
                for pp in pnl_dict.get("positions", []):
                    pid = pp.get("positionID")
                    if pid is not None:
                        pnl_map[pid] = float(pp.get("netProfit", 0.0))
                
                unrealized_pnl = float(pnl_dict.get("netProfit", 0.0) or sum(pnl_map.values()))'''

new_block = '''                # Extract unrealizedPnL.pnL map across positions
                for pp in pnl_dict.get("positions", []):
                    pid = pp.get("positionID")
                    if pid is not None:
                        upnl_obj = pp.get("unrealizedPnL", {})
                        if isinstance(upnl_obj, dict):
                            val = upnl_obj.get("pnL", 0.0)
                        else:
                            val = pp.get("netProfit", 0.0)
                        pnl_map[pid] = float(val or 0.0)
                
                unrealized_pnl = float(sum(pnl_map.values())) if pnl_map else float(pnl_dict.get("netProfit", 0.0) or 0.0)'''

if old_block in code:
    code = code.replace(old_block, new_block)
    with open("/home/vineet/trader-core/web_app.py", "w") as f:
        f.write(code)
    print("Successfully patched PnL extraction in web_app.py")
else:
    print("Target block not matched directly, running full replacement.")
