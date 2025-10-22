from __future__ import annotations

import re

import allure
import pytest
from playwright.sync_api import expect

from src.utils.api_client import ApiClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


@pytest.mark.smoke
@pytest.mark.api
def test_smoke_articles_index(api_client: ApiClient) -> None:
    response = api_client.list_articles(limit=1)
    assert response["articles"], "Expected at least one article in smoke test"
    logger.info("Smoke API returned %d articles", len(response["articles"]))


@pytest.mark.smoke
@pytest.mark.ui
@pytest.mark.usefixtures("frontend_ready")
def test_smoke_homepage(page, settings) -> None:  # type: ignore[assignment]
    """Quick sanity check that the homepage renders."""
    with allure.step("open homepage"):
        page.goto(settings.frontend_url, wait_until="domcontentloaded")
        nav_logo = page.get_by_role("navigation").get_by_role("link", name="conduit")
        expect(nav_logo).to_be_visible()
        expect(page).to_have_title(re.compile("Conduit", re.IGNORECASE))
        logger.info("Homepage smoke check rendered successfully")
