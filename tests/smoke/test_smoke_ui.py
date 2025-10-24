from __future__ import annotations

import pytest


@pytest.mark.ui
@pytest.mark.smoke
def test_smoke_frontend_loads(page, settings) -> None:
    page.goto(settings.frontend_url)
    header = page.locator("h1")
    header.wait_for(timeout=5000)
    assert header.count() > 0, "Expected at least one primary heading on landing page"
