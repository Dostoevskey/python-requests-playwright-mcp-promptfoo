from __future__ import annotations

import allure
import pytest

from src.utils.api_client import ApiClient, UserCredentials


@pytest.mark.api
@pytest.mark.parametrize("prefix", ["api_auth"])
def test_user_registration_and_login(api_client: ApiClient, prefix: str) -> None:
    creds: UserCredentials = api_client.generate_credentials(prefix=prefix)
    with allure.step("register new user"):
        registered = api_client.register_user(creds)
        assert registered.token, "Token should be issued on registration"

    with allure.step("login with newly created credentials"):
        logged_in = api_client.login_user(creds)
        assert logged_in.token == registered.token


@pytest.mark.api
def test_user_profile_update(api_client: ApiClient) -> None:
    creds = api_client.generate_credentials(prefix="api_profile")
    api_client.register_user(creds)

    with allure.step("update user profile bio"):
        response = api_client.update_profile(creds, bio="Automation enthusiast")
        assert response["user"]["bio"] == "Automation enthusiast"
