from django.db import models

from apps.common.models import BaseModel
from apps.chat.choices import ConversationType


class Conversation(BaseModel):


    type = models.CharField(
        max_length=10, choices=ConversationType.choices, default=ConversationType.DIRECT
    )
    title = models.CharField(max_length=255, blank=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        db_table = 'chat_conversations'
        ordering = ['-updated_at']

    def __str__(self):
        return self.title or f'Conversation {self.id}'