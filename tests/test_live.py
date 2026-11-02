import os
import pytest
from app.ollama import OllamaClient
from app.schemas import Report, Settings


@pytest.mark.live
@pytest.mark.skipif(os.getenv('LOCALAI_LIVE')!='1',reason='Set LOCALAI_LIVE=1 for real local model inference')
async def test_real_ollama():
    client=OllamaClient(Settings)
    try:
        models=await client.models()
        assert {'qwen3:4b','qwen2.5-coder:7b'} <= set(models)
        result=await client.generate('research','You generate concise hypothetical reports.','Give one sentence about a local todo app.',Report)
        assert result.body
    finally:
        await client.close()
