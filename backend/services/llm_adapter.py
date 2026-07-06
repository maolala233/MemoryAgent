"""LLM adapter layer with mock, Ollama, and OpenAI providers plus embeddings."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import random
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from ..config.settings import settings
from ..utils.logger import error, info, warn
from .config_loader import get_models_config


# ----------------------------------------------------------------------------
# Embeddings
# ----------------------------------------------------------------------------
class EmbeddingProvider:
    """Base embedding provider."""

    @property
    def dim(self) -> int:
        return settings.embedding_dim

    async def embed(self, text: str) -> List[float]:
        raise NotImplementedError

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [await self.embed(t) for t in texts]


class MockEmbedding(EmbeddingProvider):
    """Deterministic hash-based embedding for offline use."""

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, text: str) -> List[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        # Expand hash to dim bytes by repeating
        needed = self._dim
        bytes_buf = bytearray()
        counter = 0
        while len(bytes_buf) < needed:
            counter += 1
            bytes_buf.extend(hashlib.sha256(h + counter.to_bytes(4, "big")).digest())
        vec = [(b - 128) / 128.0 for b in bytes_buf[:needed]]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class OllamaEmbedding(EmbeddingProvider):
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def embed(self, text: str) -> List[float]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
            )
            resp.raise_for_status()
            return resp.json().get("embedding", [])


class OpenAIEmbedding(EmbeddingProvider):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        self.api_key = api_key
        self.model = model

    async def embed(self, text: str) -> List[float]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"input": text, "model": self.model},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]


def get_embedding_provider() -> EmbeddingProvider:
    provider = settings.embedding_provider.lower()
    if provider == "ollama":
        return OllamaEmbedding(settings.ollama_base_url, settings.embedding_model)
    if provider == "openai":
        if not settings.openai_api_key:
            warn("OpenAI embedding requested but no API key; falling back to mock")
            return MockEmbedding(settings.embedding_dim)
        return OpenAIEmbedding(settings.openai_api_key, "text-embedding-3-small")
    return MockEmbedding(settings.embedding_dim)


# ----------------------------------------------------------------------------
# LLM providers
# ----------------------------------------------------------------------------
class LLMProvider:
    """Base LLM provider."""

    name = "base"

    async def generate(self, prompt: str, system_prompt: str = "",
                       temperature: float = 0.7, max_tokens: int = 1024) -> str:
        raise NotImplementedError

    async def stream_generate(self, prompt: str, system_prompt: str = "",
                              temperature: float = 0.7,
                              max_tokens: int = 1024) -> AsyncIterator[str]:
        # Default fallback: generate then chunk the output
        text = await self.generate(prompt, system_prompt, temperature, max_tokens)
        for chunk in _chunk_text(text, size=24):
            yield chunk
            await asyncio.sleep(0.02)

    async def validate_connection(self) -> bool:
        return True


def _chunk_text(text: str, size: int = 24) -> List[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), max(1, size // 4)):
        chunks.append(" ".join(words[i:i + size // 4 + 1]))
    if not chunks:
        chunks = [text]
    return chunks


class MockLLM(LLMProvider):
    name = "mock"

    def __init__(self, model: str = "mock-gpt") -> None:
        self.model = model

    async def generate(self, prompt: str, system_prompt: str = "",
                       temperature: float = 0.7, max_tokens: int = 1024) -> str:
        await asyncio.sleep(0.1)
        return self._render(prompt, system_prompt, streaming=False)

    async def stream_generate(self, prompt: str, system_prompt: str = "",
                              temperature: float = 0.7,
                              max_tokens: int = 1024) -> AsyncIterator[str]:
        text = self._render(prompt, system_prompt, streaming=True)
        for token in text.split():
            yield token + " "
            await asyncio.sleep(0.04)

    @staticmethod
    def _render(prompt: str, system_prompt: str, streaming: bool) -> str:
        role_note = ""
        if system_prompt:
            first_line = system_prompt.strip().splitlines()[0]
            role_note = f"_{first_line}_\n\n"
        preview = prompt.strip().splitlines()[0][:140] if prompt.strip() else ""
        body = (
            f"{role_note}"
            f"**Mock response** for: `{preview}`\n\n"
            "This is the offline mock provider. To enable a real LLM, set "
            "`default_llm_provider: ollama` or `openai` in `backend/config/models.yaml` "
            "and configure the corresponding environment variables.\n\n"
            "Suggested next steps:\n"
            "1. Review retrieved memories below\n"
            "2. Refine the question with more context\n"
            "3. Use `/agents` to switch agents\n"
        )
        if streaming:
            body += "\n[stream complete]"
        return body


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate(self, prompt: str, system_prompt: str = "",
                       temperature: float = 0.7, max_tokens: int = 1024) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")

    async def stream_generate(self, prompt: str, system_prompt: str = "",
                              temperature: float = 0.7,
                              max_tokens: int = 1024) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}/api/generate",
                                     json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = data.get("response", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break

    async def validate_connection(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception as exc:
            error("Ollama connection failed", exc)
            return False


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str, timeout: int = 60) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _messages(self, prompt: str, system_prompt: str) -> List[Dict[str, str]]:
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    async def generate(self, prompt: str, system_prompt: str = "",
                       temperature: float = 0.7, max_tokens: int = 1024) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": self._messages(prompt, system_prompt),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def stream_generate(self, prompt: str, system_prompt: str = "",
                              temperature: float = 0.7,
                              max_tokens: int = 1024) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": self._messages(prompt, system_prompt),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        data = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    delta = data["choices"][0].get("delta", {}).get("content", "")
                    if delta:
                        yield delta

    async def validate_connection(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code == 200
        except Exception as exc:
            error("OpenAI connection failed", exc)
            return False


class LLMFactory:
    _registry: Dict[str, type] = {
        "mock": MockLLM,
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
    }

    @classmethod
    def register_provider(cls, name: str, provider_class: type) -> None:
        cls._registry[name.lower()] = provider_class

    @classmethod
    def create(cls, provider_name: Optional[str] = None,
               model: Optional[str] = None) -> LLMProvider:
        cfg = get_models_config()
        name = (provider_name or cfg.get("default_provider") or
                settings.default_llm_provider or "mock").lower()
        providers = cfg.get("providers", {})
        provider_cfg = providers.get(name, {})
        type_name = provider_cfg.get("type", name).lower()
        klass = cls._registry.get(type_name, MockLLM)
        if klass is MockLLM:
            return MockLLM(model or provider_cfg.get("model", "mock-gpt"))
        if klass is OllamaProvider:
            return OllamaProvider(
                base_url=provider_cfg.get("base_url", settings.ollama_base_url),
                model=model or provider_cfg.get("model", settings.ollama_model),
                timeout=int(provider_cfg.get("timeout", 120)),
            )
        if klass is OpenAIProvider:
            api_key = provider_cfg.get("api_key") or settings.openai_api_key
            return OpenAIProvider(
                api_key=api_key or "",
                model=model or provider_cfg.get("model", settings.openai_model),
                timeout=int(provider_cfg.get("timeout", 60)),
            )
        return MockLLM()


llm_factory = LLMFactory()
