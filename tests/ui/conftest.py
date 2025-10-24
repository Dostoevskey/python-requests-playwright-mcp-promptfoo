from __future__ import annotations

from typing import Dict, Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page


@pytest.fixture(scope="session")
def multi_context(browser: Browser, tmp_path_factory) -> Generator[Dict[str, BrowserContext], None, None]:
    """
    Provide two contexts (desktop + mobile) for multi-context UI tests.
    Use an explicit mobile options dict to avoid importing `devices` from Playwright,
    and place video artifacts in per-run temp dirs.
    """
    contexts: Dict[str, BrowserContext] = {}
    videos_dir = tmp_path_factory.mktemp("playwright_videos")
    videos_mobile = tmp_path_factory.mktemp("playwright_videos_mobile")

    # Minimal mobile emulation options (sufficient for most responsive UI tests)
    mobile_opts = {
        "viewport": {"width": 414, "height": 896},
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
        "device_scale_factor": 3,
        "is_mobile": True,
        "has_touch": True,
    }

    try:
        contexts["desktop"] = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(videos_dir),
        )
        contexts["desktop"].add_init_script("window.localStorage.clear(); window.sessionStorage.clear();")

        contexts["mobile"] = browser.new_context(
            **mobile_opts,
            record_video_dir=str(videos_mobile),
        )
        contexts["mobile"].add_init_script("window.localStorage.clear(); window.sessionStorage.clear();")

        yield contexts
    finally:
        # Ensure contexts are closed even if tests fail
        for context in contexts.values():
            try:
                context.close()
            except Exception:
                pass




@pytest.fixture
def author_reader_pages(multi_context: Dict[str, BrowserContext], settings) -> Generator[Dict[str, Page], None, None]:
    """
    Create Page objects for each context and navigate to the frontend root.
    If tests require authenticated author state, extend this fixture to:
      - create an author via the API (ApiClient)
      - set the auth token into localStorage for the page context before navigation
    """
    pages: Dict[str, Page] = {}
    for name, ctx in multi_context.items():
        page = ctx.new_page()
        # Navigate to the app root so pages are ready for test actions
        page.goto(settings.frontend_url)
        pages[name] = page

    try:
        yield pages
    finally:
        for page in pages.values():
            try:
                page.close()
            except Exception:
                pass
