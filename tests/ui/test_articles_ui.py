from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

import allure
import pytest
from playwright.sync_api import Page, expect

from src.data.factory import factory
from src.utils.api_client import ApiClient, UserCredentials
from src.utils.logger import get_logger

SNAPSHOT_DIR = Path("tests/ui/__snapshots__")
logger = get_logger(__name__)


def assert_snapshot(page: Page, name: str, **options) -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    baseline = SNAPSHOT_DIR / name
    current = SNAPSHOT_DIR / f"{Path(name).stem}.current.png"
    if os.environ.get("PLAYWRIGHT_HEADLESS", "1").lower() in {"0", "false", "no"}:
        preview = SNAPSHOT_DIR / f"{Path(name).stem}.headed.png"
        page.screenshot(path=preview, **options)
        allure.attach.file(
            str(preview),
            name=f"snapshot-headed-{name}",
            attachment_type=allure.attachment_type.PNG,
        )
        preview.unlink(missing_ok=True)
        return
    page.screenshot(path=current, **options)
    logger.debug("Captured screenshot for %s", name)
    allure.attach.file(
        str(current),
        name=f"snapshot-current-{name}",
        attachment_type=allure.attachment_type.PNG,
    )
    if not baseline.exists():
        baseline.write_bytes(current.read_bytes())
        allure.attach.file(
            str(baseline),
            name=f"snapshot-baseline-{name}",
            attachment_type=allure.attachment_type.PNG,
        )
        current.unlink(missing_ok=True)
        logger.info("Stored new baseline screenshot %s", baseline)
        return
    if baseline.read_bytes() != current.read_bytes():
        allure.attach.file(
            str(baseline),
            name=f"snapshot-baseline-{name}",
            attachment_type=allure.attachment_type.PNG,
        )
        logger.error("Visual regression detected for %s", name)
        raise AssertionError(f"Visual regression detected for {name}")
    current.unlink(missing_ok=True)


@pytest.mark.ui
def test_ui_author_can_create_article(
    author_reader_pages: Dict[str, Page],
    settings,
    api_client: ApiClient,
) -> None:
    page = author_reader_pages["desktop"]
    creds: UserCredentials = api_client.generate_credentials(prefix="ui_author")
    api_client.register_user(creds)
    logger.info("UI author %s registered", creds.username)

    recipe = factory.article(creds, title_seed="Playwright UI Article")
    logger.debug("UI article recipe: %s", recipe.model_dump())

    with allure.step("open sign in page"):
        page.goto(settings.frontend_url)
        page.wait_for_load_state("networkidle")
        page.wait_for_selector('a:has-text("Login")', timeout=10000)
        page.locator('a:has-text("Login")').click()
        logger.info("Navigated to login page for UI author flow")

    with allure.step("fill credentials and submit"):
        page.get_by_placeholder("Email").fill(creds.email)
        page.get_by_placeholder("Password").fill(creds.password)
        page.get_by_role("button", name="Login").click()
        expect(page.get_by_role("link", name="New Article")).to_be_visible(timeout=10000)
        logger.info("Login successful for %s", creds.username)

    with allure.step("compose a new article"):
        page.get_by_role("link", name="New Article").click()
        page.get_by_placeholder("Article Title").fill(recipe.title)
        page.get_by_placeholder("What's this article about?").fill(recipe.description)
        page.get_by_placeholder("Write your article (in markdown)").fill(recipe.body)
        page.get_by_role("button", name="Publish Article").click()
        logger.info("Article published via UI for %s", creds.username)

    with allure.step("verify article view"):
        expect(page.get_by_role("heading", name=recipe.title)).to_be_visible()
        slug = page.url.rstrip("/").split("/")[-1]
        logger.debug("Article visible at slug %s", slug)

    with allure.step("cleanup via API"):
        api_client.delete_article(creds, slug)
        logger.info("Cleaned up article %s", slug)


@pytest.mark.ui
def test_ui_feed_pagination(author_reader_pages: Dict[str, Page], settings) -> None:
    mobile_page = author_reader_pages["mobile"]

    with allure.step("visit home page on mobile viewport"):
        mobile_page.goto(settings.frontend_url)
        mobile_page.wait_for_load_state("networkidle")
        expect(mobile_page.locator('a[href="#/"]:has-text("Home")')).to_be_visible(timeout=10000)
        expect(mobile_page.locator('text=Global Feed')).to_be_visible(timeout=10000)
        logger.info("Global feed visible on mobile viewport")

    with allure.step("navigate to second page of articles"):
        pagination = mobile_page.locator(".pagination")
        expect(pagination).to_be_visible(timeout=10000)
        second_page = pagination.locator("li.page-item").nth(2)
        second_page.click()
        expect(pagination.locator("li.page-item.active")).to_have_count(1)
        logger.debug("Pagination advanced to second page")

    with allure.step("capture hero snapshot"):
        assert_snapshot(
            mobile_page,
            "home-feed.png",
            animations="disabled",
            caret="hide",
            mask=[mobile_page.locator(".article-actions")],
            full_page=True,
        )
        logger.info("Homepage snapshot captured for regression coverage")


@pytest.mark.ui
def test_ui_route_requires_auth(author_reader_pages: Dict[str, Page], settings) -> None:
    anonymous_page = author_reader_pages["desktop"]
    with allure.step("directly navigate to editor while logged out"):
        anonymous_page.goto(f"{settings.frontend_url}editor")
        anonymous_page.wait_for_load_state("networkidle")
        expect(anonymous_page).to_have_url(settings.frontend_url, timeout=10000)
        expect(anonymous_page.locator('a:has-text("Login")')).to_be_visible(timeout=10000)
        logger.info("Unauthenticated redirect verified for editor route")
