"""Generic reverse proxy so the React Shop page can talk to either backend
(the monolith or the three microservices) through one client interface.

/api/shop/monolith/{path}       -> forwarded to the monolith
/api/shop/microservices/{path}  -> forwarded to user-/product-/order-service
                                    based on the path prefix (user, product, order)
"""
import json

import httpx
from fastapi import APIRouter, Request, Response

from .. import config

router = APIRouter(prefix="/api/shop", tags=["shop"])


def _microservice_base_url(path: str) -> str:
    first_segment = path.split("/", 1)[0]
    for prefix in config.SERVICE_ROUTE_PREFIXES:
        if first_segment.startswith(prefix):
            base_url = config.RUNTIME_BASE_URLS[prefix]
            if base_url is None:
                raise ValueError(
                    f"'{prefix}-service' doesn't exist yet — it's created live during migration, not before."
                )
            return base_url
    raise ValueError(f"No microservice owns path '{path}'")


async def _forward(base_url: str, path: str, request: Request) -> Response:
    url = f"{base_url}/api/{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    body = await request.body()

    async with httpx.AsyncClient(timeout=10) as client:
        upstream = await client.request(
            request.method, url, headers=headers, params=request.query_params, content=body
        )
    return Response(content=upstream.content, status_code=upstream.status_code, media_type=upstream.headers.get("content-type"))


@router.api_route("/monolith/{path:path}", methods=["GET", "POST"])
async def proxy_monolith(path: str, request: Request):
    base_url = config.RUNTIME_BASE_URLS["monolith"]
    if base_url is None:
        return Response(content=json.dumps({"message": "Monolith is not available."}), status_code=503, media_type="application/json")
    return await _forward(base_url, path, request)


@router.api_route("/microservices/{path:path}", methods=["GET", "POST"])
async def proxy_microservices(path: str, request: Request):
    try:
        base_url = _microservice_base_url(path)
    except ValueError as exc:
        return Response(content=json.dumps({"message": str(exc)}), status_code=503, media_type="application/json")
    return await _forward(base_url, path, request)
