from __future__ import annotations

from typing import Dict, Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page


@pytest.fixture(scope="session")
def multi_context(browser: Browser) -> Generator[Dict[str, BrowserContext], None, None]:
    contexts: Dict[str, BrowserContext] = {}
    try:
        contexts["desktop"] = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir="playwright-report",
        )
        contexts["desktop"].add_init_script("window.localStorage.clear(); window.sessionStorage.clear();")
        contexts["mobile"] = browser.new_context(
            viewport={"width": 414, "height": 896},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
            device_scale_factor=3,
            is_mobile=True,
            record_video_dir="playwright-report",
        )
        contexts["mobile"].add_init_script("window.localStorage.clear(); window.sessionStorage.clear();")
        yield contexts
    finally:
        for context in contexts.values():
            context.close()


@pytest.fixture
def author_reader_pages(multi_context: Dict[str, BrowserContext]) -> Generator[Dict[str, Page], None, None]:
    for context in multi_context.values():
        context.clear_cookies()
    pages = {name: context.new_page() for name, context in multi_context.items()}
    try:
        yield pages
    finally:
        for page in pages.values():
            page.close()
