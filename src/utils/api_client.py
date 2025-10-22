"""Lightweight wrapper around the RealWorld API for test readability."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.data.factory import ArticleRecipe, factory
from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_TIMEOUT = 10  # seconds

@dataclass
class UserCredentials:
    username: str
    email: str
    password: str
    token: str | None = None


class ApiError(RuntimeError):
    """Raised when the API returns an unexpected status code."""

    def __init__(self, message: str, status: Optional[int] = None, body: Optional[str] = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class ApiClient:
    def __init__(self, base_url: str, session: requests.Session | None = None, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        # Configure retries for transient server/network errors
        retries = Retry(total=3, backoff_factor=0.3, status_forcelist=(429, 500, 502, 503, 504), raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        # Default headers
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    def _raise_for_status(self, response: requests.Response, expected: tuple[int, ...]) -> dict[str, Any]:
        if response.status_code not in expected:
            logger.error(
                "Unexpected status %s for %s %s",
                response.status_code,
                response.request.method,
                response.request.url,
            )
            raise ApiError(f"Unexpected status {response.status_code}: {response.text}", status=response.status_code, body=response.text)
        if response.text:
            return response.json()
        return {}

    def generate_credentials(self, prefix: str = "testuser") -> UserCredentials:
        recipe = factory.user(prefix)
        logger.debug("Generated credentials for prefix %s -> %s", prefix, recipe.username)
        return UserCredentials(**recipe.model_dump())

    # User endpoints -----------------------------------------------------

    def register_user(self, creds: UserCredentials) -> UserCredentials:
        payload = {"user": {"username": creds.username, "email": creds.email, "password": creds.password}}
        logger.info("Registering user %s", creds.username)
        response = self.session.post(f"{self.base_url}/users", json=payload, timeout=self.timeout)
        data = self._raise_for_status(response, expected=(200, 201))
        creds.token = data["user"].get("token")
        logger.debug("Registration complete for %s", creds.username)
        return creds

    def login_user(self, creds: UserCredentials) -> UserCredentials:
        payload = {"user": {"email": creds.email, "password": creds.password}}
        logger.info("Logging in user %s", creds.username)
        response = self.session.post(f"{self.base_url}/users/login", json=payload, timeout=self.timeout)
        data = self._raise_for_status(response, expected=(200,))
        creds.token = data["user"].get("token")
        logger.debug("Login complete for %s", creds.username)
        return creds

    def update_profile(
        self,
        creds: UserCredentials,
        bio: str | None = None,
        image: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Token {creds.token}"} if creds.token else {}
        payload = {"user": {}}
        if bio:
            payload["user"]["bio"] = bio
        if image:
            payload["user"]["image"] = image
        if password:
            payload["user"]["password"] = password
        logger.debug("Updating profile for %s", creds.username)
        response = self.session.put(f"{self.base_url}/user", headers=headers, json=payload, timeout=self.timeout)
        return self._raise_for_status(response, expected=(200,))

    # Article endpoints --------------------------------------------------

    def create_article(
        self,
        creds: UserCredentials,
        title: str,
        description: str,
        body: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Token {creds.token}"} if creds.token else {}
        payload = {
            "article": {
                "title": title,
                "description": description,
                "body": body,
                "tagList": tags or [],
            }
        }
        logger.info("Creating article '%s' for %s", title, creds.username)
        response = self.session.post(f"{self.base_url}/articles", headers=headers, json=payload, timeout=self.timeout)
        return self._raise_for_status(response, expected=(200, 201))

    def get_article(self, slug: str) -> dict[str, Any]:
        logger.debug("Fetching article %s", slug)
        response = self.session.get(f"{self.base_url}/articles/{slug}", timeout=self.timeout)
        return self._raise_for_status(response, expected=(200,))

    def create_article_from_recipe(self, creds: UserCredentials, recipe: ArticleRecipe) -> dict[str, Any]:
        return self.create_article(
            creds=creds,
            title=recipe.title,
            description=recipe.description,
            body=recipe.body,
            tags=recipe.tags,
        )

    def list_articles(self, limit: int = 5, offset: int = 0) -> dict[str, Any]:
        params = {"limit": limit, "offset": offset}
        logger.debug("Listing articles limit=%s offset=%s", limit, offset)
        response = self.session.get(f"{self.base_url}/articles", params=params, timeout=self.timeout)
        return self._raise_for_status(response, expected=(200,))

    def update_article(
        self,
        creds: UserCredentials,
        slug: str,
        title: str | None = None,
        body: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Token {creds.token}"} if creds.token else {}
        payload: dict[str, Any] = {"article": {}}
        if title:
            payload["article"]["title"] = title
        if body:
            payload["article"]["body"] = body
        logger.info("Updating article %s for %s", slug, creds.username)
        response = self.session.put(f"{self.base_url}/articles/{slug}", headers=headers, json=payload, timeout=self.timeout)
        return self._raise_for_status(response, expected=(200,))

    def delete_article(self, creds: UserCredentials, slug: str) -> None:
        headers = {"Authorization": f"Token {creds.token}"}
        logger.info("Deleting article %s for %s", slug, creds.username)
        response = self.session.delete(f"{self.base_url}/articles/{slug}", headers=headers, timeout=self.timeout)
        self._raise_for_status(response, expected=(200, 204))


__all__ = ["ApiClient", "ApiError", "UserCredentials"]