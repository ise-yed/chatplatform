from apps.chat.models import Message


def get_messages_for_conversation(*, conversation_id):
    """
    پیام‌های یه گفتگوی مشخص رو به ترتیب زمانی (قدیم به جدید) برمی‌گردونه.

    is_deleted=False فیلتر می‌شه چون حذف پیام soft-delete ـه (فاز ۲) —
    پیام‌های "حذف‌شده" نباید تو خروجی عادی لیست ظاهر بشن.
    select_related('sender') چون سریالایزر برای هر پیام باید یوزرنیم
    فرستنده رو نشون بده؛ بدون این، هر پیام یه query جدا برای گرفتن
    sender می‌زد.
    """
    return (
        Message.objects.filter(conversation_id=conversation_id, is_deleted=False)
        .select_related('sender')
        .order_by('created_at')
    )