"""Tests for secret masking utility."""

from app.core.security import mask_secrets


def test_mask_aws_access_key() -> None:
    content = "Error: AKIAIOSFODNN7EXAMPLE not authorized"
    masked = mask_secrets(content)
    assert "AKIAIOSFODNN7EXAMPLE" not in masked
    assert "MASKED" in masked


def test_mask_github_token() -> None:
    token = "ghp_" + "a" * 36
    masked = mask_secrets(f"Using token {token}")
    assert token not in masked


def test_mask_password_assignment() -> None:
    content = 'password: "super-secret-123"'
    masked = mask_secrets(content)
    assert "super-secret-123" not in masked
