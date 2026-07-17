"""Post-run smoke tests: run AFTER `make run` (and, for the microservices
half, after triggering a migration from the Migrate page or running
`python scripts/run_local.py --all`). Exercises the real register -> login ->
create product -> add to cart -> checkout flow against whichever backends
are currently reachable — skips (rather than fails) a backend that isn't up,
since the microservices are expected to be down until migration runs."""
import uuid

import httpx
import pytest

MONOLITH_URL = "http://127.0.0.1:6000"
USER_SERVICE_URL = "http://127.0.0.1:5001"
PRODUCT_SERVICE_URL = "http://127.0.0.1:5002"
ORDER_SERVICE_URL = "http://127.0.0.1:5003"
BFF_URL = "http://127.0.0.1:8000"


def _is_up(url: str) -> bool:
    try:
        return httpx.get(f"{url}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def test_monolith_full_flow():
    if not _is_up(MONOLITH_URL):
        pytest.skip("monolith not running — start it with `make run` first")

    token = uuid.uuid4().hex[:8]
    username, email, password = f"user{token}", f"{token}@example.com", "secret123"

    r = httpx.post(f"{MONOLITH_URL}/api/user/create", data={"username": username, "email": email, "password": password})
    assert r.status_code == 200, r.text

    r = httpx.post(f"{MONOLITH_URL}/api/user/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    api_key = r.json()["api_key"]

    r = httpx.post(f"{MONOLITH_URL}/api/product/create", data={"name": f"P{token}", "slug": f"p{token}", "price": "1500"})
    assert r.status_code == 200, r.text
    product_id = r.json()["product"]["id"]

    headers = {"Authorization": f"Basic {api_key}"}
    r = httpx.post(f"{MONOLITH_URL}/api/order/add-item", data={"product_id": product_id, "qty": 2}, headers=headers)
    assert r.status_code == 200, r.text

    r = httpx.post(f"{MONOLITH_URL}/api/order/checkout", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["result"]["is_open"] is False


def test_microservices_full_flow():
    services_up = all(_is_up(u) for u in (USER_SERVICE_URL, PRODUCT_SERVICE_URL, ORDER_SERVICE_URL))
    if not services_up:
        pytest.skip("microservices not all running — start them from the Migrate page (local mode) first")

    token = uuid.uuid4().hex[:8]
    username, email, password = f"user{token}", f"{token}@example.com", "secret123"

    r = httpx.post(f"{USER_SERVICE_URL}/api/user/create", data={"username": username, "email": email, "password": password})
    assert r.status_code == 200, r.text

    r = httpx.post(f"{USER_SERVICE_URL}/api/user/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    api_key = r.json()["api_key"]

    r = httpx.post(f"{PRODUCT_SERVICE_URL}/api/product/create", data={"name": f"P{token}", "slug": f"p{token}", "price": "1500"})
    assert r.status_code == 200, r.text
    product_id = r.json()["product"]["id"]

    headers = {"Authorization": f"Basic {api_key}"}
    r = httpx.post(f"{ORDER_SERVICE_URL}/api/order/add-item", data={"product_id": product_id, "qty": 2}, headers=headers)
    assert r.status_code == 200, r.text  # order-service calls user-service internally (ACL) to validate api_key

    r = httpx.post(f"{ORDER_SERVICE_URL}/api/order/checkout", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["result"]["is_open"] is False


def test_bff_reachable_and_proxies_correctly():
    if not _is_up(BFF_URL):
        pytest.skip("bff not running — start it with `make run` first")
    if not _is_up(MONOLITH_URL):
        pytest.skip("monolith not running")

    r = httpx.get(f"{BFF_URL}/api/shop/monolith/products")
    assert r.status_code == 200
    assert "results" in r.json()
