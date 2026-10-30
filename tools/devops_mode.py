#!/usr/bin/env python3
"""Prepare chat setup/boundaries or restrict to Safe; never issue authority."""
import importlib.util
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location("devops_chat_modes", Path(__file__).resolve().parents[1]/"devops-platform-contracts/scripts/chat_modes.py")
chat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chat)
if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(chat.main())
