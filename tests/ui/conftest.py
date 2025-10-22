from __future__ import annotations

import os
from typing import Dict, Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page

from src.utils.logger import get_logger

logger = get_logger(__name__)


@pytest.fixture(scope="session")
def multi_context(browser: Browser) -> Generator[Dict[str, BrowserContext], None, None]:
    contexts: Dict[str, BrowserContext] = {}
    record_dir = os.environ.get("PLAYWRIGHT_RECORD", "0").lower() in {"1", "true"}
    context_kwargs = {}
    if record_dir:
        context_kwargs["record_video_dir"] = "playwright-report"

    init_script = """
        window.localStorage.clear();
        window.sessionStorage.clear();
        const style = document.createElement('style');
        style.innerHTML = '* { transition-duration: 0s !important; animation-duration: 0s !important; }';
        document.head.appendChild(style);
    """
    try:
        contexts["desktop"] = browser.new_context(
            viewport={"width": 1440, "height": 900},
            **context_kwargs,
        )
        contexts["desktop"].add_init_script(init_script)
        contexts["mobile"] = browser.new_context(
            viewport={"width": 414, "height": 896},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
            device_scale_factor=3,
            is_mobile=True,
            **context_kwargs,
        )
        contexts["mobile"].add_init_script(init_script)
        logger.info("Playwright contexts initialised (record=%s)", record_dir)
        yield contexts
    finally:
        for context in contexts.values():
            context.close()
        logger.debug("Playwright contexts closed")


@pytest.fixture
def author_reader_pages(multi_context: Dict[str, BrowserContext]) -> Generator[Dict[str, Page], None, None]:
    for context in multi_context.values():
        context.clear_cookies()
    pages = {name: context.new_page() for name, context in multi_context.items()}
    logger.debug("Spawned pages: %s", list(pages.keys()))
    try:
        yield pages
    finally:
        for page in pages.values():
            page.close()
        logger.debug("Pages closed")
