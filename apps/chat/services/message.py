from pathlib import Path

import magic
from PIL import Image, UnidentifiedImageError

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.chat.choices import ConversationUpdateAction, MessageType
from apps.chat.models import Conversation, Message
from apps.chat.models.participant import Participant
from apps.chat.services.realtime import (
    broadcast_conversation_update,
    broadcast_new_message,
)
from apps.common.constants import MAX_MESSAGE_LENGTH


# ============================================================
# Constants
# ============================================================

MAX_ATTACHMENT_SIZE_MB = 10
MAX_ATTACHMENT_SIZE_BYTES = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024

MAX_IMAGE_DIMENSION = 4096
MAGIC_HEADER_SIZE = 2048


ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
}

ALLOWED_AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".aac",
    ".ogg",
    ".m4a",
    ".flac",
}

ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",
    ".flv",
}

ALLOWED_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
    ".rtf",
    ".csv",
    ".zip",
    ".rar",
    ".7z",
}


# ============================================================
# MIME definitions
# ============================================================

ALLOWED_DOCUMENT_MIMES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/rtf",
    "text/csv",
    "application/zip",
    "application/x-rar",
    "application/x-rar-compressed",
    "application/x-7z-compressed",
}


# Extension -> allowed MIME types
IMAGE_MIME_MAP = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".gif": {"image/gif"},
    ".webp": {"image/webp"},
    ".bmp": {"image/bmp", "image/x-ms-bmp"},
}

AUDIO_MIME_MAP = {
    ".mp3": {"audio/mpeg", "audio/mp3"},
    ".wav": {"audio/wav", "audio/x-wav"},
    ".aac": {"audio/aac", "audio/x-hx-aac-adts"},
    ".ogg": {"audio/ogg", "application/ogg"},
    ".m4a": {"audio/mp4"},
    ".flac": {"audio/flac", "audio/x-flac"},
}

VIDEO_MIME_MAP = {
    ".mp4": {"video/mp4"},
    ".avi": {"video/x-msvideo"},
    ".mov": {"video/quicktime"},
    ".mkv": {"video/x-matroska"},
    ".webm": {"video/webm"},
    ".flv": {"video/x-flv"},
}


# ============================================================
# Basic validators
# ============================================================

def validate_message_type(message_type):
    if message_type not in MessageType.values:
        raise ValidationError(
            f"Invalid message type: {message_type}"
        )


def clean_content(content):
    content = (content or "").strip()

    if not content:
        raise ValidationError(
            "Message content cannot be empty."
        )

    if len(content) > MAX_MESSAGE_LENGTH:
        raise ValidationError(
            f"Message content cannot exceed "
            f"{MAX_MESSAGE_LENGTH} characters."
        )

    return content


def validate_attachment_exists(attachment):
    if not attachment:
        raise ValidationError(
            "An attachment is required for this message type."
        )


def validate_attachment_size(attachment):
    if attachment.size > MAX_ATTACHMENT_SIZE_BYTES:
        raise ValidationError(
            f"File size cannot exceed "
            f"{MAX_ATTACHMENT_SIZE_MB}MB."
        )


def get_file_extension(attachment):
    filename = getattr(attachment, "name", "")

    return Path(filename).suffix.lower()


def validate_extension(extension, allowed_extensions):
    if extension not in allowed_extensions:
        raise ValidationError(
            f"Unsupported file extension: {extension or 'unknown'}"
        )


# ============================================================
# MIME detection
# ============================================================

def detect_mime_type(file):
    """
    Detect the actual MIME type from the file content.

    The client-provided Content-Type is intentionally ignored.
    """

    file.seek(0)

    header = file.read(MAGIC_HEADER_SIZE)

    file.seek(0)

    if not header:
        raise ValidationError("The uploaded file is empty.")

    try:
        mime_type = magic.from_buffer(
            header,
            mime=True,
        )
    except Exception as exc:
        raise ValidationError(
            "Could not determine the file type."
        ) from exc

    return mime_type


