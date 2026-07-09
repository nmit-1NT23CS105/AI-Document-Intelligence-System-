from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Protocol

import httpx

from app.core.config import get_settings


class LLMClient(Protocol):
    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        ...


class LLMProviderError(RuntimeError):
    pass


class GeminiLLMClient:
    def __init__(
        self,
        api_key: str,
        model_name: str,
        base_url: str,
        temperature: float,
        timeout_seconds: int,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url
        self.temperature = temperature
        self.http_client = http_client or httpx.Client(timeout=timeout_seconds)

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        model = self.model_name.removeprefix("models/")
        response = self.http_client.post(
            self.base_url.rstrip("/"),
            headers={"x-goog-api-key": self.api_key},
            json={
                "model": model,
                "input": user_prompt,
                "system_instruction": system_prompt,
                "generation_config": {"temperature": self.temperature},
            },
        )
        response.raise_for_status()
        text = _extract_generated_text(response.json()).strip()
        if not text:
            raise LLMProviderError("Gemini response did not include generated text.")
        return text


def _extract_generated_text(payload: Any) -> str:
    if isinstance(payload, dict):
        output_text = payload.get("output_text")
        if isinstance(output_text, str):
            return output_text

        candidates = payload.get("candidates")
        if isinstance(candidates, list):
            parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
            return "\n".join(
                part.get("text", "")
                for part in parts
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            )

        steps = payload.get("steps")
        if isinstance(steps, list):
            text_parts = []
            for step in steps:
                if isinstance(step, dict) and isinstance(step.get("text"), str):
                    text_parts.append(step["text"])
                if isinstance(step, dict) and isinstance(step.get("content"), list):
                    for content in step["content"]:
                        if isinstance(content, dict) and isinstance(content.get("text"), str):
                            text_parts.append(content["text"])
            return "\n".join(text_parts)

    return ""


def _strip_json_fence(text: str) -> str:
    cleaned = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return cleaned


def parse_llm_summary(text: str, max_key_points: int) -> tuple[str, list[str]] | None:
    try:
        payload = json.loads(_strip_json_fence(text))
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    short_summary = str(payload.get("short_summary") or "").strip()
    raw_key_points = payload.get("key_points") or []
    key_points = [
        str(point).strip()
        for point in raw_key_points
        if str(point).strip()
    ][:max_key_points]

    if not short_summary and not key_points:
        return None
    return short_summary, key_points


@lru_cache
def get_llm_client() -> LLMClient | None:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()

    if provider == "gemini" and settings.gemini_api_key.strip():
        return GeminiLLMClient(
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_model,
            base_url=settings.gemini_api_base_url,
            temperature=settings.llm_temperature,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    return None
