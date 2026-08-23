import uuid
from apps.common.models import BaseModel

from django.conf import settings
from django.db import models


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