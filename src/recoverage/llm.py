"""LLM provider. The default path never opens a socket."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from recoverage.models import Gap


class LLMClient(Protocol):
    name: str

    def complete(self, *, system: str, user: str, timeout: float = 30) -> str: ...


@dataclass
class OpenAICompatibleClient:
    """Chat completions against any OpenAI-compatible base URL. Stdlib HTTP only."""

    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    name: str = "openai-compatible"

    def complete(self, *, system: str, user: str, timeout: float = 30) -> str:
        url = self.base_url.rstrip("/") + "/chat/completions"
        body = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload["choices"][0]["message"]["content"])


def client_from_env(*, mode: str) -> LLMClient | None:
    """mode is auto, on, or off. auto uses a client only when the API key is set."""
    if mode == "off":
        return None
    key = os.environ.get("RECOVERAGE_LLM_API_KEY", "").strip()
    if not key:
        if mode == "on":
            raise RuntimeError("RECOVERAGE_LLM_API_KEY is not set")
        return None
    return OpenAICompatibleClient(
        api_key=key,
        base_url=os.environ.get("RECOVERAGE_LLM_BASE_URL", "https://api.openai.com/v1"),
        model=os.environ.get("RECOVERAGE_LLM_MODEL", "gpt-4o-mini"),
    )


def enrich_gaps(gaps: list[Gap], client: LLMClient | None) -> tuple[list[Gap], str]:
    if client is None or not gaps:
        return gaps, "off" if client is None else client.name
    payload = [
        {
            "id": gap.id,
            "severity": gap.severity,
            "kind": gap.kind,
            "title": gap.title,
            "why": gap.why,
            "file": gap.file,
            "symbol": gap.symbol,
            "suggestion": gap.suggestion,
        }
        for gap in gaps[:20]
    ]
    system = (
        "You review test-coverage gaps. Return JSON only: "
        '{"gaps":[{"id":"G01","why":"...","suggestion":"..."}]}. '
        "Do not invent coverage numbers. Keep why under 80 words."
    )
    user = json.dumps({"gaps": payload})
    try:
        raw = client.complete(system=system, user=user)
    except Exception as exc:
        note = Gap(
            id="",
            severity="low",
            kind="llm-error",
            title="LLM enrichment failed",
            why=f"The OpenAI-compatible call failed ({type(exc).__name__}: {exc}). Heuristic gaps were kept.",
            file="",
            symbol=None,
            suggestion="Re-run with --no-llm or check RECOVERAGE_LLM_BASE_URL and the key.",
            heuristic=True,
        )
        gaps = [*gaps, note]
        for index, gap in enumerate(gaps, start=1):
            if gap.kind == "llm-error":
                gap.id = f"G{index:02d}"
        return gaps, "heuristic-fallback"
    parsed = _parse_json_object(raw)
    updates = {item.get("id"): item for item in (parsed or {}).get("gaps", []) if isinstance(item, dict)}
    if not updates:
        return gaps, client.name
    enriched: list[Gap] = []
    for gap in gaps:
        update = updates.get(gap.id)
        if not update:
            enriched.append(gap)
            continue
        why = str(update.get("why") or gap.why).strip()
        suggestion = str(update.get("suggestion") or gap.suggestion).strip()
        enriched.append(
            Gap(
                id=gap.id,
                severity=gap.severity,
                kind=gap.kind,
                title=gap.title,
                why=why,
                file=gap.file,
                symbol=gap.symbol,
                suggestion=suggestion,
                heuristic=gap.heuristic,
                llm_enriched=True,
            )
        )
    return enriched, client.name


def _parse_json_object(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None
