# apps/chat/services/messages.py

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.chat.choices import MessageType
from apps.chat.models import Conversation, Message
from apps.chat.services.realtime import broadcast_new_message
from apps.common.constants import MAX_MESSAGE_LENGTH

# ============== Constants ==============
IMAGE_MIME_PREFIX = 'image/'
AUDIO_MIME_PREFIX = 'audio/'
VIDEO_MIME_PREFIX = 'video/'
DOCUMENT_MIME_PREFIXES = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
    'application/zip',
    'application/x-zip-compressed',
]
FILE_MIME_PREFIXES = [
    'application/',
    'text/',
]


# ============== Validators ==============

def validate_message_type(message_type):
    """Validate that message type is valid."""
    if message_type not in MessageType.values:
        raise ValidationError(f'Invalid message type: {message_type}')


def clean_content(content):
    """Clean and validate text content."""
    content = (content or '').strip()
    
    if not content:
        raise ValidationError('Message content cannot be empty.')
    
    if len(content) > MAX_MESSAGE_LENGTH:
        raise ValidationError(
            f'Message content cannot exceed {MAX_MESSAGE_LENGTH} characters.'
        )
    
    return content


def validate_attachment_exists(attachment):
    """Validate that attachment exists."""
    if not attachment:
        raise ValidationError('An attachment is required for this message type.')


def validate_attachment_mime_type(attachment, expected_type):
    """Validate attachment MIME type based on message type."""
    mime_type = getattr(attachment, 'content_type', '') or ''
    
    if not mime_type:
        raise ValidationError('Could not determine file type.')
    
    if expected_type == MessageType.IMAGE:
        if not mime_type.startswith(IMAGE_MIME_PREFIX):
            raise ValidationError('The uploaded file must be an image.')
        return mime_type
    
    if expected_type == MessageType.MUSIC:
        if not mime_type.startswith(AUDIO_MIME_PREFIX):
            raise ValidationError('The uploaded file must be an audio file.')
        return mime_type
    
    if expected_type == MessageType.VIDEO:
        if not mime_type.startswith(VIDEO_MIME_PREFIX):
            raise ValidationError('The uploaded file must be a video.')
        return mime_type
    
    if expected_type == MessageType.DOCUMENT:
        if mime_type not in DOCUMENT_MIME_PREFIXES:
            raise ValidationError(
                'The uploaded file must be a document (PDF, Word, Excel, TXT, etc.).'
            )
        return mime_type
    
    if expected_type == MessageType.FILE:
        # هر فایل دیگه‌ای رو قبول کن
        return mime_type
    
    return mime_type


def validate_attachment_size(attachment, max_size_mb=10):
    """Validate attachment size."""
    file_size = getattr(attachment, 'size', 0)
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if file_size > max_size_bytes:
        raise ValidationError(
            f'File size cannot exceed {max_size_mb}MB.'
        )
    
    return file_size


def validate_content_empty(content):
    """Validate that content is empty for file messages."""
    if content and content.strip():
        raise ValidationError('File messages cannot contain text content.')


def validate_attachment_empty(attachment):
    """Validate that attachment is empty for text messages."""
    if attachment:
        raise ValidationError('Text messages cannot contain an attachment.')


# ============== Main Validation Function ==============

def validate_message_payload(*, message_type, content, attachment):
    """
    Validate message payload based on message type.
    Returns cleaned content.
    """
    # 1. Validate message type
    validate_message_type(message_type)
    
    # 2. Clean content
    content = (content or '').strip()
    
    # 3. Validate based on type
    if message_type == MessageType.TEXT:
        # TEXT: فقط متن، بدون فایل
        validate_attachment_empty(attachment)
        return clean_content(content)
    
    # 4. File-based messages (IMAGE, MUSIC, VIDEO, DOCUMENT, FILE)
    validate_attachment_exists(attachment)
    validate_content_empty(content)
    validate_attachment_mime_type(attachment, message_type)
    validate_attachment_size(attachment)
    
    # Content should be empty for file messages
    return ''


# ============== Helper Functions ==============

def get_file_info(attachment):
    """Extract file information from attachment."""
    if not attachment:
        return {}
    
    return {
        'file_name': getattr(attachment, 'name', ''),
        'file_size': getattr(attachment, 'size', None),
        'mime_type': getattr(attachment, 'content_type', ''),
    }


# ============== Main Service ==============

def send_message(*, conversation_id, sender, content='', message_type=MessageType.TEXT, attachment=None):
    """
    Send a message in a conversation.
    
    Supports: TEXT, IMAGE, MUSIC, VIDEO, DOCUMENT, FILE
    """
    # Validate and clean content
    content = validate_message_payload(
        message_type=message_type,
        content=content,
        attachment=attachment,
    )
    
    # Get file info
    file_info = get_file_info(attachment)
    
    with transaction.atomic():
        message = Message.objects.create(
            conversation_id=conversation_id,
            sender=sender,
            type=message_type,
            content=content,
            attachment=attachment,
            file_name=file_info.get('file_name', ''),
            file_size=file_info.get('file_size', None),
            mime_type=file_info.get('mime_type', ''),
        )
        
        # Update conversation timestamp
        Conversation.objects.filter(id=conversation_id).update(
            updated_at=timezone.now()
        )
        
        transaction.on_commit(lambda: broadcast_new_message(message=message))
    
    return message