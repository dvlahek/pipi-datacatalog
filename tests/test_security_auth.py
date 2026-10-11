from app.config import Settings
from app.security.auth import (
    create_access_token,
    decode_access_token,
    password_hash,
    validate_auth_configuration,
    verify_login,
)


def _settings(password: str = "correct-horse-battery-staple") -> Settings:
    return Settings(
        auth_enabled=True,
        auth_username="admin",
        auth_password_hash=password_hash(password),
        auth_jwt_secret="s" * 48,
        auth_token_ttl_minutes=15,
    )


def test_password_hash_and_jwt_roundtrip() -> None:
    settings = _settings()
    validate_auth_configuration(settings)

    assert verify_login("admin", "correct-horse-battery-staple", settings) is True
    assert verify_login("admin", "wrong-password", settings) is False
    assert verify_login("other", "correct-horse-battery-staple", settings) is False

    token, expires_in = create_access_token("admin", settings)
    claims = decode_access_token(token, settings)

    assert expires_in == 900
    assert claims["sub"] == "admin"
    assert claims["role"] == "admin"


def test_auth_configuration_fails_closed_when_enabled_without_secrets() -> None:
    settings = Settings(auth_enabled=True)
    try:
        validate_auth_configuration(settings)
    except RuntimeError as exc:
        assert "AUTH_USERNAME" in str(exc)
        assert "AUTH_PASSWORD_HASH" in str(exc)
        assert "AUTH_JWT_SECRET" in str(exc)
    else:
        raise AssertionError("Expected auth configuration failure")
