from django.contrib import admin

from apps.chat.models import ChatMessage, ChatSession


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    fields = ("created_at", "role", "message_type", "content", "safety_flags")
    readonly_fields = ("created_at",)


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "user", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "title", "user__username")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (ChatMessageInline,)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "message_type", "created_at")
    list_filter = ("role", "message_type", "created_at")
    search_fields = ("id", "session__id", "content", "user__username")
    readonly_fields = ("id", "created_at")
