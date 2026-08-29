from apps.chat.choices import ParticipantRole
from apps.chat.models import Participant


def is_user_participant(*, conversation_id, user):
    return Participant.objects.filter(conversation_id=conversation_id, user=user).exists()



def get_latest_other_participant_read_message(*, conversation_id, user):
    """
    Returns the furthest-read Message among all OTHER participants of
    this conversation — i.e. whichever other participant has read the
    most messages. A message is considered "seen" once its
    created_at <= this watermark.

    This matches the app's "seen" semantics everywhere else (see
    chat.js's markMessagesAsSeen): a message counts as seen as soon
    as AT LEAST ONE other participant has read it, not only once
    every participant has. In a direct (2-person) conversation
    there's exactly one other participant, so this reduces to the
    old single-participant behavior automatically. In a group, it
    picks the furthest-advanced reader instead of an arbitrary one —
    which is the previous bug: .exclude(user=user).first() returned
    whichever row Postgres happened to return first, unrelated to who
    had actually read the most.
    """
    participant = (
        Participant.objects.filter(conversation_id=conversation_id)
        .exclude(user=user)
        .exclude(last_read_message__isnull=True)
        .select_related('last_read_message')
        .order_by('-last_read_message__created_at')
        .first()
    )
    return participant.last_read_message if participant else None



def is_conversation_admin(*, conversation_id, user):
    """
    True اگه `user` عضو این گفتگو با نقش ADMIN باشه. جدا از
    is_user_participant نگه داشته شده چون این‌جا شرط سخت‌گیرانه‌تری
    (ادمین بودن، نه فقط عضو بودن) لازمه — و جاهایی که فقط باید عضویت
    چک بشه نباید به این تابع وابسته باشن.
    """
    return Participant.objects.filter(
        conversation_id=conversation_id, user=user, role=ParticipantRole.ADMIN
    ).exists()


def get_group_participants(*, conversation_id):
    """
    همه‌ی Participantهای یه گفتگوی گروهی به همراه User مربوطه
    (select_related تا N+1 query نخوریم موقع serialize کردن username).
    """
    return (
        Participant.objects.filter(conversation_id=conversation_id)
        .select_related('user')
        .order_by('user__username')
    )