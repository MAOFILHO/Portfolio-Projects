#!/usr/bin/env python3
"""Before/after performance benchmark — real, reproducible measurements, not
fabricated numbers.

IMPORTANT for a fair comparison: this hits the monolith and the microservice
DIRECTLY on their own URLs, NOT through the FastAPI BFF. Both sides are
Flask + gunicorn/dev-server with identical route/serialization code — the
only variable being measured is "one process/one DB" vs. "three
processes/three DBs", not an extra proxy hop or a different framework.

Target URLs are fetched from the BFF's GET /api/services (its live runtime
registry — config.RUNTIME_BASE_URLS), not hardcoded. Locally these are fixed
localhost ports; against Azure they're whatever Container Apps FQDNs the
live migration has created so far. This makes the same script work
unmodified in both environments while still hitting each backend directly.
If the BFF itself isn't reachable (e.g. running this before `make run`),
falls back to the local default ports so `make benchmark` still works
standalone.
"""
import argparse
import asyncio
import json
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "results"

DEFAULT_BFF_URL = "http://127.0.0.1:8000"
_LOCAL_FALLBACK_URLS = {"monolith": "http://127.0.0.1:6000", "product": "http://127.0.0.1:5002"}


async def _fetch_service_urls(bff_url: str) -> dict[str, str | None]:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{bff_url}/api/services")
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError:
        return dict(_LOCAL_FALLBACK_URLS)


async def _is_healthy(client: httpx.AsyncClient, base_url: str, timeout_s: float = 30.0) -> bool:
    """Container Apps on the Consumption plan scale to zero when idle — a
    healthy backend can still take several seconds to cold-start on its
    first request after being idle overnight (caught for real: a single 3s
    attempt reported the monolith as unreachable when it just hadn't
    finished waking up yet). Poll instead of a single short-timeout probe."""
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            r = await client.get(f"{base_url}/health", timeout=5)
            return r.status_code == 200
        except httpx.HTTPError:
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(2)


async def bench_operation(
    operation: str, base_url: str, method: str, path: str, requests: int, concurrency: int,
    data_fn=None, cleanup_slug_prefix: str | None = None,
) -> dict:
    async with httpx.AsyncClient() as client:
        latencies: list[float] = []
        errors = 0
        created_slugs: list[str] = []
        semaphore = asyncio.Semaphore(concurrency)

        async def worker(i: int):
            nonlocal errors
            async with semaphore:
                data = data_fn(i) if data_fn else None
                start = time.perf_counter()
                try:
                    r = await client.request(method, f"{base_url}{path}", data=data, timeout=10)
                    ok = r.status_code < 500
                    if ok and cleanup_slug_prefix and data:
                        created_slugs.append(data["slug"])
                except httpx.HTTPError:
                    ok = False
                elapsed_ms = (time.perf_counter() - start) * 1000
                latencies.append(elapsed_ms)
                if not ok:
                    errors += 1

        start = time.perf_counter()
        await asyncio.gather(*(worker(i) for i in range(requests)))
        wall_time = time.perf_counter() - start

        if created_slugs:
            # Benchmark-created products are throwaway load-test data, not
            # real catalog items — delete them so the Shop UI (which reads
            # from this same database) doesn't accumulate hundreds of
            # 'bench-*' rows every time the benchmark runs.
            await asyncio.gather(
                *(client.delete(f"{base_url}/api/product/{slug}", timeout=10) for slug in created_slugs),
                return_exceptions=True,
            )

    latencies.sort()
    p50 = statistics.median(latencies) if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else 0.0
    throughput = requests / wall_time if wall_time > 0 else 0.0

    return {
        "operation": operation,
        "requests": requests,
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "throughput_rps": round(throughput, 2),
        "errors": errors,
    }


def _unique_product_form(i: int) -> dict:
    token = uuid.uuid4().hex[:8]
    return {"name": f"bench-{token}-{i}", "slug": f"bench-{token}-{i}", "price": "999"}


async def run_all(requests: int, concurrency: int, bff_url: str) -> dict:
    """Measures whichever backend(s) are actually reachable right now, rather
    than requiring both. This matches the real lifecycle of this project: with
    `make run` (or right after `make provision` in Azure), only the monolith
    is up (pre-migration) — that's a legitimate, honest "before" measurement
    on its own, not a failure. Once migration creates product-service (and
    eventually stops the monolith), only the microservices are reachable — an
    equally legitimate "after" measurement. Only errors out if NEITHER is
    reachable, since there's nothing at all to measure in that case."""
    service_urls = await _fetch_service_urls(bff_url)
    monolith_url = service_urls.get("monolith")
    product_service_url = service_urls.get("product")

    async with httpx.AsyncClient() as client:
        monolith_up = bool(monolith_url) and await _is_healthy(client, monolith_url)
        product_service_up = bool(product_service_url) and await _is_healthy(client, product_service_url)

    if not monolith_up and not product_service_up:
        raise SystemExit(
            f"Neither the monolith ({monolith_url}) nor product-service ({product_service_url}) is "
            f"reachable — start at least one with `make run` first, or check {bff_url}/api/services."
        )

    measured: list[str] = []
    monolith_results: list[dict] = []
    microservices_results: list[dict] = []

    if monolith_up:
        measured.append("monolith")
        monolith_results = [
            await bench_operation("list_products", monolith_url, "GET", "/api/products", requests, concurrency),
            await bench_operation("create_product", monolith_url, "POST", "/api/product/create", requests, concurrency, _unique_product_form, cleanup_slug_prefix="bench-"),
        ]
    if product_service_up:
        measured.append("microservices")
        microservices_results = [
            await bench_operation("list_products", product_service_url, "GET", "/api/products", requests, concurrency),
            await bench_operation("create_product", product_service_url, "POST", "/api/product/create", requests, concurrency, _unique_product_form, cleanup_slug_prefix="bench-"),
        ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "measured": measured,
        "monolith": monolith_results,
        "microservices": microservices_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=50, help="requests per operation per backend")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--bff-url", default=DEFAULT_BFF_URL, help="Where to fetch current backend URLs from (GET /api/services)")
    args = parser.parse_args()

    result = asyncio.run(run_all(args.requests, args.concurrency, args.bff_url))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS_DIR / f"benchmark_{timestamp}.json"
    out_path.write_text(json.dumps(result, indent=2))

    print(json.dumps(result, indent=2))
    print(f"\nSaved to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
