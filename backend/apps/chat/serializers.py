from rest_framework import serializers


class ChatMessageRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=4000, trim_whitespace=True)
    session_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_message(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Message is required.")
        return value
