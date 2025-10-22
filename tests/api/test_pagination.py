from __future__ import annotations

import allure
import pytest

from src.utils.api_client import ApiClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


@pytest.mark.api
def test_articles_pagination(api_client: ApiClient) -> None:
    with allure.step("fetch first page of articles"):
        first_page = api_client.list_articles(limit=5, offset=0)
        assert first_page["articles"], "Expected at least one article on page 1"
        total_count = first_page["articlesCount"]
        assert total_count >= 10, "Seed data should provide at least ten articles"
        logger.info("Fetched first page with %d articles (total=%d)", len(first_page["articles"]), total_count)

    with allure.step("fetch second page of articles"):
        second_page = api_client.list_articles(limit=5, offset=1)
        assert second_page["articles"], "Expected articles on page 2"
        logger.info("Fetched second page with %d articles", len(second_page["articles"]))

    with allure.step("verify pagination returns distinct content"):
        first_titles = {article["slug"] for article in first_page["articles"]}
        second_titles = {article["slug"] for article in second_page["articles"]}
        assert not first_titles.intersection(second_titles), "Pages should not overlap"
        logger.debug("Pagination sets are disjoint: %s vs %s", first_titles, second_titles)
