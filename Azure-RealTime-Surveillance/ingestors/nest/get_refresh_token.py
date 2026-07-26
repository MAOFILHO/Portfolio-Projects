"""One-time interactive helper to mint a Google OAuth refresh_token for the
Nest ingestor. Run once, paste the resulting refresh_token into .env, then
delete/forget it -- the script is not needed again unless access is revoked.

Usage:
    python get_refresh_token.py
"""

from __future__ import annotations

import sys
import urllib.parse

import requests

AUTH_URL = "https://nestservices.google.com/partnerconnections/{project_id}/auth"
TOKEN_URL = "https://www.googleapis.com/oauth2/v4/token"
REDIRECT_URI = "https://www.google.com"
SCOPE = "https://www.googleapis.com/auth/sdm.service"


def main() -> None:
    project_id = input("Device Access Project ID: ").strip()
    client_id = input("OAuth Client ID: ").strip()
    client_secret = input("OAuth Client Secret: ").strip()

    params = {
        "redirect_uri": REDIRECT_URI,
        "access_type": "offline",
        "prompt": "consent",
        "client_id": client_id,
        "response_type": "code",
        "scope": SCOPE,
    }
    auth_url = AUTH_URL.format(project_id=project_id) + "?" + urllib.parse.urlencode(params)

    print("\n1. Open this URL in a browser and authorize access to your Nest structure:\n")
    print(f"   {auth_url}\n")
    print("2. After granting access, you'll land on google.com with a `code=` query param in the URL.")
    code = input("3. Paste that code here: ").strip()

    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )
    if not response.ok:
        print(f"\nToken exchange failed: {response.status_code} {response.text}", file=sys.stderr)
        sys.exit(1)

    payload = response.json()
    print("\nSuccess. Add these to ingestors/nest/.env:\n")
    print(f"GOOGLE_CLIENT_ID={client_id}")
    print(f"GOOGLE_CLIENT_SECRET={client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={payload['refresh_token']}")
    print(f"GOOGLE_DEVICE_ACCESS_PROJECT_ID={project_id}")


if __name__ == "__main__":
    main()
