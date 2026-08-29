import json
from unittest.mock import patch

import pytest

from src.core.synthesizer import Synthesizer, SynthesizerError


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.body).encode("utf-8")


def test_synthesize_uses_llama_structured_output():
    synthesizer = Synthesizer(
        model_name="deepseek-v3",
        api_url="http://localhost:11434/api/generate",
        timeout_seconds=30,
    )
    response = FakeResponse({"response": '{"entities":["Synthesizer"]}'})

    with patch("src.core.synthesizer.urllib.request.urlopen", return_value=response) as urlopen:
        result = synthesizer.synthesize("Updated the synthesizer.")

    assert json.loads(result) == {"entities": ["Synthesizer"]}
    request = urlopen.call_args.args[0]
    payload = json.loads(request.data)
    assert payload["model"] == "deepseek-v3"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["format"]["required"] == ["entities"]
    assert urlopen.call_args.kwargs["timeout"] == 30


def test_synthesize_for_journal_returns_technical_sections():
    synthesizer = Synthesizer(model_name="deepseek-v3", timeout_seconds=30)
    response = FakeResponse(
        {
            "response": (
                '{"summary":"Completed validation.",'
                '"sections":[{"title":"Validation","work_done":"Ran tests.",'
                '"went_well":"Tests passed.","learned":"Coverage matters.",'
                '"remember":"Keep tests fast.","commits":["abc123"]}]}'
            )
        }
    )

    with patch("src.core.synthesizer.urllib.request.urlopen", return_value=response):
        result = synthesizer.synthesize_for_journal("Git commits: abc123")

    assert json.loads(result)["sections"][0]["commits"] == ["abc123"]


def test_synthesize_day_overview_returns_summary():
    synthesizer = Synthesizer(model_name="deepseek-v3", timeout_seconds=30)
    response = FakeResponse({"response": '{"summary":"Completed validation."}'})

    with patch("src.core.synthesizer.urllib.request.urlopen", return_value=response):
        summary = synthesizer.synthesize_day_overview(
            "2026-08-29", "Tests passed."
        )

    assert summary == "Completed validation."


def test_synthesize_rejects_invalid_structured_output():
    synthesizer = Synthesizer(model_name="deepseek-v3", timeout_seconds=30)
    response = FakeResponse({"response": "not JSON"})

    with patch("src.core.synthesizer.urllib.request.urlopen", return_value=response):
        with pytest.raises(SynthesizerError, match="invalid structured output"):
            synthesizer.synthesize("Updated the synthesizer.")


def test_synthesize_rejects_an_invalid_entities_shape():
    synthesizer = Synthesizer(model_name="deepseek-v3", timeout_seconds=30)
    response = FakeResponse({"response": '{"entities":[{"name":"Synthesizer"}]}'})

    with patch("src.core.synthesizer.urllib.request.urlopen", return_value=response):
        with pytest.raises(SynthesizerError, match="entities.*strings"):
            synthesizer.synthesize("Updated the synthesizer.")
