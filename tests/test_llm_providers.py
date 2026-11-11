from pipeline import config, llm


def test_anthropic_provider_registered_and_parsed():
    assert llm._parse("anthropic:claude-sonnet-5-5") == ("anthropic", "claude-sonnet-5-5")
    assert llm.PROVIDERS["anthropic"][0] == "ANTHROPIC_API_KEY"
    assert "ANTHROPIC_API_KEY" in config.API_KEY_VARS


def test_anthropic_call_sets_default_max_tokens(monkeypatch):
    seen = {}

    class Fake:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    seen.update(kw)
                    msg = type("M", (), {"content": "hi"})
                    return type("R", (), {"choices": [type("C", (), {"message": msg})]})

    monkeypatch.setattr(llm, "_client", lambda provider: Fake)
    assert llm._call_openai("anthropic", "claude-sonnet-5-5", "x", "sys", False, None, 0.3) == "hi"
    assert seen["max_tokens"] == 8192
