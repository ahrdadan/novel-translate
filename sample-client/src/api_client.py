from typing import Any

import httpx


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.api_v1 = f"{self.base_url}/api/v1"
        self.client = httpx.Client(timeout=60.0)

    def check_server(self) -> bool:
        try:
            res = self.client.get(f"{self.base_url}/")
            return res.status_code == 200
        except httpx.RequestError:
            return False

    def fetch_platforms(self) -> list[dict[str, Any]]:
        try:
            res = self.client.get(f"{self.api_v1}/platforms")
            if res.status_code == 200:
                return res.json()
        except httpx.RequestError:
            return []
        return []

    def fetch_models(self) -> list[dict[str, Any]]:
        try:
            res = self.client.get(f"{self.api_v1}/models")
            if res.status_code == 200:
                return res.json()
        except httpx.RequestError:
            return []
        return []

    def fetch_series(self) -> list[dict[str, Any]]:
        try:
            res = self.client.get(f"{self.api_v1}/series")
            if res.status_code == 200:
                return res.json()
        except httpx.RequestError:
            return []
        return []

    def fetch_jobs(self, series_id: int | None = None, status: str | None = None) -> list[dict[str, Any]]:
        try:
            url = f"{self.api_v1}/jobs"
            params = []
            if series_id:
                params.append(f"series_id={series_id}")
            if status:
                params.append(f"status={status}")
            if params:
                url += "?" + "&".join(params)
            res = self.client.get(url)
            if res.status_code == 200:
                return res.json()
        except httpx.RequestError:
            return []
        return []

    def fetch_chapters(self, series_id: int) -> list[dict[str, Any]]:
        try:
            res = self.client.get(f"{self.api_v1}/series/{series_id}/chapters")
            if res.status_code == 200:
                return res.json()
        except httpx.RequestError:
            return []
        return []

    def fetch_chapter_detail(self, series_id: int, chapter_number: float) -> dict[str, Any] | None:
        try:
            res = self.client.get(f"{self.api_v1}/series/{series_id}/chapters/{chapter_number}")
            if res.status_code == 200:
                return res.json()
        except httpx.RequestError:
            return None
        return None

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.client.post(url, **kwargs)
        
    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.client.get(url, **kwargs)

    def patch(self, url: str, **kwargs) -> httpx.Response:
        return self.client.patch(url, **kwargs)
