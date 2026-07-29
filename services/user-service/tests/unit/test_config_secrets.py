import pytest
from app.core.config import Settings
from pydantic import ValidationError

DSN = "postgresql://admin:password@127.0.0.1:5432/user_db"
STRONG_SECRET = "a" * 32
WEAK_SECRET = "short_secret"


def _settings(**overrides) -> Settings:
    # _env_file=None keeps a developer's local .env from leaking into the test.
    kwargs = {"DATABASE_URL": DSN, "JWT_SECRET": STRONG_SECRET, "_env_file": None}
    kwargs.update(overrides)
    return Settings(**kwargs)


def test_production_rejects_short_jwt_secret():
    with pytest.raises(ValidationError, match="at least 32 characters"):
        _settings(ENVIRONMENT="production", JWT_SECRET=WEAK_SECRET)


def test_production_accepts_32_char_jwt_secret():
    settings = _settings(ENVIRONMENT="production", JWT_SECRET=STRONG_SECRET)
    assert settings.JWT_SECRET.get_secret_value() == STRONG_SECRET


def test_production_rejects_secret_one_char_too_short():
    with pytest.raises(ValidationError):
        _settings(ENVIRONMENT="production", JWT_SECRET="a" * 31)


@pytest.mark.parametrize("environment", ["development", "test", "staging"])
def test_non_production_allows_weak_secret(environment):
    # The length rule is only enforced in production so local dev stays easy.
    settings = _settings(ENVIRONMENT=environment, JWT_SECRET=WEAK_SECRET)
    assert settings.ENVIRONMENT == environment


def test_jwt_secret_is_masked_in_repr():
    settings = _settings(JWT_SECRET="super_secret_value_that_must_not_leak")
    # SecretStr keeps the value out of logs and tracebacks.
    assert "super_secret_value_that_must_not_leak" not in repr(settings)
    assert "super_secret_value_that_must_not_leak" not in str(settings.JWT_SECRET)


def test_jwt_secret_is_required(monkeypatch):
    # A missing secret must fail fast at startup rather than fall back to a
    # default that would sign tokens with a predictable key.
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL=DSN, _env_file=None)


def test_database_url_must_be_a_postgres_dsn():
    with pytest.raises(ValidationError):
        _settings(DATABASE_URL="not-a-dsn")


def test_cookie_secure_only_in_production():
    assert _settings(ENVIRONMENT="production").COOKIE_SECURE is True
    assert _settings(ENVIRONMENT="development").COOKIE_SECURE is False


def test_access_token_lifetime_is_short_by_default():
    # Access tokens are short-lived; sessions are extended via refresh tokens.
    settings = _settings()
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 7
