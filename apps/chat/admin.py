from django.contrib import admin

from apps.chat.models import Conversation, Message, Participant


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'title', 'is_archived', 'created_at')
    list_filter = ('type', 'is_archived')
    search_fields = ('title',)


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'user', 'role', 'joined_at')
    list_filter = ('role',)
    autocomplete_fields = ('conversation', 'user')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'type', 'is_deleted', 'created_at')
    list_filter = ('type', 'is_deleted')
    search_fields = ('content',)