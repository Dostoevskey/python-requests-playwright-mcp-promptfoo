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
        return UserContext(username=data["username"], email=data["email"], token=data["token"], password=password)
    if resp.status_code == 422:
        # user exists; fall back to login
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


def ensure_profile(session: requests.Session, base_url: str, author: UserContext, bio: str | None = None) -> None:
    profile_payload = {"user": {}}
    if bio:
        profile_payload["user"]["bio"] = bio
    if not profile_payload["user"]:
        return
    resp = session.put(
        f"{base_url}/user",
        headers={"Authorization": f"Token {author.token}"},
        json=profile_payload,
        timeout=15,
    )
    if resp.status_code not in (200, 201):
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default="config/demo.env", help="Path to .env file")
    parser.add_argument("--seed", default="config/seed_data.yaml", help="YAML file with seed data")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not Path(args.env_file).exists():
        print(f"Environment file not found: {args.env_file}", file=sys.stderr)
        return 1
    if not Path(args.seed).exists():
        print(f"Seed data file not found: {args.seed}", file=sys.stderr)
        return 1

    load_dotenv(args.env_file, override=True)
    api_base_url = os.environ.get("API_BASE_URL")
    if not api_base_url:
        print("API_BASE_URL not configured in environment", file=sys.stderr)
        return 1

    default_password = os.environ.get("DEFAULT_PASSWORD", "Password123!")

    with open(args.seed, "r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh)

    users_data = payload.get("users", [])
    articles_data = payload.get("articles", [])
    if len(users_data) < 1:
        print("No users defined in seed data", file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})

    authors: dict[str, UserContext] = {}
    for user in users_data:
        context = register_user(session, api_base_url, user, default_password)
        ensure_profile(session, api_base_url, context, user.get("bio"))
        authors[context.username] = context
        print(f"User ready: {context.username} <{context.email}>")

    default_tags = ["demo", "automation", "seeded"]
    for article in articles_data:
        author_username = article.get("author")
        if author_username not in authors:
            raise RuntimeError(f"Author {author_username} not found among seeded users")
        ensure_article(session, api_base_url, article, authors[author_username], default_tags)
        print(f"Article ready: {article['title']} (author: {author_username})")

    summary = {
        "users": list(authors.keys()),
        "articles": [article["title"] for article in articles_data],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
