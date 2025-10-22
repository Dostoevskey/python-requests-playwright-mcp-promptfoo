"""Deterministic data builders for tests."""
from __future__ import annotations

import secrets
from dataclasses import dataclass

from pydantic import BaseModel, EmailStr


class UserRecipe(BaseModel):
    username: str
    email: EmailStr
    password: str


class ArticleRecipe(BaseModel):
    title: str
    description: str
    body: str
    tags: list[str]


@dataclass
class DataFactory:
    prefix: str = "demo"

    def _token(self) -> str:
        return secrets.token_hex(3)

    def user(self, prefix: str | None = None) -> UserRecipe:
        token = self._token()
        base = prefix or self.prefix
        username = f"{base}_{token}"
        email = f"{username}@example.com"
        password = f"Pass!{token}"
        return UserRecipe(username=username, email=email, password=password)

    def article(self, owner: UserRecipe, title_seed: str = "Automation article") -> ArticleRecipe:
        token = self._token()
        title = f"{title_seed} {token}"
        return ArticleRecipe(
            title=title,
            description=f"Generated for {owner.username}",
            body="This article was created during automated tests to validate CRUD flows.",
            tags=["automation", "pytest"],
        )


factory = DataFactory()

__all__ = ["DataFactory", "ArticleRecipe", "UserRecipe", "factory"]
