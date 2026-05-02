#!/usr/bin/env python3
"""Upload TikTok automation secrets to GitHub Actions."""

import base64
import requests
from nacl import encoding, public

import os
GH_TOKEN = os.environ.get("GH_TOKEN", "")
REPO = "gotrendy-lb/gotrendy-tiktok-automation"

SECRETS = {
    # TikTok credentials (sandbox)
    "TIKTOK_ACCESS_TOKEN": os.environ.get("TIKTOK_ACCESS_TOKEN", ""),
    "TIKTOK_OPEN_ID": "-000pmOHIKqIpSRJrv5mE5VA5CzvyQL2dGsI",
    "TIKTOK_CLIENT_KEY": "sbawwtsizb9ps5a2ga",
    "TIKTOK_CLIENT_SECRET": "VQMKgETw4xvV6cqNMpzUDWqBa8hN8L85",
    "TIKTOK_REFRESH_TOKEN": os.environ.get("TIKTOK_REFRESH_TOKEN", ""),
    # Shared Dropbox (same as Instagram)
    "DROPBOX_APP_KEY": "xp2ita2ukyk9kdx",
    "DROPBOX_APP_SECRET": "kluwncua8skydkg",
    "DROPBOX_REFRESH_TOKEN": os.environ.get("DROPBOX_REFRESH_TOKEN", ""),
    "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
    "IMGUR_CLIENT_ID": "546c25a59c58ad7",
}

def encrypt_secret(public_key_b64, secret_value):
    public_key_bytes = base64.b64decode(public_key_b64)
    sealed_box = public.SealedBox(public.PublicKey(public_key_bytes))
    encrypted = sealed_box.encrypt(secret_value.encode('utf-8'))
    return base64.b64encode(encrypted).decode('utf-8')

# Get repo public key
headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
key_resp = requests.get(f"https://api.github.com/repos/{REPO}/actions/secrets/public-key", headers=headers)
key_data = key_resp.json()
key_id = key_data["key_id"]
pub_key = key_data["key"]
print(f"Got public key, key_id: {key_id}")

# Upload each secret
for name, value in SECRETS.items():
    encrypted = encrypt_secret(pub_key, value)
    r = requests.put(
        f"https://api.github.com/repos/{REPO}/actions/secrets/{name}",
        headers=headers,
        json={"encrypted_value": encrypted, "key_id": key_id}
    )
    status = "✅" if r.status_code in (201, 204) else f"❌ {r.status_code}: {r.text}"
    print(f"{status} {name}")

print("\nAll secrets uploaded!")
