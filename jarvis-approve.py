#!/usr/bin/env python3
"""
Generate a local approval code for Telegram dangerous actions.
Writes the code to TELEGRAM_LOCAL_APPROVAL_FILE (from .env or env var).
"""

import os
import sys
import secrets

from dotenv import load_dotenv


def _generate_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


def main() -> int:
    load_dotenv()
    request_id = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if not request_id:
        print("Usage: ./jarvis-approve.py <REQUEST_ID>")
        return 2
    
    approval_file = os.getenv("TELEGRAM_LOCAL_APPROVAL_FILE", "").strip()
    if not approval_file:
        print("TELEGRAM_LOCAL_APPROVAL_FILE is not set.")
        return 2
    
    code = _generate_code()
    os.makedirs(os.path.dirname(os.path.abspath(approval_file)), exist_ok=True)
    with open(approval_file, "w", encoding="utf-8") as f:
        f.write(code)
    
    print(f"Request ID: {request_id}")
    print(f"Approval Code: {code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