# ============================================================
# MIME validation
# ============================================================

def validate_image_mime(extension, mime_type):
    allowed_mimes = IMAGE_MIME_MAP.get(extension)

    if not allowed_mimes:
        raise ValidationError(
            f"Unsupported image extension: {extension}"
        )

    if mime_type not in allowed_mimes:
        raise ValidationError(
            "File extension does not match the actual file type."
        )


def validate_audio_mime(extension, mime_type):
    allowed_mimes = AUDIO_MIME_MAP.get(extension)

    if not allowed_mimes:
        raise ValidationError(
            f"Unsupported audio extension: {extension}"
        )

    if mime_type not in allowed_mimes:
        raise ValidationError(
            "File extension does not match the actual file type."
        )


def validate_video_mime(extension, mime_type):
    allowed_mimes = VIDEO_MIME_MAP.get(extension)

    if not allowed_mimes:
        raise ValidationError(
            f"Unsupported video extension: {extension}"
        )

    if mime_type not in allowed_mimes:
        raise ValidationError(
            "File extension does not match the actual file type."
        )


def validate_document_mime(mime_type):
    if mime_type not in ALLOWED_DOCUMENT_MIMES:
        raise ValidationError(
            f"Unsupported document type: {mime_type}"
        )


# ============================================================
# Image validation
# ============================================================

def validate_image_file(file):
    """
    Validate image structure and dimensions using Pillow.
    """

    file.seek(0)

    try:
        with Image.open(file) as image:
            image.verify()

        file.seek(0)

        with Image.open(file) as image:
            width, height = image.size

    except UnidentifiedImageError as exc:
        raise ValidationError(
            "Invalid image file."
        ) from exc

    except Exception as exc:
        raise ValidationError(
            "Could not validate the image file."
        ) from exc

    finally:
        file.seek(0)

    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise ValidationError(
            f"Image dimensions cannot exceed "
            f"{MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION} pixels."
        )


# ============================================================
# Attachment validation
# ============================================================

def validate_attachment(attachment, expected_type):
    """
    Complete attachment validation.

    Returns:
        str: detected MIME type
    """

    validate_attachment_exists(attachment)
    validate_attachment_size(attachment)

    extension = get_file_extension(attachment)

    mime_type = detect_mime_type(attachment)

    # -------------------------
    # Image
    # -------------------------

    if expected_type == MessageType.IMAGE:
        validate_extension(
            extension,
            ALLOWED_IMAGE_EXTENSIONS,
        )

        validate_image_mime(
            extension,
            mime_type,
        )

        validate_image_file(attachment)

        return mime_type

    # -------------------------
    # Audio
    # -------------------------

    if expected_type == MessageType.MUSIC:
        validate_extension(
            extension,
            ALLOWED_AUDIO_EXTENSIONS,
        )

        validate_audio_mime(
            extension,
            mime_type,
        )

        return mime_type

    # -------------------------
    # Video
    # -------------------------

    if expected_type == MessageType.VIDEO:
        validate_extension(
            extension,
            ALLOWED_VIDEO_EXTENSIONS,
        )

        validate_video_mime(
            extension,
            mime_type,
        )

        return mime_type

    # -------------------------
    # Document
    # -------------------------

    if expected_type == MessageType.DOCUMENT:
        validate_extension(
            extension,
            ALLOWED_DOCUMENT_EXTENSIONS,
        )

        validate_document_mime(
            mime_type,
        )

        return mime_type

    # -------------------------
    # Generic file
    # -------------------------

    if expected_type == MessageType.FILE:
        allowed_extensions = (
            ALLOWED_IMAGE_EXTENSIONS
            | ALLOWED_AUDIO_EXTENSIONS
            | ALLOWED_VIDEO_EXTENSIONS
            | ALLOWED_DOCUMENT_EXTENSIONS
        )

        validate_extension(
            extension,
            allowed_extensions,
        )

        return mime_type

    raise ValidationError(
        f"Unsupported message type: {expected_type}"
    )


