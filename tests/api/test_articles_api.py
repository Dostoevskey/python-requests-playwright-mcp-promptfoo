from __future__ import annotations

import allure
import pytest

from src.data.factory import factory
from src.utils.api_client import ApiClient, ApiError
from src.utils.logger import get_logger

logger = get_logger(__name__)


@pytest.mark.api
@pytest.mark.parametrize("prefix", ["api_article"])
def test_article_crud_flow(api_client: ApiClient, prefix: str) -> None:
    creds = api_client.generate_credentials(prefix=prefix)
    api_client.register_user(creds)

    logger.info("Generated user %s for CRUD flow", creds.username)

    article_recipe = factory.article(creds, title_seed="Automation CRUD article")
    logger.debug("Article recipe: %s", article_recipe.model_dump())

    with allure.step("create article"):
        created = api_client.create_article_from_recipe(creds, article_recipe)["article"]
        slug = created["slug"]
        assert created["title"] == article_recipe.title
        logger.info("Article created with slug %s", slug)

    with allure.step("update article title and content"):
        updated_title = f"{article_recipe.title} - updated"
        updated = api_client.update_article(
            creds,
            slug=slug,
            title=updated_title,
            body="Updated body text",
        )["article"]
        assert updated["title"] == updated_title
        slug = updated["slug"]
        logger.info("Article updated; new slug %s", slug)

    with allure.step("verify ownership before delete"):
        fetched = api_client.get_article(slug)["article"]
        assert fetched["author"]["username"] == creds.username
        logger.debug("Ownership verified for slug %s", slug)

    with allure.step("delete article"):
        api_client.delete_article(creds, slug)
        with pytest.raises(ApiError):
            api_client.get_article(slug)
        logger.info("Article %s deleted", slug)
