from django.conf import settings
from django.db import models

from apps.common.models import BaseModel
from apps.chat.choices import MessageType


class Message(BaseModel):


    conversation = models.ForeignKey(
        'chat.Conversation', on_delete=models.CASCADE, related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages'
    )
    type = models.CharField(max_length=10, choices=MessageType.choices, default=MessageType.TEXT)
    content = models.TextField()
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'chat_messages'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender}: {self.content[:30]}'