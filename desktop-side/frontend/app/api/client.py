from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx


class ApiClient:
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=15.0)

    def get(self, path: str, token: str | None = None, params: dict[str, Any] | None = None) -> Any:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = self.client.get(
            f"{self.base_url}{path}", headers=headers, params=params
        )
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict[str, Any] | None = None, token: str | None = None) -> Any:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = self.client.post(
            f"{self.base_url}{path}", json=payload, headers=headers
        )
        response.raise_for_status()
        return response.json()

    def put(self, path: str, payload: dict[str, Any], token: str | None = None) -> Any:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = self.client.put(
            f"{self.base_url}{path}", json=payload, headers=headers
        )
        response.raise_for_status()
        return response.json()

    def delete(self, path: str, token: str | None = None) -> None:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = self.client.delete(
            f"{self.base_url}{path}", headers=headers
        )
        response.raise_for_status()

    def _upload_file(
        self, path: str, file_path: str, payload: dict[str, Any], token: str | None
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        form = {key: str(value) for key, value in payload.items() if value is not None}
        with open(file_path, "rb") as file_handle:
            response = self.client.post(
                f"{self.base_url}{path}",
                data=form,
                files={"file": (Path(file_path).name, file_handle, content_type)},
                headers=headers,
                timeout=60.0,
            )
        response.raise_for_status()
        return response.json()

    # Documents
    def upload_document(self, file_path: str, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        return self._upload_file("/api/v1/documents/upload", file_path, payload, token)

    def create_document_version(self, document_id: str, file_path: str, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        path = f"/api/v1/documents/{quote(document_id, safe='')}/new-version"
        return self._upload_file(path, file_path, payload, token)

    def get_documents(self, token: str | None = None, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self.get("/api/v1/documents", token=token, params=params)

    def get_document(self, document_id: str, token: str | None = None) -> dict[str, Any]:
        return self.get(f"/api/v1/documents/{quote(document_id, safe='')}", token=token)

    def delete_document(self, document_id: str, token: str | None = None) -> None:
        self.delete(f"/api/v1/documents/{quote(document_id, safe='')}", token=token)

    def get_document_versions(self, document_id: str, token: str | None = None) -> list[dict[str, Any]]:
        return self.get(f"/api/v1/documents/{quote(document_id, safe='')}/versions", token=token)

    def update_document(self, document_id: str, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        return self.put(f"/api/v1/documents/{quote(document_id, safe='')}", payload, token=token)

    def _document_action(self, document_id: str, action: str, token: str | None) -> dict[str, Any]:
        return self.post(f"/api/v1/documents/{quote(document_id, safe='')}/{action}", token=token)

    def confirm_document(self, document_id: str, token: str | None = None) -> dict[str, Any]:
        return self._document_action(document_id, "confirm", token)

    def archive_document(self, document_id: str, token: str | None = None) -> dict[str, Any]:
        return self._document_action(document_id, "archive", token)

    def reject_document(self, document_id: str, token: str | None = None) -> dict[str, Any]:
        return self._document_action(document_id, "reject", token)

    def restore_document(self, document_id: str, token: str | None = None) -> dict[str, Any]:
        return self._document_action(document_id, "restore", token)

    def get_folders(self, token: str | None = None, include_archived: bool = False) -> list[dict[str, Any]]:
        return self.get(
            "/api/v1/documents/folders",
            token=token,
            params={"include_archived": include_archived},
        )

    def create_folder(self, name: str, parent_id: int | None = None, token: str | None = None) -> dict[str, Any]:
        return self.post(
            "/api/v1/documents/folders",
            {"name": name, "parent_id": parent_id},
            token=token,
        )

    def update_folder(self, folder_id: int, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        return self.put(f"/api/v1/documents/folders/{folder_id}", payload, token=token)

    def download_document(self, document_id: str, token: str | None = None, version: int | None = None) -> tuple[bytes, str, str]:
        headers = {"Accept": "*/*"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        path = f"/api/v1/documents/{quote(document_id, safe='')}/download"
        params = {"version": version} if version is not None else None
        response = self.client.get(
            f"{self.base_url}{path}", headers=headers, params=params, timeout=60.0
        )
        response.raise_for_status()
        return (
            response.content,
            response.headers.get("content-type", "application/octet-stream"),
            response.headers.get("content-disposition", ""),
        )

    # Authentication
    def login(self, username: str, password: str) -> dict[str, Any]:
        response = self.client.post(
            f"{self.base_url}/api/v1/auth/login",
            data={"username": username, "password": password},
        )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", "Login failed")
            except ValueError:
                detail = "Login failed"
            raise RuntimeError(detail)
        return response.json()

    def register(self, username: str, password: str, full_name: str) -> dict[str, Any]:
        try:
            return self.post(
                "/api/v1/auth/register",
                {"username": username, "password": password, "full_name": full_name},
            )
        except httpx.HTTPStatusError as exc:
            try:
                error_payload = exc.response.json()
            except ValueError:
                error_payload = {}
            detail = error_payload.get("detail")
            if isinstance(detail, str):
                message = detail
            elif isinstance(detail, list):
                messages = [
                    str(item["msg"])
                    for item in detail
                    if isinstance(item, dict) and item.get("msg")
                ]
                message = "; ".join(messages) or "Registration failed."
            else:
                message = f"Registration failed (HTTP {exc.response.status_code})."
            raise RuntimeError(message) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                "Unable to connect to the server. Check that it is running and try again."
            ) from exc

    def health(self) -> dict[str, Any]:
        response = self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    # Property Listings
    def get_property_listings(
        self, token: str | None = None, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return self.get("/api/v1/property-listings", token=token, params=params)

    def sync_property_listings(self, token: str | None = None) -> dict[str, Any]:
        return self.post("/api/v1/property-listings/sync", token=token)

    def update_property_listing(self, listing_id: int, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        return self.put(f"/api/v1/property-listings/{listing_id}", payload, token=token)

    def delete_property_listing(self, listing_id: int, token: str | None = None) -> None:
        self.delete(f"/api/v1/property-listings/{listing_id}", token=token)

    def get_property_status_summary(self, token: str | None = None) -> dict[str, int]:
        return self.get("/api/v1/property-listings/status-summary", token=token)

    # Agents
    def get_agents(self, token: str | None = None) -> list[dict[str, Any]]:
        return self.get("/api/v1/agents", token=token)

    def get_agent_count(self, token: str | None = None) -> int:
        data = self.get("/api/v1/agents/count", token=token)
        return int(data.get("total", 0))

    def get_agent(self, agent_id: str, token: str | None = None) -> dict[str, Any]:
        return self.get(
            f"/api/v1/agents/{quote(agent_id, safe='')}",
            token=token,
        )

    def sync_agents(self, token: str | None = None) -> dict[str, Any]:
        return self.post("/api/v1/agents/sync", token=token)

    # Clients
    def get_clients(self, token: str | None = None) -> list[dict[str, Any]]:
        return self.get("/api/v1/clients", token=token)

    def get_client(self, client_id: str, token: str | None = None) -> dict[str, Any]:
        return self.get(
            f"/api/v1/clients/{quote(client_id, safe='')}",
            token=token,
        )

    def delete_client(self, client_id: str, token: str | None = None) -> None:
        self.delete(f"/api/v1/clients/{quote(client_id, safe='')}", token=token)

    def get_client_count(self, token: str | None = None) -> int:
        data = self.get("/api/v1/clients/count", token=token)
        return int(data.get("total", 0))

    def get_client_summary(self, token: str | None = None) -> dict[str, int]:
        return self.get("/api/v1/clients/summary", token=token)

    def sync_clients(self, token: str | None = None) -> dict[str, Any]:
        return self.post("/api/v1/clients/sync", token=token)

    # Transactions
    def get_transactions(self, token: str | None = None) -> list[dict[str, Any]]:
        return self.get("/api/v1/transactions", token=token)

    def get_transaction(
        self, transaction_id: str, token: str | None = None
    ) -> dict[str, Any]:
        return self.get(
            f"/api/v1/transactions/{quote(transaction_id, safe='')}",
            token=token,
        )

    def get_transaction_summary(self, token: str | None = None) -> dict[str, Any]:
        return self.get("/api/v1/transactions/summary", token=token)

    def sync_transactions(self, token: str | None = None) -> dict[str, Any]:
        return self.post("/api/v1/transactions/sync", token=token)

    # Dashboard
    def get_dashboard_summary(self, token: str | None = None) -> dict[str, Any]:
        return self.get("/api/v1/dashboard/summary", token=token)

    def get_dashboard_property_status(self, token: str | None = None) -> dict[str, int]:
        return self.get("/api/v1/dashboard/property-status", token=token)

    def get_dashboard_transaction_trend(self, token: str | None = None) -> dict[str, Any]:
        return self.get("/api/v1/dashboard/transaction-trend", token=token)

    def get_dashboard_recent_transactions(
        self, token: str | None = None
    ) -> list[dict[str, Any]]:
        return self.get("/api/v1/dashboard/recent-transactions", token=token)

    def get_dashboard_agent_performance(
        self, token: str | None = None
    ) -> list[dict[str, Any]]:
        return self.get("/api/v1/dashboard/agent-performance", token=token)

    def get_dashboard_forecast(self, token: str | None = None) -> dict[str, Any]:
        return self.get("/api/v1/dashboard/forecast", token=token)
