from __future__ import annotations

import uuid
from typing import Dict

import allure
import pytest
from playwright.sync_api import Page, expect

from src.utils.api_client import ApiClient, UserCredentials


@pytest.mark.ui
def test_ui_author_can_create_article(
    author_reader_pages: Dict[str, Page],
    settings,
    api_client: ApiClient,
) -> None:
    page = author_reader_pages["desktop"]
    creds: UserCredentials = api_client.generate_credentials(prefix="ui_author")
    api_client.register_user(creds)

    title = f"Playwright UI Article {uuid.uuid4().hex[:6]}"
    body = "This article was created via Playwright UI automation."

    with allure.step("open sign in page"):
        page.goto(settings.frontend_url)
        page.get_by_role("link", name="Sign in").click()

    with allure.step("fill credentials and submit"):
        page.get_by_placeholder("Email").fill(creds.email)
        page.get_by_placeholder("Password").fill(creds.password)
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_role("link", name="New Article")).to_be_visible()

    with allure.step("compose a new article"):
        page.get_by_role("link", name="New Article").click()
        page.get_by_placeholder("Article Title").fill(title)
        page.get_by_placeholder("What's this article about?").fill("End-to-end authoring")
        page.get_by_placeholder("Write your article (in markdown)").fill(body)
        page.get_by_role("button", name="Publish Article").click()

    with allure.step("verify article view"):
        expect(page.get_by_role("heading", name=title)).to_be_visible()
        slug = page.url.rstrip("/").split("/")[-1]

    with allure.step("cleanup via API"):
        api_client.delete_article(creds, slug)


@pytest.mark.ui
def test_ui_feed_pagination(author_reader_pages: Dict[str, Page], settings) -> None:
    mobile_page = author_reader_pages["mobile"]

    with allure.step("visit home page on mobile viewport"):
        mobile_page.goto(settings.frontend_url)
        expect(mobile_page.get_by_role("link", name="Global Feed")).to_be_visible()

    with allure.step("navigate to second page of articles"):
        pagination = mobile_page.locator(".pagination")
        expect(pagination).to_be_visible()
        second_page = pagination.locator("li.page-item").nth(2)
        second_page.click()
        expect(pagination.locator("li.page-item.active")).to_have_count(1)


@pytest.mark.ui
def test_ui_route_requires_auth(author_reader_pages: Dict[str, Page], settings) -> None:
    anonymous_page = author_reader_pages["desktop"]
    with allure.step("directly navigate to editor while logged out"):
        anonymous_page.goto(f"{settings.frontend_url}/editor")
        expect(anonymous_page).to_have_url(f"{settings.frontend_url}/login")
