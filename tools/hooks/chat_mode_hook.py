#!/usr/bin/env python3
"""Codex planning-mode adapter; stdin never authenticates execution authority.

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
        if event.get("hook_event_name") == "UserPromptSubmit" and isinstance(event.get("prompt"), str) and event["prompt"].strip().casefold() in chat.SAFE_MESSAGES:
            # Remote cancellation must not depend on availability of local draft
            # state. The broker itself authenticates this client via mutual TLS.
            profile = chat.ROOT/"broker-client.json"
            if profile.exists() or profile.is_symlink():
                client = chat.module("host_broker_restriction_client", chat.ROOT/"tools/devops_exec.py")
                result = client.call_broker(chat.read(profile), {"mode": "safe", "grant": None}, "restrict")
                if result.get("status") != "restricted": raise ValueError("broker restriction unconfirmed")
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "BROKER_SAFE: prior higher-mode grants for this protected client are restricted. Existing admitted work may require containment."}}))
                return 0
        result = chat.host_event(event)
        if result:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": event["hook_event_name"], "additionalContext": result}}, ensure_ascii=True))
        return 0
    except Exception:
        print(json.dumps({"systemMessage": "DevOps mode confirmation blocked: unavailable, expired, changed or mismatched boundaries; continue only authorized preparation/diagnosis."}))
        return 0  # Preserve the user's prompt; never fabricate an active grant.


if __name__ == "__main__":
    raise SystemExit(main())
