from django.db import models


class AuthType(models.TextChoices):
    """
    How a DeviceSession was created.

    Determines how apps.accounts.services.authentication.revoke_device_session
    actually enforces a revoke, since web and API logins have nothing
    in common to revoke:

    - API: a JWT refresh token, tracked by refresh_token_jti. Revoke
      blacklists it (rest_framework_simplejwt.token_blacklist) and the
      per-request DeviceSessionAuthentication check
      (apps.accounts.authentication) rejects that device's access
      token on its very next call.
    - WEB: a Django session-cookie login, tracked by django_session_key.
      Revoke deletes the underlying django.contrib.sessions.models.Session
      row, so SessionMiddleware treats that browser as logged out on
      its very next request.
    """

    WEB = "web", "Web"
    API = "api", "API"
