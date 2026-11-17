from __future__ import annotations

from typing import Any, AsyncIterator, Iterator

import httpx
import httpx_sse

from arga_sdk.exceptions import ArgaAPIError


def _raise_for_status(response: httpx.Response) -> None:
    """Raise ArgaAPIError for non-2xx responses."""
    if response.is_success:
        return
    try:
        body = response.json()
        message = body.get("detail", body.get("message", response.text))
    except Exception:
        message = response.text
    raise ArgaAPIError(
        status_code=response.status_code,
        message=str(message),
        response=response,
    )


class SyncHTTPClient:
    """Synchronous HTTP client wrapper around httpx."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 60.0) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self._client.get(path, params=params)
        _raise_for_status(response)
        return response.json()

    def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        response = self._client.post(path, json=json)
        _raise_for_status(response)
        return response.json()

    def put(self, path: str, json: dict[str, Any]) -> Any:
        response = self._client.put(path, json=json)
        _raise_for_status(response)
        return response.json()

    def patch(self, path: str, json: dict[str, Any]) -> Any:
        response = self._client.patch(path, json=json)
        _raise_for_status(response)
        return response.json()

    def get_text(self, path: str) -> str:
        response = self._client.get(path)
        _raise_for_status(response)
        return response.text

    def get_redirect(self, path: str) -> str:
        # Return the signed artifact URL without forwarding Arga credentials to storage.
        response = self._client.get(path, follow_redirects=False)
        return _redirect_url(response)

    def delete(self, path: str) -> Any:
        response = self._client.delete(path)
        _raise_for_status(response)
        return response.json()

    def stream_sse(self, path: str) -> Iterator[dict[str, Any]]:
        """Stream SSE events from a GET endpoint."""
        with httpx_sse.connect_sse(
            self._client, "GET", path
        ) as event_source:
            for sse in event_source.iter_sse():
                import json as _json

                try:
                    data = _json.loads(sse.data)
                except (ValueError, TypeError):
                    data = sse.data
                yield {
                    "event": sse.event,
                    "data": data,
                    "id": sse.id,
                    "retry": sse.retry,
                }

    def close(self) -> None:
        self._client.close()


class AsyncHTTPClient:
    """Asynchronous HTTP client wrapper around httpx."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._client.get(path, params=params)
        _raise_for_status(response)
        return response.json()

    async def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        response = await self._client.post(path, json=json)
        _raise_for_status(response)
        return response.json()

    async def put(self, path: str, json: dict[str, Any]) -> Any:
        response = await self._client.put(path, json=json)
        _raise_for_status(response)
        return response.json()

    async def patch(self, path: str, json: dict[str, Any]) -> Any:
        response = await self._client.patch(path, json=json)
        _raise_for_status(response)
        return response.json()

    async def get_text(self, path: str) -> str:
        response = await self._client.get(path)
        _raise_for_status(response)
        return response.text

    async def get_redirect(self, path: str) -> str:
        response = await self._client.get(path, follow_redirects=False)
        return _redirect_url(response)

    async def delete(self, path: str) -> Any:
        response = await self._client.delete(path)
        _raise_for_status(response)
        return response.json()

    async def stream_sse(self, path: str) -> AsyncIterator[dict[str, Any]]:
        """Stream SSE events from a GET endpoint."""
        async with httpx_sse.aconnect_sse(
            self._client, "GET", path
        ) as event_source:
            async for sse in event_source.aiter_sse():
                import json as _json

                try:
                    data = _json.loads(sse.data)
                except (ValueError, TypeError):
                    data = sse.data
                yield {
                    "event": sse.event,
                    "data": data,
                    "id": sse.id,
                    "retry": sse.retry,
                }

    async def close(self) -> None:
        await self._client.aclose()


def _redirect_url(response: httpx.Response) -> str:
    from arga_sdk.exceptions import ArgaError

    if response.status_code not in {301, 302, 303, 307, 308}:
        _raise_for_status(response)
        raise ArgaError("Artifact endpoint did not return a signed URL")
    location = response.headers.get("location", "")
    url = httpx.URL(location)
    if url.scheme != "https" or not url.host or url.userinfo:
        raise ArgaError("Artifact endpoint returned an invalid signed URL")
    return location
