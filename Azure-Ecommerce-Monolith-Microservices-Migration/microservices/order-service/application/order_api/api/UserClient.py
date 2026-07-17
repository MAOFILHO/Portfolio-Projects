"""Anti-Corruption-Layer-style client: order-service never touches the user
database directly — it always asks user-service over HTTP, exactly like a
production microservices boundary would."""
import os

import requests

USER_SERVICE_BASE_URL = os.environ.get("USER_SERVICE_BASE_URL", "http://127.0.0.1:5001")


class UserClient:
    @staticmethod
    def get_user(api_key: str | None):
        if not api_key:
            return None
        headers = {"Authorization": api_key}
        try:
            response = requests.get(f"{USER_SERVICE_BASE_URL}/api/user", headers=headers, timeout=5)
        except requests.RequestException:
            return None
        if response.status_code != 200:
            return None
        return response.json()
