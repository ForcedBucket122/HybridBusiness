import asyncio
import json
import logging
import re
import time

import httpx
from pydantic import ValidationError

log = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    pass


def parse_json(content):
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.S).strip()
    if content.startswith('```'):
        content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find('{'), content.rfind('}')
        if start < 0 or end < start:
            raise ValueError('Model nie zwrócił JSON.')
        return json.loads(content[start:end + 1])


class OllamaClient:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.lock = asyncio.Lock()
        self.http = httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False)
        self.metrics = []

    async def close(self):
        await self.http.aclose()

    async def models(self):
        try:
            response = await self.http.get(self.settings().ollama_url + '/api/tags', timeout=5)
            response.raise_for_status()
            return [m['name'] for m in response.json()['models'] if not m.get('remote_host') and 'cloud' not in m['name'].lower()]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise OllamaError('Brak połączenia z lokalną Ollama. Uruchom ollama serve.') from exc

    async def generate(self, role, system, prompt, schema):
        async with self.lock:
            cfg = self.settings()
            model = cfg.models[role]
            if model not in await self.models():
                raise OllamaError(f'Brak lokalnego modelu {model}. Modele nie są pobierane automatycznie.')
            # /api/show guards against a remote-backed alias even on a local server.
            response = await self.http.post(cfg.ollama_url + '/api/show', json={'model': model}, timeout=10)
            response.raise_for_status()
            if response.json().get('remote_host') or response.json().get('remote_model'):
                raise OllamaError('Model wskazuje usługę zdalną; inferencja została zablokowana.')
            messages = [
                {'role': 'system', 'content': system + '\nReturn only JSON matching this schema: ' + json.dumps(schema.model_json_schema())},
                {'role': 'user', 'content': prompt},
            ]
            error = ''
            for attempt in range(cfg.max_attempts):
                started = time.monotonic()
                estimated_input = (len(json.dumps(messages, ensure_ascii=False).encode('utf-8')) + 2) // 3
                output_budget = min(cfg.max_tokens, cfg.context_size - estimated_input - 256)
                if output_budget < 256:
                    raise OllamaError('Kontekst wraz ze schematem nie pozostawia miejsca na odpowiedź. Zmniejsz zakres zadania.')
                try:
                    response = await self.http.post(cfg.ollama_url + '/api/chat', timeout=cfg.timeout, json={
                        'model': model, 'messages': messages, 'format': schema.model_json_schema(),
                        'stream': False, 'think': False, 'keep_alive': 0,
                        'options': {'temperature': cfg.temperature, 'num_predict': output_budget, 'num_ctx': cfg.context_size},
                    })
                    response.raise_for_status()
                    payload = response.json()
                    self.metrics.append({'role': role, 'model': model, 'attempt': attempt + 1,
                        'seconds': round(time.monotonic() - started, 3), 'estimated_input_tokens': estimated_input,
                        'output_budget': output_budget, 'prompt_eval_count': payload.get('prompt_eval_count'),
                        'eval_count': payload.get('eval_count'), 'done_reason': payload.get('done_reason')})
                    self.metrics = self.metrics[-20:]
                    if payload.get('done_reason') == 'length':
                        raise ValueError('Odpowiedź ucięta przez limit tokenów; zmniejsz zakres zadania.')
                    result = schema.model_validate(parse_json(payload['message']['content']))
                    log.info('LLM role=%s model=%s seconds=%.2f attempt=%s', role, model, time.monotonic() - started, attempt + 1)
                    return result
                except (httpx.HTTPError, ValueError, KeyError, ValidationError) as exc:
                    if isinstance(exc, ValidationError):
                        error = '; '.join('.'.join(map(str, e['loc'])) + ': ' + e['type']
                                          for e in exc.errors(include_input=False, include_url=False)[:8])
                    elif isinstance(exc, httpx.HTTPError):
                        error = type(exc).__name__
                    else:
                        error = 'Invalid or incomplete JSON response (' + type(exc).__name__ + ')'
                    log.warning('LLM role=%s attempt=%s error_type=%s', role, attempt + 1, type(exc).__name__)
                    messages.append({'role': 'user', 'content': 'Previous response was invalid: ' + error +
                        '. Return complete JSON with ALL required fields. Keep it concise.'})
                    if attempt + 1 < cfg.max_attempts:
                        await asyncio.sleep(0.5)
            raise OllamaError(f'Niepoprawna odpowiedź Ollama po {cfg.max_attempts} próbach: {error}')
