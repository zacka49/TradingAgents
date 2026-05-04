from unittest.mock import patch

import pytest

from tradingagents.llm_clients.factory import create_llm_client


@pytest.mark.unit
@patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI")
def test_groq_provider_uses_openai_compatible_endpoint(mock_chat, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")

    client = create_llm_client("groq", "openai/gpt-oss-20b")
    client.get_llm()

    kwargs = mock_chat.call_args.kwargs
    assert kwargs["base_url"] == "https://api.groq.com/openai/v1"
    assert kwargs["api_key"] == "groq-test-key"
    assert kwargs["model"] == "openai/gpt-oss-20b"
