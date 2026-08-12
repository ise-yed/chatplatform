from apps.chat.models import Conversation


def get_conversations_for_user(*, user):
    """
    همه‌ی گفتگوهایی که کاربر داده‌شده عضوشه رو برمی‌گردونه.

    برای صفحه‌ی لیست گفتگوها (inbox) استفاده می‌شه. با prefetch_related
    روی participants__user، از N+1 query جلوگیری می‌کنه — چون سریالایزر
    برای نمایش لیست شرکت‌کننده‌های هر گفتگو باید به user هر participant
    دسترسی داشته باشه.
    """
    return (
        Conversation.objects.filter(participants__user=user)
        .distinct()
        .prefetch_related('participants__user')
    )
    
def get_conversation_for_user(*, conversation_id, user):
    """
    یه گفتگوی مشخص رو فقط در صورتی برمی‌گردونه که کاربر داده‌شده
    عضوش باشه؛ در غیر این صورت None.

    این تابع لایه‌ی دفاعی اصلی در برابر IDOR ـه: صرفاً داشتن UUID یه
    گفتگو کافی نیست، کاربر باید واقعاً عضوش باشه. هم تو API views
    هم (به‌شکل معادلش) تو WebSocket Consumer استفاده می‌شه تا این
    قانون یه‌جا تعریف بشه، نه چندبار تکراری.
    """
    return Conversation.objects.filter(
        id=conversation_id, participants__user=user
    ).first()