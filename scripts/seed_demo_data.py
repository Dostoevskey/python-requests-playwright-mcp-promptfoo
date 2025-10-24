#!/usr/bin/env python3
"""Seed the Conduit RealWorld backend with deterministic demo data."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class UserContext:
    username: str
    email: str
    token: str
    password: str


def slugify(title: str) -> str:
    import re

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "article"


def register_user(session: requests.Session, base_url: str, user: dict[str, Any], password: str) -> UserContext:
    payload = {"user": {"username": user["username"], "email": user["email"], "password": password}}
    resp = session.post(f"{base_url}/users", json=payload, timeout=15)
    if resp.status_code in (200, 201):
        data = resp.json()["user"]
        logger.debug("Registered user %s", data["username"])
        return UserContext(username=data["username"], email=data["email"], token=data["token"], password=password)
    if resp.status_code == 422:
        # user exists; fall back to login
        logger.debug("User %s already exists; logging in", user["username"])
        return login_user(session, base_url, user, password)
    raise RuntimeError(f"Failed to create user {user['username']}: {resp.status_code} {resp.text}")


def login_user(session: requests.Session, base_url: str, user: dict[str, Any], password: str) -> UserContext:
    payload = {"user": {"email": user["email"], "password": password}}
    resp = session.post(f"{base_url}/users/login", json=payload, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Failed to login user {user['username']} ({user['email']}): {resp.status_code} {resp.text}"
        )
    data = resp.json()["user"]
    return UserContext(username=data["username"], email=data["email"], token=data["token"], password=password)


def ensure_profile(
    session: requests.Session,
    base_url: str,
    author: UserContext,
    bio: str | None = None,
    password: str | None = None,
) -> None:
    profile_payload = {"user": {}}
    if bio:
        profile_payload["user"]["bio"] = bio
    if password:
        profile_payload["user"]["password"] = password
    if not profile_payload["user"]:
        return
    resp = session.put(
        f"{base_url}/user",
        headers={"Authorization": f"Token {author.token}"},
        json=profile_payload,
        timeout=15,
    )
    if resp.status_code in (200, 201):
        logger.debug("Updated profile for %s", author.username)
        return
    if resp.status_code == 500:
        logger.warning("Profile update warning for %s: %s", author.username, resp.text)
        return
    raise RuntimeError(f"Failed to update profile for {author.username}: {resp.status_code} {resp.text}")


def ensure_article(
    session: requests.Session,
    base_url: str,
    article: dict[str, Any],
    author: UserContext,
    default_tags: list[str] | None = None,
) -> None:
    slug = slugify(article["title"])
    inspect_resp = session.get(f"{base_url}/articles/{slug}", timeout=10, headers={"Authorization": f"Token {author.token}"})
    if inspect_resp.status_code == 200:
        return

    payload = {
        "article": {
            "title": article["title"],
            "description": article.get("description", article["title"][:80]),
            "body": article.get("body", ""),
            "tagList": default_tags or ["demo", "automation"],
        }
    }
    if "tags" in article:
        payload["article"]["tagList"] = article["tags"]

    resp = session.post(
        f"{base_url}/articles",
        headers={"Authorization": f"Token {author.token}"},
        json=payload,
        timeout=20,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to create article {article['title']} for {author.username}: {resp.status_code} {resp.text}"
        )
    logger.debug("Created article '%s' for %s", article["title"], author.username)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default="config/demo.env", help="Path to .env file")
    parser.add_argument("--seed", default="config/seed_data.yaml", help="YAML file with seed data")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not Path(args.env_file).exists():
        logger.error("Environment file not found: %s", args.env_file)
        return 1
    if not Path(args.seed).exists():
        logger.error("Seed data file not found: %s", args.seed)
        return 1

    load_dotenv(args.env_file, override=True)
    api_base_url = os.environ.get("API_BASE_URL")
    if not api_base_url:
        logger.error("API_BASE_URL not configured in environment")
        return 1

    default_password = os.environ.get("DEFAULT_PASSWORD", "Password123!")
    logger.info("Seeding demo data via %s", api_base_url)

    with open(args.seed, "r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh)

    users_data = payload.get("users", [])
    articles_data = payload.get("articles", [])
    if len(users_data) < 1:
        logger.error("No users defined in seed data")
        return 1

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})

    authors: dict[str, UserContext] = {}
    for user in users_data:
        context = register_user(session, api_base_url, user, default_password)
        ensure_profile(session, api_base_url, context, user.get("bio"), context.password)
        authors[context.username] = context
        logger.info("User ready: %s <%s>", context.username, context.email)

    default_tags = ["demo", "automation", "seeded"]
    for article in articles_data:
        author_username = article.get("author")
        if author_username not in authors:
            raise RuntimeError(f"Author {author_username} not found among seeded users")
        ensure_article(session, api_base_url, article, authors[author_username], default_tags)
        logger.info("Article ready: %s (author: %s)", article["title"], author_username)

    summary = {
        "users": list(authors.keys()),
        "articles": [article["title"] for article in articles_data],
    }
    logger.info("Seeding summary: %s", json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
