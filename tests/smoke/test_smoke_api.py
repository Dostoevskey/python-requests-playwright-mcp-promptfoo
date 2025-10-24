from __future__ import annotations

import pytest


@pytest.mark.api
@pytest.mark.smoke
def test_smoke_can_register_user(api_client) -> None:
    creds = api_client.generate_credentials(prefix="smoke_user")
    registered = api_client.register_user(creds)
    assert registered.token, "Registration should return auth token"


@pytest.mark.api
@pytest.mark.smoke
def test_smoke_can_login_user(api_client) -> None:
    creds = api_client.generate_credentials(prefix="smoke_login")
    api_client.register_user(creds)
    logged_in = api_client.login_user(creds)
    assert logged_in.token, "Login should succeed for freshly registered user"


@pytest.mark.api
@pytest.mark.smoke
def test_smoke_can_create_article(api_client) -> None:
    creds = api_client.generate_credentials(prefix="smoke_article")
    api_client.register_user(creds)

    created = api_client.create_article(
        creds,
        title=api_client.unique_title("Smoke Article"),
        description="Smoke test description",
        body="This is a smoke test article body.",
        tags=["smoke"],
    )["article"]

    assert created["slug"], "Article creation should return slug"
    assert created["title"].startswith("Smoke Article"), "Article title should match request"
