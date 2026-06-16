from __future__ import annotations

from rest_framework import serializers

from apps.knowledge.models import KnowledgeDocument


class KnowledgeDocumentFilterSerializer(serializers.Serializer):
    source = serializers.CharField(required=False, allow_blank=True, max_length=80)
    department_code = serializers.CharField(required=False, allow_blank=True, max_length=40)
    status = serializers.ChoiceField(required=False, choices=KnowledgeDocument.Status.choices)
    q = serializers.CharField(required=False, allow_blank=True, max_length=200)
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=50, default=20)


class KnowledgeDocumentStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=KnowledgeDocument.Status.choices)


class KnowledgeSearchVerificationSerializer(serializers.Serializer):
    query = serializers.CharField(required=True, allow_blank=False, max_length=1000)
    top_k = serializers.IntegerField(required=False, min_value=1, max_value=20, default=5)
    source = serializers.CharField(required=False, allow_blank=True, max_length=80)
    department_code = serializers.CharField(required=False, allow_blank=True, max_length=40)
    include_needs_review = serializers.BooleanField(required=False, default=False)
