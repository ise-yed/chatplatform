from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.common.models import BaseModel


class User(AbstractUser, BaseModel):
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.username