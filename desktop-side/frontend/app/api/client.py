from __future__ import annotations

import json
from typing import Any

import httpx


class ApiClient:
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=15.0)

    def get(self, path: str, token: str | None = None, params: dict[str, Any] | None = None) -> Any:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = self.client.get(f"{self.base_url}{path}", headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict[str, Any] | None = None, token: str | None = None) -> Any:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = self.client.post(f"{self.base_url}{path}", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    def login(self, username: str, password: str) -> dict[str, Any]:
        form = {"username": username, "password": password}
        response = self.client.post(f"{self.base_url}/api/v1/auth/login", data=form)
        if response.status_code >= 400:
            raise RuntimeError(response.json().get("detail", "Login failed"))
        return response.json()

    def get_property_listings(self) -> list[dict[str, Any]]:
        response = self.client.get(
                f"{self.base_url}/api/v1/property-listings"
            )
        response.raise_for_status()
        return response.json()

    def register(
        self,
        username: str,
        password: str,
        full_name: str,
    ) -> dict[str, Any]:
        try:
            return self.post(
                '/api/v1/auth/register',
                {
                    'username': username,
                    'password': password,
                    'full_name': full_name,
                },
            )
        except httpx.HTTPStatusError as exc:
            try:
                error_payload = exc.response.json()
            except ValueError:
                error_payload = {}

            detail = error_payload.get('detail')
            if isinstance(detail, str):
                message = detail
            elif isinstance(detail, list):
                messages = [
                    str(item['msg'])
                    for item in detail
                    if isinstance(item, dict) and item.get('msg')
                ]
                message = '; '.join(messages) or 'Registration failed.'
            else:
                message = f'Registration failed (HTTP {exc.response.status_code}).'
            raise RuntimeError(message) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                'Unable to connect to the server. Check that it is running '
                'and try again.'
            ) from exc

    def health(self) -> dict[str, Any]:
        response = self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
