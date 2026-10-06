from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx


DEFAULT_API_URL = os.environ.get("ALTY_API_URL", "http://localhost:8000")


def error_message(error: Exception) -> str:
    """Human-readable text for an API/network error (shows backend detail)."""
    if isinstance(error, httpx.HTTPStatusError):
        try:
            detail = error.response.json().get("detail")
        except ValueError:
            detail = None
        if isinstance(detail, dict):
            parts = [str(detail.get("message") or "Request failed")]
            if detail.get("stage"):
                parts.append(f"Stage: {detail['stage']}")
            if detail.get("reason"):
                parts.append(f"Reason: {detail['reason']}")
            return "\n".join(parts)
        if isinstance(detail, list):
            return "; ".join(str(item.get("msg", item)) for item in detail if item) or "Invalid request"
        return str(detail or f"Request failed (HTTP {error.response.status_code}).")
    if isinstance(error, httpx.RequestError):
        return "Unable to connect to the server. Check that it is running and try again."
    return str(error) or "The operation could not be completed."


class ApiClient:
    def __init__(self, base_url: str | None = None) -> None:
        if base_url is None and "ALTY_API_URL" not in os.environ:
            try:  # URL saved on the Settings page
                from PyQt6.QtCore import QSettings

                base_url = QSettings("Alty", "Desktop").value("api_url") or None
            except Exception:
                base_url = None
        self.base_url = (base_url or DEFAULT_API_URL).rstrip("/")
        # Requests run off the GUI thread so the window keeps painting its
        # loading indicators (see app.busy).
        from app.busy import ResponsiveHttpClient

        self.client = ResponsiveHttpClient(httpx.Client(timeout=30.0))

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

    def archive_document(self, document_id: str, token: str | None = None) -> dict[str, Any]:
        return self._document_action(document_id, "archive", token)

    def restore_document(self, document_id: str, token: str | None = None) -> dict[str, Any]:
        return self._document_action(document_id, "restore", token)

    def reprocess_document(self, document_id: str, token: str | None = None,
                           document_type: str | None = None) -> dict[str, Any]:
        payload = {"document_type": document_type} if document_type else None
        return self.post(f"/api/v1/documents/{quote(document_id, safe='')}/reprocess", payload, token=token)

    def get_document_types(self, token: str | None = None) -> list[dict[str, Any]]:
        return self.get("/api/v1/documents/types", token=token)

    def get_document_audit(self, document_id: str, token: str | None = None) -> list[dict[str, Any]]:
        return self.get(f"/api/v1/documents/{quote(document_id, safe='')}/audit", token=token)

    def get_notifications(self, token: str | None = None) -> dict[str, Any]:
        return self.get("/api/v1/notifications", token=token)

    def mark_notifications_read(self, keys: list[str], token: str | None = None) -> dict[str, Any]:
        return self.post("/api/v1/notifications/read", {"keys": keys}, token=token)

    def mark_all_notifications_read(self, token: str | None = None) -> dict[str, Any]:
        return self.post("/api/v1/notifications/read-all", {}, token=token)

    def get_document_summary(self, token: str | None = None) -> dict[str, Any]:
        return self.get("/api/v1/documents/summary", token=token)

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

    def me(self, token: str) -> dict[str, Any]:
        return self.get("/api/v1/auth/me", token=token)

    def logout(self, token: str) -> None:
        try:
            response = self.client.post(
                f"{self.base_url}/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
        except httpx.HTTPError:
            pass  # the token is discarded locally either way

    def health(self) -> dict[str, Any]:
        response = self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    # Property Listings
    def get_property_listings(
        self, token: str | None = None, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return self.get("/api/v1/property-listings", token=token, params=params)

    def get_property_listing(self, listing_id: int, token: str | None = None) -> dict[str, Any]:
        return self.get(f"/api/v1/property-listings/{listing_id}", token=token)

    def get_property_history(self, listing_id: int, token: str | None = None) -> dict[str, Any]:
        return self.get(f"/api/v1/property-listings/{listing_id}/history", token=token)

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

    def get_agent_activity(self, agent_id: str, token: str | None = None) -> dict[str, Any]:
        return self.get(f"/api/v1/agents/{quote(agent_id, safe='')}/activity", token=token)

    def get_partners(self, token: str | None = None) -> list[dict[str, Any]]:
        return self.get("/api/v1/partners", token=token)

    def get_agent_reviews(self, agent_id: str, token: str | None = None, limit: int = 20) -> dict[str, Any]:
        """Client rating summary, star distribution and recent reviews."""
        return self.get(f"/api/v1/agents/{quote(agent_id, safe='')}/reviews", token=token, params={"limit": limit})

    # Clients
    def get_clients(self, token: str | None = None) -> list[dict[str, Any]]:
        return self.get("/api/v1/clients", token=token)

    def get_client(self, client_id: str, token: str | None = None) -> dict[str, Any]:
        return self.get(
            f"/api/v1/clients/{quote(client_id, safe='')}",
            token=token,
        )

    def get_client_profile(self, client_id: str, token: str | None = None) -> dict[str, Any]:
        return self.get(f"/api/v1/clients/{quote(client_id, safe='')}/profile", token=token)

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
    def get_transactions(self, token: str | None = None,
                         params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self.get("/api/v1/transactions", token=token, params=params)

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

    def get_dashboard_revenue_trend(self, token: str | None = None) -> dict[str, Any]:
        return self.get("/api/v1/dashboard/revenue-trend", token=token)

    # Analytics / forecasting / decision support / workforce
    def get_analytics_overview(self, token: str | None = None) -> dict[str, Any]:
        return self.get("/api/v1/analytics/overview", token=token)

    def get_forecast(self, token: str | None = None, metric: str = "revenue") -> dict[str, Any]:
        return self.get("/api/v1/analytics/forecast", token=token, params={"metric": metric})

    def get_dss(self, token: str | None = None) -> dict[str, Any]:
        return self.get("/api/v1/analytics/dss", token=token)

    def get_workforce(self, token: str | None = None) -> dict[str, Any]:
        return self.get("/api/v1/analytics/workforce", token=token)

    # Users
    def get_users(self, token: str | None = None) -> list[dict[str, Any]]:
        return self.get("/api/v1/users", token=token)

    def get_roles(self, token: str | None = None) -> list[dict[str, Any]]:
        return self.get("/api/v1/users/roles", token=token)

    def create_user(self, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        return self.post("/api/v1/users", payload, token=token)

    def update_user(self, user_id: int, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        return self.put(f"/api/v1/users/{user_id}", payload, token=token)

    def reset_user_password(self, user_id: int, password: str, token: str | None = None) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = self.client.post(f"{self.base_url}/api/v1/users/{user_id}/reset-password",
                                    json={"password": password}, headers=headers)
        response.raise_for_status()

    # Audit
    def get_audit_events(self, token: str | None = None,
                         params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.get("/api/v1/audit", token=token, params=params)

    def get_audit_actions(self, token: str | None = None) -> list[str]:
        return self.get("/api/v1/audit/actions", token=token)

    # System settings / synchronization
    def get_system_settings(self, token: str | None = None) -> dict[str, Any]:
        return self.get("/api/v1/system/settings", token=token)

    def get_sync_status(self, token: str | None = None) -> dict[str, Any]:
        return self.get("/api/v1/system/sync", token=token)

    def push_sync(self, token: str | None = None) -> dict[str, Any]:
        return self.post("/api/v1/system/sync/push", token=token)

    # Media (digital property preview)
    def get_media(self, token: str | None = None, listing_id: int | None = None) -> list[dict[str, Any]]:
        params = {"listing_id": listing_id} if listing_id is not None else None
        return self.get("/api/v1/media", token=token, params=params)

    def get_media_summary(self, token: str | None = None) -> dict[str, Any]:
        return self.get("/api/v1/media/summary", token=token)

    def upload_media(self, listing_id: int, file_path: str, token: str | None = None) -> dict[str, Any]:
        return self._upload_file(f"/api/v1/media/properties/{listing_id}", file_path, {}, token)

    def get_media_file(self, media_id: int, token: str | None = None) -> bytes:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = self.client.get(f"{self.base_url}/api/v1/media/{media_id}/file", headers=headers)
        response.raise_for_status()
        return response.content

    def delete_media(self, media_id: int, token: str | None = None) -> None:
        self.delete(f"/api/v1/media/{media_id}", token=token)

    # Global search
    def search(self, query: str, token: str | None = None, limit: int = 8) -> dict[str, Any]:
        return self.get("/api/v1/search", token=token, params={"q": query, "limit": limit})
