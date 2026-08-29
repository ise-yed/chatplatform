# apps/chat/models/conversation.py
from pathlib import Path
from uuid import uuid4

from django.db import models

from apps.chat.choices import ConversationType
from apps.common.models import BaseModel


def conversation_avatar_upload_to(instance, filename):
    """
    Builds a unique upload path for a group conversation's avatar,
    scoped by conversation id and suffixed with a random hex to avoid
    collisions if two admins upload a file with the same name.
    """
    extension = Path(filename).suffix.lower()
    return f'chat/avatars/{instance.id}/{uuid4().hex}{extension}'


class Conversation(BaseModel):

    type = models.CharField(
        max_length=10, choices=ConversationType.choices, default=ConversationType.DIRECT
    )
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    avatar = models.ImageField(upload_to=conversation_avatar_upload_to, blank=True, null=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        db_table = 'chat_conversations'
        ordering = ['-updated_at']

    def __str__(self):
        return self.title or f'Conversation {self.id}'