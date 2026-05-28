from django.urls import path

from apps.chat.views import create_chat_message


urlpatterns = [
    path("messages/", create_chat_message, name="chat-message-list"),
]
