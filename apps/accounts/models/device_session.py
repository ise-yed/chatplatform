import uuid
from apps.common.models import BaseModel

from django.conf import settings
from django.db import models
from django.utils import timezone


class DeviceSession( BaseModel):


    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_sessions",
    )

    device_name = models.CharField(
        max_length=100,
        blank=True,
    )

    device_type = models.CharField(
        max_length=30,
        blank=True,
    )

    user_agent = models.TextField(
        blank=True,
    )

    refresh_token_jti = models.CharField(
        max_length=255,
        unique=True,
    )

    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-last_used_at", "-created_at"]
        db_table = "accounts_device_sessions"

    @property
    def is_revoked(self):
        return self.revoked_at is not None

    @property
    def is_active(self):
        """
        Single source of truth for "is this session still usable" —
        used by DeviceSessionSerializer, the JWT WebSocket middleware
        (apps.chat.middleware), and DeviceSessionAuthentication
        (apps.accounts.authentication) so the three places that need
        to answer this question can't quietly drift out of sync.
        """
        return not self.is_revoked and (self.expires_at is None or self.expires_at > timezone.now())