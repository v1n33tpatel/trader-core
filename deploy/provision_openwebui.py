#!/usr/bin/env python3
"""
Open-WebUI Automated Workspace & RAG Provisioner CLI
MoneyMakingMachine / QWERTY CORP

Usage:
  ./.venv/bin/python deploy/provision_openwebui.py --url http://192.168.2.15:8080 --key YOUR_KEY
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from feeds.openwebui_client import OpenWebUIClient


def print_banner():
    print("\033[1;36m" + "=" * 68)
    print(" 🚀 TraderCore -> Open-WebUI Automated Provisioner")
    print("    Workspace · Tools · RAG Knowledge · Dual Custom Models")
    print("=" * 68 + "\033[0m")


def main():
    parser = argparse.ArgumentParser(description="Provision Open-WebUI workspace for trader-core.")
    parser.add_argument("--url", default=os.getenv("OPEN_WEBUI_URL", "http://192.168.2.15:8080"), help="Open-WebUI Base URL")
    parser.add_argument("--key", default=os.getenv("OPEN_WEBUI_API_KEY", ""), help="Open-WebUI API Bearer Token")
    parser.add_argument("--fast-model", default="llama3.1:8b", help="Base model for Fast Orchestrator (default: llama3.1:8b)")
    parser.add_argument("--deep-model", default="deepseek-r1:7b", help="Base model for Deep Quant Reasoner (default: deepseek-r1:7b)")
    parser.add_argument("--non-interactive", action="store_true", help="Do not prompt for interactive input")
    args = parser.parse_args()

    print_banner()
    print(f"[*] Target Open-WebUI Host: \033[1;33m{args.url}\033[0m")
    print(f"[*] Fast Base Model:       \033[1;32m{args.fast_model}\033[0m")
    print(f"[*] Deep Base Model:       \033[1;35m{args.deep_model}\033[0m")

    if not args.key:
        print("\033[1;31m[!] Warning: No API key provided via --key or OPEN_WEBUI_API_KEY.\033[0m")
        print("    If Open-WebUI authentication is enabled, requests may return 401 Unauthorized.")
        if not args.non_interactive and sys.stdin.isatty():
            try:
                user_key = input("Enter Open-WebUI API Key (or press Enter to try unauthenticated): ").strip()
                if user_key:
                    args.key = user_key
            except (EOFError, KeyboardInterrupt):
                pass

    client = OpenWebUIClient(base_url=args.url, api_key=args.key)

    print("\n[1/4] Probing Open-WebUI connectivity...")
    conn = client.check_connection()
    if conn.get("status") == "online":
        print(f"    \033[1;32m✓ Online\033[0m (latency: {conn.get('latency_ms')} ms)")
    else:
        print(f"    \033[1;31m✗ Status: {conn.get('status')}\033[0m - {conn.get('error', '')}")
        if conn.get("status") == "unauthorized":
            print("    Please provide a valid Open-WebUI API Key generated under Settings > Account > API Keys.")
        sys.exit(1)

    print("\n[2/4] Deploying TraderCore Quant Hub Tools (deploy/open_webui_trader_tool.py)...")
    tool_res = client.deploy_tool()
    if tool_res.get("status") == "success":
        print(f"    \033[1;32m✓ Tool deployed:\033[0m ID '{tool_res.get('id')}' ({tool_res.get('action')})")
    else:
        print(f"    \033[1;31m✗ Tool deployment failed:\033[0m {tool_res.get('message')}")

    print("\n[3/4] Compiling & Uploading RAG Knowledge Playbooks...")
    rag_res = client.deploy_rag_playbooks()
    if rag_res.get("status") == "success":
        kb_name = rag_res.get("knowledge_name")
        files = rag_res.get("uploaded_files", [])
        print(f"    \033[1;32m✓ Knowledge Base created:\033[0m '{kb_name}' (ID: {rag_res.get('knowledge_id')})")
        for f in files:
            print(f"      - Embedded: {f.get('filename')}")
    else:
        print(f"    \033[1;31m✗ RAG deployment failed:\033[0m {rag_res.get('message')}")

    print("\n[4/4] Provisioning Dual Custom Models & Quick Prompts...")
    kb_id = rag_res.get("knowledge_id")
    model_res = client.deploy_dual_models(
        fast_base_model=args.fast_model,
        deep_base_model=args.deep_model,
        tool_id="trader_core_tools",
        knowledge_id=kb_id
    )
    for m in model_res.get("models", []):
        print(f"    \033[1;32m✓ Model:\033[0m {m.get('name')} ({m.get('status')})")

    prompts_res = client.deploy_prompts()
    for p in prompts_res.get("prompts", []):
        print(f"    \033[1;32m✓ Quick Command:\033[0m {p.get('command')} ({p.get('status')})")

    print("\n\033[1;32m" + "=" * 68)
    print(" ✓ Open-WebUI Workspace Successfully Provisioned!")
    print("=" * 68 + "\033[0m")
    print(f"Open your browser at \033[1;34m{args.url}\033[0m and start chatting:")
    print("  • Select 'TraderCore Orchestrator (Fast)' for rapid scans and commands.")
    print("  • Select 'TraderCore Quant Reasoner (Deep R1)' for deep institutional chain-of-thought.")
    print("  • Quick commands available: /scan, /macro, /portfolio, /evaluate\n")


if __name__ == "__main__":
    main()
