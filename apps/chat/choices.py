from django.db import models


class ConversationType(models.TextChoices):
    DIRECT = 'direct', 'Direct'
    GROUP = 'group', 'Group'


class ParticipantRole(models.TextChoices):
    MEMBER = 'member', 'Member'
    ADMIN = 'admin', 'Admin'


class MessageType(models.TextChoices):
    TEXT = 'text', 'Text'
    IMAGE = 'image', 'Image'
    FILE = 'file', 'File'