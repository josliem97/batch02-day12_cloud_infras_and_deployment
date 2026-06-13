from app.providers.openai_provider import OpenAIProvider
from app.providers.openrouter_provider import OpenRouterProvider
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.opencode_provider import OpenCodeProvider


def make_provider(name: str):
    if name == "openai":
        return OpenAIProvider()
    if name == "openrouter":
        return OpenRouterProvider()
    if name == "anthropic":
        return AnthropicProvider()
    if name == "gemini":
        return GeminiProvider()
    if name == "opencode":
        return OpenCodeProvider()
    raise ValueError(f"Unknown provider: {name}")
