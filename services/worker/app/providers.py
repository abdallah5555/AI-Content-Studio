import os
from dataclasses import dataclass

from fastapi import APIRouter

router = APIRouter(prefix="/providers", tags=["providers"])


@dataclass(frozen=True)
class ProviderDefinition:
    id: str
    label: str
    env_key: str
    priority: int
    capability: str = "text"


TEXT_PROVIDERS = (
    ProviderDefinition(id="gemini", label="Google Gemini", env_key="GEMINI_API_KEY", priority=1),
    ProviderDefinition(id="groq", label="Groq", env_key="GROQ_API_KEY", priority=2),
    ProviderDefinition(id="openrouter", label="OpenRouter", env_key="OPENROUTER_API_KEY", priority=3),
)

MEDIA_PROVIDERS = (
    ProviderDefinition(id="pexels", label="Pexels", env_key="PEXELS_API_KEY", priority=1, capability="media"),
    ProviderDefinition(id="pixabay", label="Pixabay", env_key="PIXABAY_API_KEY", priority=2, capability="media"),
)


def configured_text_providers() -> list[ProviderDefinition]:
    return [provider for provider in TEXT_PROVIDERS if os.getenv(provider.env_key, "").strip()]


def configured_media_providers() -> list[ProviderDefinition]:
    return [provider for provider in MEDIA_PROVIDERS if os.getenv(provider.env_key, "").strip()]


def _status(provider: ProviderDefinition) -> dict[str, object]:
    return {
        "id": provider.id,
        "label": provider.label,
        "capability": provider.capability,
        "priority": provider.priority,
        "configured": bool(os.getenv(provider.env_key, "").strip()),
    }


def provider_status() -> list[dict[str, object]]:
    return [_status(provider) for provider in (*TEXT_PROVIDERS, *MEDIA_PROVIDERS)]


@router.get("/status")
def get_provider_status():
    configured_text = configured_text_providers()
    configured_media = configured_media_providers()
    return {
        "providers": provider_status(),
        "failover_order": {
            "text": [provider.id for provider in TEXT_PROVIDERS],
            "media": [provider.id for provider in MEDIA_PROVIDERS],
        },
        "ready": {
            "text": bool(configured_text),
            "media": bool(configured_media),
        },
        "active": {
            "text": configured_text[0].id if configured_text else None,
            "media": configured_media[0].id if configured_media else None,
        },
    }
