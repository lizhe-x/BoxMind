"""Gateway request extras (OpenRouter provider routing, reasoning switch) and the API key fallback."""
from app.config import settings
from app.services.llm import LLM


def test_no_extras_by_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider_order", "")
    monkeypatch.setattr(settings, "llm_allow_fallbacks", True)
    monkeypatch.setattr(settings, "llm_reasoning", "")
    assert LLM.request_extras() == {}


def test_provider_order_and_reasoning_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider_order", "coreweave, decart,parasail,,inceptron")
    monkeypatch.setattr(settings, "llm_allow_fallbacks", True)
    monkeypatch.setattr(settings, "llm_reasoning", "off")
    assert LLM.request_extras() == {
        "provider": {"allow_fallbacks": True, "order": ["coreweave", "decart", "parasail", "inceptron"]},
        "reasoning": {"enabled": False},
    }


def test_fallbacks_can_be_disabled_without_an_order(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider_order", "")
    monkeypatch.setattr(settings, "llm_allow_fallbacks", False)
    monkeypatch.setattr(settings, "llm_reasoning", "")
    assert LLM.request_extras() == {"provider": {"allow_fallbacks": False}}


def test_api_key_falls_back_to_openrouter_env(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-env")
    assert LLM()._headers["Authorization"] == "Bearer sk-or-env"
    monkeypatch.setattr(settings, "llm_api_key", "sk-explicit")
    assert LLM()._headers["Authorization"] == "Bearer sk-explicit"
    assert LLM()._headers["X-Title"] == "BoxMind"


def test_usage_is_added_to_the_current_trace() -> None:
    from app.services import trace
    from app.services.llm import _count_tokens

    t = trace.start("agent")
    _count_tokens({"prompt_tokens": 1200, "completion_tokens": 40, "total_tokens": 1240})
    _count_tokens(None)
    _count_tokens({"total_tokens": 10})
    assert t.tokens == 1250
