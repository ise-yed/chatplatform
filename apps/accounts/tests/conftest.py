# apps/accounts/tests/conftest.py
import pytest
from django.core.cache import cache
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user():
    """Create a test user for OTP tests."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123"
    )


@pytest.fixture
def user_without_email():
    """Create a test user without email."""
    return User.objects.create_user(
        username="testuser_noemail",
        email="",
        password="testpass123"
    )


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test to ensure isolation."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def mock_send_mail(mocker):
    """Mock Django's send_mail function."""
    return mocker.patch("django.core.mail.send_mail")


@pytest.fixture
def mock_logger(mocker):
    """Mock logger for OTP service."""
    return mocker.patch("logging.Logger.error")


@pytest.fixture
def otp_service():
    """Return OTPService class."""
    from apps.accounts.services.otp import OTPService
    return OTPService