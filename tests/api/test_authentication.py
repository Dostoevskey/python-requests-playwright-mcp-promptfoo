from __future__ import annotations

import allure
import pytest

from src.utils.api_client import ApiClient, UserCredentials
from src.utils.logger import get_logger

logger = get_logger(__name__)


@pytest.mark.api
@pytest.mark.parametrize("prefix", ["api_auth"])
def test_user_registration_and_login(api_client: ApiClient, prefix: str) -> None:
    creds: UserCredentials = api_client.generate_credentials(prefix=prefix)
    logger.info("Testing registration/login for %s", creds.username)
    with allure.step("register new user"):
        registered = api_client.register_user(creds)
        assert registered.token, "Token should be issued on registration"
        logger.debug("Registration token issued for %s", creds.username)

    with allure.step("login with newly created credentials"):
        logged_in = api_client.login_user(creds)
        assert logged_in.token == registered.token
        logger.info("Login verified for %s", creds.username)


@pytest.mark.api
def test_user_profile_update(api_client: ApiClient) -> None:
    creds = api_client.generate_credentials(prefix="api_profile")
    api_client.register_user(creds)
    logger.info("Testing profile update for %s", creds.username)

    with allure.step("update user profile bio"):
        response = api_client.update_profile(creds, bio="Automation enthusiast", password=creds.password)
        assert response["user"]["bio"] == "Automation enthusiast"
        logger.info("Profile updated for %s", creds.username)