# ============================================================
# Message payload validation
# ============================================================

def validate_content_empty(content):
    if content and content.strip():
        raise ValidationError(
            "File messages cannot contain text content."
        )


def validate_attachment_empty(attachment):
    if attachment:
        raise ValidationError(
            "Text messages cannot contain an attachment."
        )


def validate_message_payload(
    *,
    message_type,
    content,
    attachment,
):
    """
    Validate the complete message payload.

    Returns:
        tuple[str, str | None]:
            cleaned content
            detected MIME type
    """

    validate_message_type(message_type)

    content = (content or "").strip()

    # -------------------------
    # Text message
    # -------------------------

    if message_type == MessageType.TEXT:
        validate_attachment_empty(attachment)

        return (
            clean_content(content),
            None,
        )

    # -------------------------
    # File message
    # -------------------------

    validate_attachment_exists(attachment)
    validate_content_empty(content)

    mime_type = validate_attachment(
        attachment,
        message_type,
    )

    return (
        "",
        mime_type,
    )


# ============================================================
# File metadata
# ============================================================

def get_file_info(attachment, mime_type=None):
    if not attachment:
        return {}

    return {
        "file_name": getattr(
            attachment,
            "name",
            "",
        ),
        "file_size": getattr(
            attachment,
            "size",
            None,
        ),
        "mime_type": mime_type or "",
    }


# ============================================================
# Send message
# ============================================================

def send_message(
    *,
    conversation_id,
    sender,
    content="",
    message_type=MessageType.TEXT,
    attachment=None,
):
    """
    Create a message and update the conversation.

    All database changes happen inside one transaction.
    Realtime events are sent only after successful commit.
    """

    # ========================================================
    # 1. Authorization
    # ========================================================

    is_participant = Participant.objects.filter(
        conversation_id=conversation_id,
        user_id=sender.id,
        # is_active=True,
    ).exists()

    if not is_participant:
        raise ValidationError(
            "You are not an active participant "
            "in this conversation."
        )

    # ========================================================
    # 2. Validate message payload
    # ========================================================

    content, detected_mime_type = validate_message_payload(
        message_type=message_type,
        content=content,
        attachment=attachment,
    )

    # ========================================================
    # 3. File metadata
    # ========================================================

    file_info = get_file_info(
        attachment,
        mime_type=detected_mime_type,
    )

    # ========================================================
    # 4. Database transaction
    # ========================================================

    with transaction.atomic():

        conversation = (
            Conversation.objects
            .select_for_update()
            .get(id=conversation_id)
        )

        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            type=message_type,
            content=content,
            attachment=attachment,
            file_name=file_info.get(
                "file_name",
                "",
            ),
            file_size=file_info.get(
                "file_size",
            ),
            mime_type=file_info.get(
                "mime_type",
                "",
            ),
        )

        conversation.last_message = message
        conversation.updated_at = timezone.now()

        conversation.save(
            update_fields=[
                "last_message",
                "updated_at",
            ]
        )

        # ====================================================
        # 5. Participants who should receive the update
        # ====================================================

        participant_ids = list(
            Participant.objects
            .filter(
                conversation_id=conversation_id,
                # is_active=True,
            )
            .exclude(
                user_id=sender.id,
            )
            .values_list(
                "user_id",
                flat=True,
            )
        )

        # ====================================================
        # 6. Realtime broadcasts
        # ====================================================

        transaction.on_commit(
            lambda: broadcast_new_message(
                message=message,
            )
        )

        if participant_ids:
            transaction.on_commit(
                lambda: broadcast_conversation_update(
                    conversation=conversation,
                    action=ConversationUpdateAction.new_message,
                    last_message=message,
                    participant_ids=participant_ids,
                )
            )

    return message