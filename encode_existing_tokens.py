# encode_existing_tokens.py
import base64, json, pathlib

d = pathlib.Path("~/.garmin_tokens").expanduser()
bundle = {
    "oauth1": json.loads((d / "oauth1_token.json").read_text()),
    "oauth2": json.loads((d / "oauth2_token.json").read_text()),
}
blob = base64.b64encode(json.dumps(bundle, default=str).encode("utf-8")).decode("ascii")
print(blob)
print(f"\nlen={len(blob)}  endswith '='={blob.endswith('=')}")