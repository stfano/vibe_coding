from django.urls import path

from apps.knowledge.views import (
    knowledge_document_detail,
    knowledge_document_list,
    knowledge_document_status,
    knowledge_search_verify,
)


urlpatterns = [
    path("documents/", knowledge_document_list, name="knowledge-document-list"),
    path("documents/<int:document_id>/", knowledge_document_detail, name="knowledge-document-detail"),
    path("documents/<int:document_id>/status/", knowledge_document_status, name="knowledge-document-status"),
    path("search/verify/", knowledge_search_verify, name="knowledge-search-verify"),
]
