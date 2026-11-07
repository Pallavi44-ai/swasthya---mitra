"""Gemini REST client (multimodal LLM, embeddings, audio transcription).

NOTE: implemented against Google's documented REST API (generativelanguage.googleapis.com/v1beta)
and verified with mocked HTTP responses only. A real GEMINI_API_KEY and network access are needed
to exercise it live. The API key is sent in a header, never logged and never exposed to the browser.
"""
from __future__ import annotations

import base64
import json
import logging
import re
import time

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiError(Exception):
    """Any failure talking to Gemini (network, quota, safety block, bad output)."""


class GeminiUnavailable(GeminiError):
    """No API key configured."""


class GeminiClient:
    def __init__(self, api_key: str | None, model: str, embed_model: str, timeout: float = 40.0, transport=None):
        self.api_key, self.model, self.embed_model = api_key, model, embed_model
        self._client = httpx.Client(timeout=timeout, transport=transport)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    # -- low level ------------------------------------------------------------------------------
    def _post(self, path: str, body: dict, retries: int = 2) -> dict:
        if not self.configured:
            raise GeminiUnavailable("GEMINI_API_KEY is not configured")
        last: Exception | None = None
        for attempt in range(retries + 1):
            try:
                r = self._client.post(f"{BASE_URL}/{path}", json=body, headers={"x-goog-api-key": self.api_key})
            except httpx.HTTPError as exc:
                last = exc
                log.warning("Gemini network error (%s), attempt %d", type(exc).__name__, attempt + 1)
            else:
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                    last = GeminiError(f"HTTP {r.status_code}")
                else:
                    # include Google's error message but never our key/request body
                    msg = ""
                    try:
                        msg = r.json().get("error", {}).get("message", "")[:200]
                    except Exception:  # noqa: BLE001
                        pass
                    raise GeminiError(f"Gemini returned HTTP {r.status_code}: {msg}")
            time.sleep(0.5 * (2**attempt))
        raise GeminiError(f"Gemini request failed: {type(last).__name__ if last else 'unknown'}")

    @staticmethod
    def _text_of(data: dict) -> str:
        fb = data.get("promptFeedback", {})
        if fb.get("blockReason"):
            raise GeminiError(f"Prompt blocked: {fb['blockReason']}")
        cands = data.get("candidates") or []
        if not cands:
            raise GeminiError("No candidates returned")
        parts = (cands[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise GeminiError(f"Empty response (finishReason={cands[0].get('finishReason')})")
        return text

    # -- public ---------------------------------------------------------------------------------
    def generate(
        self, *, system: str, contents: list[dict], json_schema: dict | None = None,
        temperature: float = 0.2, max_tokens: int = 1200,
    ) -> str:
        gen_cfg: dict = {"temperature": temperature, "maxOutputTokens": max_tokens}
        if json_schema:
            gen_cfg["responseMimeType"] = "application/json"
            gen_cfg["responseSchema"] = json_schema
        body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "generationConfig": gen_cfg}
        path = f"models/{self.model}:generateContent"
        try:
            return self._text_of(self._post(path, body))
        except GeminiError as exc:
            if json_schema and "HTTP 400" in str(exc):  # schema dialect rejected → retry, prompt-only JSON
                gen_cfg.pop("responseSchema", None)
                return self._text_of(self._post(path, body))
            raise

    def generate_json(self, **kwargs) -> dict:
        text = self.generate(**kwargs)
        return parse_json_loose(text)

    def embed(self, texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 50):
            batch = texts[i : i + 50]
            body = {
                "requests": [
                    {"model": f"models/{self.embed_model}", "content": {"parts": [{"text": t}]}, "taskType": task}
                    for t in batch
                ]
            }
            data = self._post(f"models/{self.embed_model}:batchEmbedContents", body)
            embs = data.get("embeddings") or []
            if len(embs) != len(batch):
                raise GeminiError("Embedding count mismatch")
            out.extend(e["values"] for e in embs)
        return out

    def transcribe(self, audio: bytes, mime: str, language_name: str) -> str:
        prompt = (
            f"Transcribe this audio exactly as spoken. The speaker is most likely speaking {language_name} "
            "(code-mixed speech is possible). Return only the transcript text in the original script, nothing else. "
            "If the audio is silent or unintelligible, return an empty string."
        )
        contents = [{"role": "user", "parts": [
            {"text": prompt}, {"inlineData": {"mimeType": mime, "data": base64.b64encode(audio).decode()}},
        ]}]
        try:
            return self.generate(system="You are a careful speech transcription engine.", contents=contents, temperature=0.0, max_tokens=800)
        except GeminiError as exc:
            if "Empty response" in str(exc):
                return ""
            raise


def parse_json_loose(text: str) -> dict:
    """Parse JSON even if wrapped in markdown fences or surrounded by prose."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    raise GeminiError("Model did not return valid JSON")


_client: GeminiClient | None = None


def get_gemini() -> GeminiClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = GeminiClient(s.gemini_api_key, s.gemini_model, s.gemini_embedding_model, s.gemini_timeout_seconds)
    return _client


def set_gemini(client: GeminiClient | None) -> None:
    """Test hook."""
    global _client
    _client = client
