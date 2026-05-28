def get_health_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "doctor-chat-backend",
        "dependencies": {
            "database": "configured",
            "redis": "configured",
            "qdrant": "configured",
            "minio": "configured",
            "embedding_service": "configured",
            "ollama": "optional",
        },
    }
