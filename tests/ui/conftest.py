from __future__ import annotations

from typing import Dict, Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, devices
from pathlib import Path


@pytest.fixture(scope="session")
def multi_context(browser: Browser, tmp_path_factory) -> Generator[Dict[str, BrowserContext], None, None]:
    """
    Provide two contexts (desktop + mobile) for multi-context UI tests.
    Use Playwright device descriptors for more accurate mobile emulation
    and per-run directories for video artifacts.
    """
    contexts: Dict[str, BrowserContext] = {}
    videos_dir = tmp_path_factory.mktemp("playwright_videos")
    videos_mobile = tmp_path_factory.mktemp("playwright_videos_mobile")

    try:
        contexts["desktop"] = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(videos_dir),
        )
        contexts["desktop"].add_init_script("window.localStorage.clear(); window.sessionStorage.clear();")
        contexts["mobile"] = browser.new_context(
            **devices["iPhone 12"],
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

