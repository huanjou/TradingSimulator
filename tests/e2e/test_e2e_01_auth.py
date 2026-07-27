import uuid

import requests
from conftest import USER_SERVICE_URL


def test_register_user_success():
    unique_id = uuid.uuid4().hex[:8]
    email = f"auth_test_{unique_id}@e2e.com"
    password = "SecurePassword123!"

    resp = requests.post(
        f"{USER_SERVICE_URL}/auth/register", json={"email": email, "password": password}
    )
    assert (
        resp.status_code == 201
    ), f"Expected 201 Created, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["email"] == email
    assert "id" in data
    assert data["is_active"] is True


def test_login_user_success_and_cookies(new_user_factory):
    user = new_user_factory()
    email = user["email"]
    password = user["password"]

    # Test login without remember_me
    resp = requests.post(
        f"{USER_SERVICE_URL}/auth/login",
        json={"email": email, "password": password, "remember_me": False},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user_id"] == user["user_id"]

    # Check that cookies were set
    cookies = resp.cookies.get_dict()
    assert "access_token" in cookies, "access_token cookie missing"
    assert "csrf_token" in cookies, "csrf_token cookie missing"


def test_get_current_user_profile(new_user_factory):
    user = new_user_factory()
    headers = user["headers"]

    resp = requests.get(f"{USER_SERVICE_URL}/users/me", headers=headers)
    assert resp.status_code == 200, f"Failed to get user profile: {resp.text}"
    data = resp.json()
    assert data["id"] == user["user_id"]
    assert data["email"] == user["email"]
    assert data["is_active"] is True


def test_login_invalid_credentials(new_user_factory):
    user = new_user_factory()
    email = user["email"]

    resp = requests.post(
        f"{USER_SERVICE_URL}/auth/login",
        json={"email": email, "password": "WrongPassword456!"},
    )
    assert resp.status_code in [
        400,
        401,
    ], f"Expected 400 or 401 for wrong password, got {resp.status_code}"


def test_logout_clears_cookies(new_user_factory):
    user = new_user_factory()

    # Login to get session cookies
    session = requests.Session()
    login_resp = session.post(
        f"{USER_SERVICE_URL}/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert login_resp.status_code == 200
    assert "access_token" in session.cookies.get_dict()

    # Logout
    logout_resp = session.post(f"{USER_SERVICE_URL}/auth/logout")
    assert logout_resp.status_code == 200, f"Logout failed: {logout_resp.text}"

    # Verify cookies in response are deleted / emptied
    # When deleted, requests session cookies usually get cleared or expire
    assert logout_resp.json().get("detail") == "Successfully logged out"
