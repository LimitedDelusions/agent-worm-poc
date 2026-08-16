import httpx
from agent_worm_poc.adapters import OpenAICompatibleAdapter
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
