from django.db import transaction

from apps.chat.models import Conversation
from apps.accounts.services.realtime import broadcast_user_updated


def update_user_profile(*, user, validated_data):
    with transaction.atomic():
        for field, value in validated_data.items():
            setattr(user, field, value)

        user.save(update_fields=validated_data.keys())

        direct_conversations = Conversation.objects.filter(
            type="direct",
            participants__user=user,
        )

        participant_ids = set()

        for conversation in direct_conversations:
            participant_ids.update(
                conversation.participants
                .exclude(user_id=user.id)
                .values_list("user_id", flat=True)
            )

        if participant_ids:
            transaction.on_commit(
                lambda: broadcast_user_updated(
                    user_id=user.id,
                    username=user.username,
                    avatar_url=(
                        user.avatar.url
                        if user.avatar
                        else None
                    ),
                    participant_ids=list(participant_ids),
                )
            )

    return user