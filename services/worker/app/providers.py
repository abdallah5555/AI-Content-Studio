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


def configured_text_providers() -> list[ProviderDefinition]:
    return [provider for provider in TEXT_PROVIDERS if os.getenv(provider.env_key, "").strip()]


def provider_status() -> list[dict[str, object]]:
    return [
        {
            "id": provider.id,
            "label": provider.label,
            "capability": provider.capability,
            "priority": provider.priority,
            "configured": bool(os.getenv(provider.env_key, "").strip()),
        }
        for provider in TEXT_PROVIDERS
    ]


@router.get("/status")
def get_provider_status():
    configured = configured_text_providers()
    return {
        "providers": provider_status(),
        "failover_order": [provider.id for provider in TEXT_PROVIDERS],
        "ready": bool(configured),
        "active": configured[0].id if configured else None,
    }
