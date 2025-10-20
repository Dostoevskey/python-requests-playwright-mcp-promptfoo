from __future__ import annotations

import allure
import pytest

from src.utils.api_client import ApiClient, ApiError


@pytest.mark.api
@pytest.mark.parametrize("prefix", ["api_article"])
def test_article_crud_flow(api_client: ApiClient, prefix: str) -> None:
    creds = api_client.generate_credentials(prefix=prefix)
    api_client.register_user(creds)

    base_title = f"Automation CRUD article {creds.username}"

    with allure.step("create article"):
        created = api_client.create_article(
            creds,
            title=base_title,
            description="Created during API test",
            body="Initial body",
            tags=["automation", "pytest"],
        )["article"]
        slug = created["slug"]
        assert created["title"] == base_title

    with allure.step("update article title and content"):
        updated_title = f"{base_title} - updated"
        updated = api_client.update_article(
            creds,
            slug=slug,
            title=updated_title,
            body="Updated body text",
        )["article"]
        assert updated["title"] == updated_title
        slug = updated["slug"]

    with allure.step("verify ownership before delete"):
        fetched = api_client.get_article(slug)["article"]
        assert fetched["author"]["username"] == creds.username

    with allure.step("delete article"):
        api_client.delete_article(creds, slug)
        with pytest.raises(ApiError):
            api_client.get_article(slug)
