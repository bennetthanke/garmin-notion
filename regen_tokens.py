"""Regenerate Garmin OAuth tokens and emit the GARMIN_TOKENS secret value.

Run interactively: it'll prompt for MFA code.
Output: a base64 blob you paste into the GARMIN_TOKENS repo secret.
"""
from __future__ import annotations
import base64
import json
import sys
from getpass import getpass
from pathlib import Path

import garth

email = input("Garmin email: ").strip()
password = getpass("Garmin password: ")

def mfa_prompt():
    return input("MFA code from Garmin: ").strip()

client = garth.Client(domain="garmin.com")
try:
    client.login(email, password, prompt_mfa=mfa_prompt)
except Exception as e:
    print(f"Login failed: {e}", file=sys.stderr)
    sys.exit(1)

o1 = client.oauth1_token
o2 = client.oauth2_token

bundle = {
    "oauth1": {
        "oauth_token": o1.oauth_token,
        "oauth_token_secret": o1.oauth_token_secret,
        "mfa_token": getattr(o1, "mfa_token", None),
        "mfa_expiration_timestamp": (
            o1.mfa_expiration_timestamp.isoformat()
            if getattr(o1, "mfa_expiration_timestamp", None)
            else None
        ),
        "domain": getattr(o1, "domain", "garmin.com"),
    },
    "oauth2": {
        k: getattr(o2, k)
        for k in o2.__dataclass_fields__
        if getattr(o2, k) is not None
    },
}

# Sanity dump to disk so you can also use it locally without re-logging in
out = Path.home() / ".garmin_tokens"
out.mkdir(exist_ok=True)
(out / "oauth1_token.json").write_text(json.dumps(bundle["oauth1"], indent=2, default=str))
(out / "oauth2_token.json").write_text(json.dumps(bundle["oauth2"], indent=2, default=str))
print(f"\nLocal tokens written to: {out}")

# Encode for the secret
blob = base64.b64encode(
    json.dumps(bundle, default=str).encode("utf-8")
).decode("ascii")

print("\n=== GARMIN_TOKENS secret value (copy everything between the lines) ===")
print(blob)
print("=== end ===")
print(f"\nLength: {len(blob)} chars")