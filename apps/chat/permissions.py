from rest_framework.permissions import BasePermission

from apps.chat.selectors import is_user_participant


class IsConversationParticipant(BasePermission):
    """
    فقط به کاربرانی اجازه دسترسی می‌ده که عضو گفتگوی مشخص‌شده
    (conversation_id در URL) هستن.

    has_permission (نه has_object_permission) استفاده می‌شه چون
    view ما از get_object() استفاده نمی‌کنه (مستقیم از URL kwargs
    و selector می‌خونه)، پس has_object_permission خودکار صدا زده
    نمی‌شد. has_permission قبل از اجرای هر متد (GET/POST) به‌طور
    خودکار توسط DRF چک می‌شه، بدون نیاز به فراخوانی دستی.
    """
    message = 'شما عضو این گفتگو نیستید.'

    def has_permission(self, request, view):
        conversation_id = view.kwargs.get('conversation_id')
        return is_user_participant(conversation_id=conversation_id, user=request.user)