import httpx
import pytest
from app.ollama import OllamaClient, OllamaError, parse_json
from app.schemas import Report, Settings


@pytest.mark.parametrize('text', ['{"ok":true}', '```json\n{"ok":true}\n```', '<think>private</think>{"ok":true}', 'Result: {"ok":true}'])
def test_json_fallback(text):
    assert parse_json(text) == {'ok':True}


async def test_retry_and_structured_output():
    calls = []
    def handler(request):
        if request.url.path == '/api/tags':
            return httpx.Response(200,json={'models':[{'name':'qwen3:4b'}]})
        if request.url.path == '/api/show':
            return httpx.Response(200,json={})
        calls.append(request)
        return httpx.Response(200,json={'message':{'content':'bad' if len(calls)==1 else '{"title":"OK","body":"Report","evidence":"estimated"}'}})
    client = OllamaClient(Settings, httpx.MockTransport(handler))
    report = await client.generate('ceo','system','prompt',Report)
    assert report.title == 'OK' and len(calls)==2
    assert b'"keep_alive":0' in calls[0].content
    await client.close()


async def test_missing_model_never_pulls():
    paths=[]
    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200,json={'models':[]})
    client = OllamaClient(Settings,httpx.MockTransport(handler))
    with pytest.raises(OllamaError,match='Brak lokalnego modelu'):
        await client.generate('ceo','','',Report)
    assert paths == ['/api/tags']
    await client.close()


async def test_remote_alias_blocked():
    def handler(request):
        return httpx.Response(200,json={'models':[{'name':'qwen3:4b'}]} if request.url.path.endswith('tags') else {'remote_host':'ollama.com'})
    client=OllamaClient(Settings,httpx.MockTransport(handler))
    with pytest.raises(OllamaError,match='zdalną'):
        await client.generate('ceo','','',Report)
    await client.close()


async def test_offline():
    def handler(request):
        raise httpx.ConnectError('offline',request=request)
    client=OllamaClient(Settings,httpx.MockTransport(handler))
    with pytest.raises(OllamaError,match='Brak połączenia'):
        await client.models()
    await client.close()
