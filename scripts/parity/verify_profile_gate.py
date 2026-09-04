r"""Send the frozen NT8 profile to the bridge and report what it did.

This is the acceptance check for plan 0.1d. It is expected to REFUSE on a box whose
global merge policy is MergeBackAdjusted, and that refusal is the passing outcome -
the gate binding is the thing being demonstrated. A run that succeeds means the
machine's globals already match the profile.

Run:
  .venv\Scripts\python.exe -m scripts.parity.verify_profile_gate
"""
from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.request

from scripts.parity.nt8_profile import build_request

BRIDGE = "http://localhost:7890/api/backtest"
TOKEN_FILE = pathlib.Path.home() / "Documents" / "NinjaTrader 8" / "mcp_token.txt"


def main() -> int:
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    body = build_request(
        "_McpTestBot", "MNQ 09-26", "2026-08-20", "2026-08-21",
        timeout_sec=90, max_trades=5,
    )
    print(f"sending profileHash: {body['profileHash']}")
    print(f"requireGlobals:      {body['requireGlobals']}")

    req = urllib.request.Request(
        BRIDGE,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        raw = urllib.request.urlopen(req, timeout=300).read()
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read()[:400]!r}")
        return 1

    d = json.loads(raw)
    err = d.get("error")
    print(f"\nerror: {err}")
    for m in d.get("globalMismatches") or []:
        print(f"  GLOBAL - {m}")
    for m in d.get("paramErrors") or []:
        print(f"  PARAM  - {m}")
    print(f"\neffectiveGlobals:   {d.get('effectiveGlobals')}")
    print(f"appliedParams:      {d.get('appliedParams')}")
    print(f"echoed profileHash: {d.get('profileHash')}")

    if err:
        print("\nREFUSED - the gate binds. Nothing ran, and the reason names what to change.")
    else:
        print("\nRAN - the machine's globals already match the profile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
