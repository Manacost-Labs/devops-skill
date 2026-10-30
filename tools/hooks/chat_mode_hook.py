#!/usr/bin/env python3
"""Trusted Codex UserPromptSubmit/SessionStart adapter; stdin is not identity proof.

Protect this runtime, configuration and issued-state writes from agent processes.
Do not expose this issuer entrypoint as an agent tool or claim same-UID isolation.
"""
import importlib.util
import json
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location("host_chat_modes", Path(__file__).resolve().parents[2]/"devops-platform-contracts/scripts/chat_modes.py")
chat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chat)


def main():
    try:
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536: raise ValueError("input limit")
        event = json.loads(raw.decode("utf-8"), object_pairs_hook=chat.authority().unique_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite event")))
        if not isinstance(event, dict): raise ValueError("event object")
        result = chat.host_event(event)
        if result:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": event["hook_event_name"], "additionalContext": result}}, ensure_ascii=True))
        return 0
    except Exception:
        print(json.dumps({"systemMessage": "DevOps mode confirmation blocked: unavailable, expired, changed or mismatched boundaries; continue only authorized preparation/diagnosis."}))
        return 0  # Preserve the user's prompt; never fabricate an active grant.


if __name__ == "__main__":
    raise SystemExit(main())
