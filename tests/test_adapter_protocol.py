import httpx
import pytest
from agent_worm_poc.adapters import CompletionTransportFailure,OpenAICompatibleAdapter
from agent_worm_poc.types import ModelSpec


def test_real_adapter_requests_json_schema(monkeypatch):
    captured = {}

    class Response:
        status_code = 200
        def raise_for_status(self): return None
        def json(self):
            return {"choices":[{"message":{"content":"{\"artifact_title\":\"x\",\"artifact_body\":\"" + "a"*100 + "\",\"review_flags\":[]}"}}],"usage":{}}

    class Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def post(self, url, json, headers):
            captured.update(json)
            return Response()

    monkeypatch.setattr(httpx, "Client", Client)
    model = ModelSpec("m","m","repo","r"*40,"r"*40,"served","auto",8192)
    schema = {"type":"object","required":["artifact_title","artifact_body","review_flags"],
              "properties":{"artifact_title":{"type":"string"},"artifact_body":{"type":"string"},
                            "review_flags":{"type":"array","items":{"type":"string"}}}}
    result = OpenAICompatibleAdapter().complete(model,[{"role":"user","content":"x"}],1,.2,.95,100,
                                                 {"stage":"relay","schema":schema})
    assert result.parsed["artifact_title"] == "x"
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["schema"]["additionalProperties"] is False


def test_real_adapter_records_successful_transport_retry(monkeypatch):
    calls = 0

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '{"ok":true}'}}], "usage": {}}

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.ReadTimeout("simulated timeout")
            return Response()

    monkeypatch.setattr(httpx, "Client", Client)
    monkeypatch.setattr("agent_worm_poc.adapters.time.sleep", lambda _: None)
    model = ModelSpec("m", "m", "repo", "r" * 40, "r" * 40, "served", "auto", 8192)
    result = OpenAICompatibleAdapter(retries=1).complete(
        model,
        [{"role": "user", "content": "x"}],
        1,
        0.2,
        0.95,
        100,
        {"stage": "relay", "schema": {"type": "object"}},
    )

    assert result.transport_attempts == 2
    assert result.transport_retry_errors == ("ReadTimeout",)


def test_real_adapter_records_terminal_transport_attempts(monkeypatch):
    calls = 0

    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "Client", Client)
    monkeypatch.setattr("agent_worm_poc.adapters.time.sleep", lambda _: None)
    model = ModelSpec("m", "m", "repo", "r" * 40, "r" * 40, "served", "auto", 8192)
    with pytest.raises(CompletionTransportFailure) as captured:
        OpenAICompatibleAdapter(retries=1).complete(
            model,
            [{"role": "user", "content": "x"}],
            1,
            0.2,
            0.95,
            100,
            {"stage": "relay", "schema": {"type": "object"}},
        )

    assert calls == 2
    assert captured.value.transport_attempts == 2
    assert captured.value.transport_retry_errors == ("ConnectError", "ConnectError")


def test_real_adapter_does_not_retry_malformed_successful_output(monkeypatch):
    calls=0

    class Response:
        status_code=200
        text='{"choices":[{"message":{"content":"not-json"}}]}'
        def raise_for_status(self):return None
        def json(self):return {"choices":[{"message":{"content":"not-json"}}],"usage":{}}

    class Client:
        def __init__(self,*_args,**_kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*_args):pass
        def post(self,*_args,**_kwargs):
            nonlocal calls
            calls+=1
            return Response()

    monkeypatch.setattr(httpx,"Client",Client)
    model=ModelSpec("m","m","repo","r"*40,"r"*40,"served","auto",8192)
    result=OpenAICompatibleAdapter(retries=1).complete(
        model,[{"role":"user","content":"x"}],1,.2,.95,100,
        {"stage":"relay","schema":{"type":"object"}},
    )
    assert calls==1 and result.transport_attempts==1
    assert result.raw_text=="not-json" and result.parsed is None
