from django.conf import settings
from django.db import models

from apps.common.models import BaseModel
from apps.chat.choices import ParticipantRole


class Participant(BaseModel):


    conversation = models.ForeignKey(
        'chat.Conversation', on_delete=models.CASCADE, related_name='participants'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversation_participations'
    )
    role = models.CharField(max_length=10, choices=ParticipantRole.choices, default=ParticipantRole.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_message = models.ForeignKey(
        'chat.Message', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    class Meta:
        db_table = 'chat_participants'
        constraints = [
            models.UniqueConstraint(fields=['conversation', 'user'], name='unique_conversation_participant')
        ]

    def __str__(self):
        return f'{self.user} in {self.conversation}'